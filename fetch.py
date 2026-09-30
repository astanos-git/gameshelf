"""Fetch PlayStation data + Metacritic scores and write docs/data.json for the dashboard.

Env vars (set as GitHub Actions secrets):
  PSN_NPSSO     your NPSSO token (required)
  RAWG_API_KEY  free key from https://rawg.io/apidocs (optional, for Metacritic/genres)
"""
from __future__ import annotations

import difflib
import hashlib
import math
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
OUT = ROOT / "docs" / "data.json"
CACHE = ROOT / "rawg_cache.json"          # remembers RAWG lookups between runs
TROPHY_CACHE = ROOT / "trophy_dates.json" # when each trophy was earned, per trophy list
HLTB_CACHE = ROOT / "hltb_cache.json"     # remembers HowLongToBeat lookups
TROPHY_BUDGET_S = 35 * 60                 # max time per run spent on trophy dates
OVERRIDES = ROOT / "overrides.json"       # manual fixes: {"PSN name": "rawg-slug" or null}

# ---------------------------------------------------------------- helpers

NOISE = re.compile(
    r"\b(ps4|ps5|playstation ?[45]|ps4 (&|and) ps5|ps5 version|ps4 version|"
    r"digital|deluxe|standard|edition|remastered edition)\b|[™®©:'’\-–—.,!()\[\]]"
)


def norm(name: str) -> str:
    """Normalise a title so the same game matches across PSN endpoints."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = NOISE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def trophy_set(ts) -> dict:
    return {"bronze": ts.bronze, "silver": ts.silver, "gold": ts.gold, "platinum": ts.platinum}


# ---------------------------------------------------------------- PSN

def fetch_psn(npsso: str) -> dict:
    """Pull everything we need from PSN into plain dicts."""
    from psnawp_api import PSNAWP

    me = PSNAWP(npsso).me()
    print(f"Signed in as {me.online_id}")

    summary = me.trophy_summary()
    avatar = None
    try:
        urls = me.get_profile_legacy()["profile"].get("avatarUrls", [])
        avatar = urls[-1]["avatarUrl"] if urls else None
    except Exception as e:  # cosmetic only
        print(f"  avatar skipped: {e}")

    profile = {
        "online_id": me.online_id,
        "avatar": avatar,
        "trophy_level": summary.trophy_level,
        "level_progress": summary.progress,
        "earned": trophy_set(summary.earned_trophies),
    }

    trophies = []
    for t in me.trophy_titles(limit=None):
        trophies.append({
            "np_id": t.np_communication_id,
            "name": t.title_name,
            "icon": t.title_icon_url,
            "platforms": sorted(p.value for p in t.title_platform),
            "progress": t.progress or 0,
            "earned": trophy_set(t.earned_trophies),
            "defined": trophy_set(t.defined_trophies),
            "last_trophy": iso(t.last_updated_datetime),
            "has_groups": bool(t.has_trophy_groups),
            "set_version": t.trophy_set_version,
        })
    print(f"  {len(trophies)} trophy lists")

    stats = []
    for s in me.title_stats(limit=None):
        stats.append({
            "title_id": s.title_id,
            "name": s.name,
            "image": s.image_url,
            "platform": {"ps4_game": "PS4", "ps5_native_game": "PS5"}.get(s.category.value if s.category else "", None),
            "hours": round(s.play_duration.total_seconds() / 3600, 1) if s.play_duration else 0,
            "first_played": iso(s.first_played_date_time),
            "last_played": iso(s.last_played_date_time),
        })
    print(f"  {len(stats)} played titles (PS4/PS5)")

    owned = []
    try:
        for e in me.game_entitlements(limit=None):
            if e.get("isBeta") or e.get("isGame") is False:
                continue
            tm, cm, gm = e.get("titleMeta") or {}, e.get("conceptMeta") or {}, e.get("gameMeta") or {}
            owned.append({
                "title_id": tm.get("titleId"),
                "concept_id": cm.get("conceptId"),
                "name": cm.get("name") or tm.get("name") or gm.get("name"),
                "image": tm.get("imageUrl") or cm.get("iconUrl") or gm.get("iconUrl"),
                "platform": "PS5" if gm.get("packageType") == "PSGD" else "PS4",
                "acquired": e.get("activeDate"),
            })
        print(f"  {len(owned)} owned titles (PS4/PS5 digital)")
    except Exception as e:
        print(f"  owned games skipped: {e}")

    # Map trophy lists to PS4/PS5 title IDs so versions/names line up.
    title_to_np = {}
    ids = sorted({x["title_id"] for x in stats + owned if x.get("title_id")})
    for i in range(0, len(ids), 5):
        try:
            for t in me.trophy_titles_for_title(ids[i:i + 5]):
                if t.np_title_id and t.np_communication_id:
                    title_to_np[t.np_title_id] = t.np_communication_id
        except Exception as e:
            print(f"  trophy/title mapping batch skipped: {e}")

    fetch_trophy_dates(me, trophies)
    fetch_group_names(me, trophies)

    return {"profile": profile, "trophies": trophies, "stats": stats, "owned": owned, "title_to_np": title_to_np}


# ---------------------------------------------------------------- trophy dates

TIER_INDEX = {"bronze": 0, "silver": 1, "gold": 2, "platinum": 3}


TROPHY_VERSION = 2   # bump to re-read every trophy list (2: keep full trophy details)
TROPHY_DIR = ROOT / "docs" / "trophies"


def trophy_row(tr) -> dict:
    """One trophy, with short keys to keep the files small."""
    rate = tr.trophy_earn_rate
    row = {"id": tr.trophy_id, "n": tr.trophy_name, "d": tr.trophy_detail, "t": tr.trophy_type.value if tr.trophy_type else None,
           "i": tr.trophy_icon_url, "g": tr.trophy_group_id, "e": bool(tr.earned),
           "at": iso(tr.earned_date_time) if tr.earned else None,
           "r": round(float(rate), 1) if rate not in (None, "") else None}
    if tr.trophy_hidden:
        row["h"] = True
    target = getattr(tr, "trophy_progress_target_value", None)
    if target and not tr.earned:
        row["p"] = f"{tr.progress or 0}/{target}"
    return row


def fetch_trophy_dates(me, trophies: list[dict]) -> None:
    """Read each trophy list: save full details to docs/trophies/<list>.json and attach
    {"YYYY-MM": [bronze, silver, gold, platinum]} plus your rarest earned trophies.

    Only lists that changed since the last run are fetched (2 requests each), so the
    first run is slow and later runs are quick. Stops after a time budget and
    continues on the next refresh.
    """
    from psnawp_api.models.trophies import PlatformType

    cache = json.loads(TROPHY_CACHE.read_text()) if TROPHY_CACHE.exists() else {}
    started, fetched, pending = time.time(), 0, 0
    for t in trophies:
        entry = cache.get(t["np_id"])
        if not entry or entry.get("updated") != t["last_trophy"] or entry.get("v", 1) < TROPHY_VERSION:
            if time.time() - started > TROPHY_BUDGET_S:
                pending += 1
            else:
                try:
                    plats = [p for p in t["platforms"] if p != "UNKNOWN"]
                    plat = PlatformType("PS5" if "PS5" in plats else (plats[0] if plats else "PS4"))
                    months: dict[str, list[int]] = {}
                    rows = []
                    for tr in me.trophies(t["np_id"], plat, include_progress=True, trophy_group_id="all"):
                        rows.append(trophy_row(tr))
                        if tr.earned and tr.earned_date_time and tr.trophy_type:
                            m = months.setdefault(tr.earned_date_time.strftime("%Y-%m"), [0, 0, 0, 0])
                            m[TIER_INDEX[tr.trophy_type.value]] += 1
                    TROPHY_DIR.mkdir(parents=True, exist_ok=True)
                    (TROPHY_DIR / f"{t['np_id']}.json").write_text(json.dumps(
                        {"list": t["name"], "platforms": t["platforms"], "trophies": rows},
                        ensure_ascii=False, separators=(",", ":")))
                    rare = sorted((r for r in rows if r["e"] and r["r"] is not None), key=lambda r: r["r"])[:5]
                    entry = cache[t["np_id"]] = {"updated": t["last_trophy"], "months": months, "v": TROPHY_VERSION,
                                                 "rare": [{k: r[k] for k in ("n", "t", "r", "at", "i")} for r in rare]}
                    fetched += 1
                except Exception as e:
                    print(f"  trophy dates skipped for {t['name']!r}: {e}")
        t["months"] = (entry or {}).get("months", {})
        t["rare"] = (entry or {}).get("rare", [])
    TROPHY_CACHE.write_text(json.dumps(cache, sort_keys=True, separators=(",", ":")))
    print(f"  trophy dates: {fetched} lists fetched" + (f", {pending} left for the next refresh" if pending else ""))


def add_months(a: dict, b: dict) -> dict:
    out = {k: list(v) for k, v in a.items()}
    for k, v in b.items():
        out[k] = [x + y for x, y in zip(out.get(k, [0, 0, 0, 0]), v)]
    return out


def estimate_hours_by_year(g: dict) -> dict[str, float]:
    """Split a game's lifetime playtime across years (PSN only gives the total).

    Half is spread evenly over the days between first and last played, half follows
    when trophies were earned. Falls back to whichever signal exists.
    """
    hours = g["hours"]
    if not hours:
        return {}
    first, last = g.get("first_played"), g.get("last_played")
    by_days: dict[str, float] = {}
    if first and last:
        d0, d1 = datetime.fromisoformat(first).date(), datetime.fromisoformat(last).date()
        span = max((d1 - d0).days, 0) + 1
        for y in range(d0.year, d1.year + 1):
            a, b = max(d0, datetime(y, 1, 1).date()), min(d1, datetime(y, 12, 31).date())
            by_days[str(y)] = ((b - a).days + 1) / span
    elif last or first:
        by_days[(last or first)[:4]] = 1.0

    by_trophy: dict[str, float] = {}
    lo, hi = (first or "0000")[:4], (last or "9999")[:4]
    counts: dict[str, int] = {}
    for month, tiers in (g.get("months") or {}).items():
        if lo <= month[:4] <= hi:
            counts[month[:4]] = counts.get(month[:4], 0) + sum(tiers)
    total = sum(counts.values())
    if total:
        by_trophy = {y: n / total for y, n in counts.items()}

    if by_days and by_trophy:
        share = {y: 0.5 * by_days.get(y, 0) + 0.5 * by_trophy.get(y, 0) for y in set(by_days) | set(by_trophy)}
    else:
        share = by_days or by_trophy
    return {y: round(hours * s, 1) for y, s in sorted(share.items()) if round(hours * s, 1) > 0}


def loose(name: str) -> str:
    """Compare names ignoring odd spaces (PSN uses non-breaking spaces in some titles)."""
    return re.sub(r"\s+", " ", (name or "").replace("\xa0", " ")).strip()


TRANSLATED = re.compile(r"[éèêàçùâîôû]|\b(l'|d'|le|la|les|du|des|et|de|el|los|der|die|und)\b", re.I)


PLATFORM_SUFFIX = re.compile(r"\s*[-–:]?\s*\b(PS4™?\s*(&|and)\s*PS5™?|PS5™?\s*(&|and)\s*PS4™?|PS[45] Version|\(PS[45]\))\s*$", re.I)


def looks_translated(name: str) -> bool:
    """The Swiss store translates some titles into French: prefer the playtime/trophy name for those."""
    return bool(TRANSLATED.search(name.replace("’", "'")))


def names_override() -> dict:
    return (json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}).get("names", {})


# ---------------------------------------------------------------- merge

def build_games(raw: dict) -> list[dict]:
    """Merge trophies, playtime and ownership into one row per game."""
    games: dict[str, dict] = {}
    key_of_title: dict[str, str] = {}   # title_id -> game key
    key_of_concept: dict[str, str] = {}
    key_of_np: dict[str, str] = {}

    NAME_RANK = {"owned": 2, "playtime": 1, "trophies": 0}  # store name first, unless it's translated

    def row(key: str, name: str, source: str) -> dict:
        g = games.setdefault(key, {
            "name": name, "names": {}, "image": None, "platforms": set(), "owned": False, "acquired": None,
            "hours": 0.0, "first_played": None, "last_played": None,
            "progress": None, "earned": None, "defined": None, "last_trophy": None, "has_trophies": False, "months": {}, "trophy_lists": [], "rare": [],
        })
        name = re.sub(r"\s+Trophies$", "", (name or "").strip())  # some trophy lists are called "<game> Trophies"
        if name:
            rank = -1 if source == "owned" and looks_translated(name) else NAME_RANK[source]
            g["names"][name] = max(g["names"].get(name, -9), rank)
        return g

    # 1. Owned games (group PS4/PS5 versions by concept)
    for o in raw["owned"]:
        key = key_of_concept.get(o["concept_id"]) or norm(o["name"])
        if o["concept_id"]:
            key_of_concept[o["concept_id"]] = key
        if o["title_id"]:
            key_of_title[o["title_id"]] = key
        g = row(key, o["name"], "owned")
        g["owned"] = True
        g["platforms"].add(o["platform"])
        g["image"] = g["image"] or o["image"]
        if o["acquired"] and (not g["acquired"] or o["acquired"] < g["acquired"]):
            g["acquired"] = o["acquired"]

    # 2. Playtime (summed across versions)
    for s in raw["stats"]:
        key = key_of_title.get(s["title_id"]) or norm(s["name"])
        key_of_title.setdefault(s["title_id"], key)
        g = row(key, s["name"], "playtime")
        if s["platform"]:
            g["platforms"].add(s["platform"])
        g["image"] = g["image"] or s["image"]
        g["hours"] = round(g["hours"] + s["hours"], 1)
        if s["first_played"] and (not g["first_played"] or s["first_played"] < g["first_played"]):
            g["first_played"] = s["first_played"]
        if s["last_played"] and (not g["last_played"] or s["last_played"] > g["last_played"]):
            g["last_played"] = s["last_played"]

    for tid, np_id in raw["title_to_np"].items():
        if tid in key_of_title:
            key_of_np.setdefault(np_id, key_of_title[tid])

    # 3. Trophies (if several lists map to one game, keep the most advanced one)
    for t in raw["trophies"]:
        key = key_of_np.get(t["np_id"]) or norm(t["name"])
        g = row(key, t["name"], "trophies")
        g["platforms"].update(p for p in t["platforms"] if p != "UNKNOWN")
        g["image"] = g["image"] or t["icon"]
        g["months"] = add_months(g["months"], t.get("months") or {})  # every list counts toward yearly stats
        g["trophy_lists"].append({"id": t["np_id"], "platforms": [p for p in t["platforms"] if p != "UNKNOWN"], "progress": t["progress"],
                                  "groups": t.get("group_names") or {}})
        g["rare"] = sorted(g["rare"] + (t.get("rare") or []), key=lambda r: r["r"])[:5]
        if g["progress"] is None or t["progress"] > g["progress"]:
            g.update(progress=t["progress"], earned=t["earned"], defined=t["defined"],
                     last_trophy=t["last_trophy"], has_trophies=True)

    english = {loose(k): v for k, v in names_override().items()}
    out = []
    for g in games.values():
        # Display the original name: your English-name list first, then playtime > trophy list > store name.
        seen = g.pop("names")
        best = max(seen, key=lambda n: seen[n]) if seen else g["name"]
        g["name"] = next((english[loose(n)] for n in seen if loose(n) in english), best)
        g["name"] = PLATFORM_SUFFIX.sub("", g["name"]).strip() or g["name"]   # "Kena PS4 & PS5" -> "Kena"
        g["aliases"] = sorted(n for n in seen if n != g["name"])
        g["trophy_lists"].sort(key=lambda x: -x["progress"])  # most advanced list first
        g["platforms"] = sorted(g["platforms"])
        if g["defined"]:
            earned_n = sum(g["earned"].values())
            total_n = sum(g["defined"].values())
            g["trophies_earned"], g["trophies_total"] = earned_n, total_n
            g["platinum"] = g["earned"]["platinum"] > 0
        else:
            g["trophies_earned"] = g["trophies_total"] = 0
            g["platinum"] = False
        played = g["hours"] > 0 or (g["progress"] or 0) > 0 or g["last_played"]
        if g["platinum"] or g["progress"] == 100:
            g["status"] = "completed"
        elif played:
            g["status"] = "started"
        else:
            g["status"] = "unplayed"
        g["last_activity"] = max(filter(None, [g["last_played"], g["last_trophy"]]), default=None)
        g["hours_by_year"] = estimate_hours_by_year(g)
        out.append(g)
    return out


# ---------------------------------------------------------------- RAWG / Metacritic

def enrich(games: list[dict], key: str | None) -> None:
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    overrides = json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}
    looked_up = 0

    for g in games:
        name = g["name"]
        info = cache.get(name)
        if name in overrides and (info or {}).get("slug") != overrides[name]:
            info = None  # override changed -> refetch
        if info is None and key:
            info = rawg_lookup(name, overrides.get(name, ""), key, name in overrides)
            cache[name] = info
            looked_up += 1
            time.sleep(0.25)
        info = info or {}
        g["metacritic"] = info.get("metacritic")
        g["genres"] = info.get("genres", [])
        g["released"] = info.get("released")
        g["rawg_slug"] = info.get("slug")

    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True, ensure_ascii=False))
    print(f"RAWG: {looked_up} new lookups, {len(cache)} cached")


def rawg_lookup(name: str, slug: str | None, key: str, forced: bool) -> dict:
    """Return {'slug','metacritic','genres','released'}; {} means 'no match' (cached so we don't retry)."""
    try:
        if forced:
            if not slug:
                return {}  # override set to null: deliberately no match
            r = requests.get(f"https://api.rawg.io/api/games/{slug}", params={"key": key}, timeout=20)
            r.raise_for_status()
            hit = r.json()
        else:
            r = requests.get("https://api.rawg.io/api/games", timeout=20, params={
                "key": key, "search": name, "search_precise": "true", "parent_platforms": 2, "page_size": 5})
            r.raise_for_status()
            results = r.json().get("results", [])
            n = norm(name)
            hit = next((x for x in results if norm(x["name"]) == n), results[0] if results else None)
            if not hit:
                return {}
        return {
            "slug": hit.get("slug"),
            "metacritic": hit.get("metacritic"),
            "genres": [x["name"] for x in hit.get("genres") or []],
            "released": hit.get("released"),
        }
    except Exception as e:
        print(f"  RAWG failed for {name!r}: {e}")
        return None  # not cached -> retried next run


# ---------------------------------------------------------------- HowLongToBeat

SEARCH_NOISE = re.compile(
    r"[™®©]|\((ps4|ps5)\)|\b(ps5|ps4) version\b|\b(ps4|ps5)( ?(&|and) ?(ps4|ps5))?\b|"
    r"\b(digital )?(deluxe|standard|gold|ultimate|complete|definitive|game of the year|goty) edition\b",
    re.I)


def search_name(name: str) -> str:
    s = name.replace("’", "'").replace("\xa0", " ").replace("Ⅲ", "III")
    s = re.sub(r"\s+", " ", re.sub(r"[™®©]", " ", s))
    s = SEARCH_NOISE.sub(" ", s)
    s = re.sub(r"\s*[—–]\s*remastered$|\s+vr$|\s+\([^)]*\)$|\s+trophy set$", "", s.strip(), flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" -–:")


HLTB_VERSION = 3  # bump to retry earlier misses after improving matching


def enrich_hltb(games: list[dict]) -> None:
    """Add HowLongToBeat times (hours). Unofficial and best-effort: any failure leaves the fields empty."""
    cache = json.loads(HLTB_CACHE.read_text()) if HLTB_CACHE.exists() else {}
    overrides = {loose(k): v for k, v in ((json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}).get("hltb", {})).items()}
    try:
        from howlongtobeatpy import HowLongToBeat
        hltb = HowLongToBeat()
    except Exception as e:
        print(f"HowLongToBeat unavailable: {e}")
        hltb = None

    looked_up, failures = 0, 0
    for g in games:
        name = g["name"]
        query = overrides.get(loose(name)) or search_name(name)
        info = cache.get(name)
        if info is not None:
            if info.get("url"):
                if loose(name) in overrides and info.get("query") != query:
                    info = None  # you changed the override -> look up again
            elif info.get("query") != query or info.get("v", 1) < HLTB_VERSION:
                info = None  # a miss from an older matching method -> try again
        if info is None and hltb and failures < 5:
            try:
                best = None
                for q in dict.fromkeys([query, query.replace(":", " "), query.split(" - ")[0]]):  # simpler variants on a miss
                    results = hltb.search(re.sub(r"\s+", " ", q).strip(), similarity_case_sensitive=False) or []
                    best = max(results, key=lambda r: r.similarity, default=None)
                    if best and best.similarity >= 0.6:
                        break
                if best and best.similarity >= 0.6:
                    info = {"query": query, "name": best.game_name, "url": best.game_web_link,
                            "main": best.main_story or None, "extra": best.main_extra or None,
                            "complete": best.completionist or None}
                else:
                    info = {"query": query, "v": HLTB_VERSION}  # no confident match; remembered so we don't retry
                cache[name] = info
                looked_up += 1
                failures = 0
                time.sleep(1)
            except Exception as e:
                failures += 1  # several failures in a row = HLTB is blocking us; stop for this run
                print(f"  HLTB failed for {name!r}: {e}")
        info = info or {}
        g["hltb"] = {k: info[k] for k in ("main", "extra", "complete", "url") if info.get(k)} or None

    HLTB_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True, ensure_ascii=False))
    print(f"HLTB: {looked_up} new lookups, {sum(1 for v in cache.values() if v.get('url'))} matched in cache"
          + (" (stopped early after repeated errors)" if failures >= 5 else ""))


# ---------------------------------------------------------------- Wikidata (Metacritic gap filler)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
# Every Metacritic score (P444 "review score", qualified by P447 "review score by" = Metacritic Q150248),
# with the platform it's for (P400) and the game's RAWG ID (P9968) for exact matching.
WIKIDATA_QUERY = """
SELECT ?game ?score ?platform ?rawg WHERE {
  ?game p:P444 ?st .
  ?st ps:P444 ?score ; pq:P447 wd:Q150248 .
  OPTIONAL { ?st pq:P400 ?platform }
  ?game wdt:P9968 ?rawg .
}"""
PLATFORM_PREF = {"Q63184502": 0, "Q5014725": 1}  # PlayStation 5, PlayStation 4; anything else after


def fetch_wikidata_scores() -> dict:
    """Return {rawg_slug: score} for games with a Metacritic critic score and a RAWG ID (exact matches only)."""
    r = requests.get(WIKIDATA_SPARQL, params={"query": WIKIDATA_QUERY, "format": "json"}, timeout=90,
                     headers={"User-Agent": "GameShelf/1.0 (personal PSN dashboard; github.com)",
                              "Accept": "application/sparql-results+json"})
    r.raise_for_status()
    best: dict[str, tuple[int, int, str | None, str | None]] = {}  # game -> (rank, score, rawg, label)
    for b in r.json()["results"]["bindings"]:
        m = re.match(r"^\s*(\d{1,3})\s*/\s*100\s*$", b["score"]["value"])  # critic Metascore; skips x/10 user scores
        if not m:
            continue
        game = b["game"]["value"]
        plat = b.get("platform", {}).get("value", "").rsplit("/", 1)[-1]
        rank = PLATFORM_PREF.get(plat, 2)
        cand = (rank, int(m.group(1)), b["rawg"]["value"].lower())
        if game not in best or rank < best[game][0]:
            best[game] = cand
    print(f"Wikidata: {len(best)} games with a Metacritic score and a RAWG ID")
    return {rawg: score for _, score, rawg in best.values()}


def fill_metacritic(games: list[dict], previous_games: list[dict]) -> None:
    """Fill games RAWG has no score for: your manual scores first, then Wikidata."""
    overrides = (json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}).get("metacritic", {})
    for g in games:
        g["metacritic_source"] = "rawg" if g.get("metacritic") else None
        if g["name"] in overrides and overrides[g["name"]] is not None:
            g["metacritic"], g["metacritic_source"] = int(overrides[g["name"]]), "manual"

    missing = [g for g in games if not g.get("metacritic")]
    if not missing:
        return

    # 1. Wikidata, exact match on RAWG ID
    try:
        by_rawg = fetch_wikidata_scores()
    except Exception as e:
        print(f"Wikidata skipped ({e}); keeping previous scores")
        by_rawg = None
        old = {p["name"]: p["metacritic"] for p in previous_games if p.get("metacritic_source") == "wikidata"}
        for g in missing:
            if g["name"] in old:
                g["metacritic"], g["metacritic_source"] = old[g["name"]], "wikidata"
    for g in missing:
        if by_rawg and by_rawg.get((g.get("rawg_slug") or "").lower()):
            g["metacritic"], g["metacritic_source"] = by_rawg[g["rawg_slug"].lower()], "wikidata"

    # 2. Wikipedia's review box for what's still missing (cached, so it survives Wikipedia being down)
    enrich_wikipedia([g for g in missing if not g.get("metacritic")])
    print(f"::notice::Metacritic: {sum(1 for g in missing if g.get('metacritic'))} of {len(missing)} gaps filled "
          f"({sum(1 for g in missing if g.get('metacritic_source') == 'wikidata')} Wikidata, "
          f"{sum(1 for g in missing if g.get('metacritic_source') == 'wikipedia')} Wikipedia)")


# ---------------------------------------------------------------- Wikipedia (Metacritic from the review box)

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_CACHE = ROOT / "wikipedia_cache.json"
WIKI_VERSION = 4       # bump to redo every lookup after improving matching
WIKI_RETRY_DAYS = 30  # retry games without a score after this long (new releases get reviewed)
WIKI_HEADERS = {"User-Agent": "GameShelf/1.0 (personal PSN dashboard; github.com)"}
PLATFORM_ORDER = ["PS5", "PS4"]
REFS = re.compile(r"<ref[^>]*/>|<ref.*?</ref>|\{\{\s*(cite|efn|sfn|refn|citation|dead link)[^{}]*\}\}|'{2,3}", re.S | re.I)
TEMPLATE_OPEN = re.compile(r"\{\{\s*[^{}|]*\|")  # {{nowrap| ... }} -> keep the inside


def parse_metacritic(wikitext: str) -> int | str | None:
    """Pick the Metacritic score from a game article's {{Video game reviews}} box: PS5, then PS4, then any.

    Returns "wikidata" when the box says to take the score from Wikidata.
    """
    if not re.search(r"\{\{\s*Video game (multiple console )?reviews", wikitext, re.I):
        return None
    # Per-platform fields: | MC_PS5 = 76/100
    per_plat = {p.upper(): int(v) for p, v in re.findall(r"\|\s*MC_(\w+)\s*=\s*[^\n|]*?\b(\d{1,3})\s*/\s*100", wikitext)}
    for plat in PLATFORM_ORDER:
        if plat in per_plat:
            return per_plat[plat]
    m = re.search(r"\|\s*MC\s*=(.*?)(?=\n\s*\||\n\s*\}\})", wikitext, re.S)
    if not m:
        return next(iter(per_plat.values()), None)
    if m.group(1).strip().lower() == "wikidata":
        return "wikidata"
    value = TEMPLATE_OPEN.sub(" ", REFS.sub(" ", m.group(1))).replace("}}", " ")
    # "PS5: 89/100" or "(PS5) 89/100" or just "89/100"
    scores = re.findall(r"(?:\(?\b([A-Za-z0-9]+)\)?\s*:?\s+)?\b(\d{1,3})\s*/\s*100\b", value)
    if not scores:
        return None
    by_plat = {p.upper(): int(v) for p, v in scores if p}
    for plat in PLATFORM_ORDER:
        if plat in by_plat:
            return by_plat[plat]
    return int(scores[0][1])


def wikidata_item_score(item: str) -> int | None:
    """Metacritic critic score stored on one Wikidata item (PS5, then PS4, then any)."""
    r = requests.get("https://www.wikidata.org/w/api.php", headers=WIKI_HEADERS, timeout=20,
                     params={"action": "wbgetentities", "ids": item, "props": "claims", "format": "json"})
    r.raise_for_status()
    best = None
    for c in r.json().get("entities", {}).get(item, {}).get("claims", {}).get("P444", []):
        q = c.get("qualifiers", {})
        by = [x.get("datavalue", {}).get("value", {}).get("id") for x in q.get("P447", [])]
        m = re.match(r"^\s*(\d{1,3})\s*/\s*100\s*$", c.get("mainsnak", {}).get("datavalue", {}).get("value", "") or "")
        if "Q150248" not in by or not m:
            continue
        plats = [x.get("datavalue", {}).get("value", {}).get("id") for x in q.get("P400", [])]
        rank = min((PLATFORM_PREF.get(p, 2) for p in plats), default=2)
        if best is None or rank < best[0]:
            best = (rank, int(m.group(1)))
    return best[1] if best else None


def clean_title(title: str) -> str:
    return norm(re.sub(r"\s*\((\d{4} )?video game\)$", "", title))


def wiki_get(params: dict) -> dict:
    """Call the Wikipedia API, waiting and retrying when it asks us to slow down."""
    for attempt in range(4):
        r = requests.get(WIKI_API, headers=WIKI_HEADERS, timeout=20, params={**params, "format": "json", "maxlag": 5})
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        throttled = r.status_code in (429, 503) or data.get("error", {}).get("code") in ("maxlag", "ratelimited")
        if not throttled:
            r.raise_for_status()
            if "error" in data:
                raise RuntimeError(data["error"].get("info", "Wikipedia API error"))
            return data
        time.sleep(int(r.headers.get("Retry-After", 0) or 0) or 5 * (attempt + 1))
    raise RuntimeError("Wikipedia kept asking to slow down")


def wikipedia_lookup(name: str, year: str | None = None) -> dict:
    """Find the game's Wikipedia article and read its Metacritic score."""
    query = search_name(name)
    data = wiki_get({"action": "query", "list": "search", "srsearch": f"{query} video game", "srlimit": 6})
    target = norm(query)
    titles = [h["title"] for h in data.get("query", {}).get("search", [])]
    exact = [t for t in titles if clean_title(t) == target]
    # Remakes share a name with the original: prefer the article for the release year, e.g. "(2024 video game)".
    title = next((t for t in exact if year and f"({year} video game)" in t), None) or next(iter(exact), None)
    if not title:
        close = [(difflib.SequenceMatcher(None, clean_title(t), target).ratio(), t) for t in titles]
        best = max(close, default=(0, None))
        title = best[1] if best[0] >= 0.85 else None
    if not title:
        return {}
    data = wiki_get({"action": "parse", "page": title, "prop": "wikitext|properties", "redirects": 1, "formatversion": 2})
    score = parse_metacritic(data.get("parse", {}).get("wikitext", ""))
    if score == "wikidata":  # the article pulls its score from its own Wikidata entry
        item = (data.get("parse", {}).get("properties") or {}).get("wikibase_item")
        score = wikidata_item_score(item) if item else None
    return {"title": title, "score": score} if score else {"title": title}


def enrich_wikipedia(games: list[dict]) -> None:
    cache = json.loads(WIKI_CACHE.read_text()) if WIKI_CACHE.exists() else {}
    today = datetime.now(timezone.utc).date()
    looked_up, failures, errors = 0, 0, []
    for g in games:
        info = cache.get(g["name"])
        stale = info is not None and not info.get("score") and (info.get("v", 1) < WIKI_VERSION or
            (today - datetime.fromisoformat(info.get("checked", "2000-01-01")).date()).days > WIKI_RETRY_DAYS)
        if (info is None or stale) and failures < 8:
            try:
                info = {**wikipedia_lookup(g["name"], (g.get("released") or "")[:4] or None),
                        "checked": today.isoformat(), "v": WIKI_VERSION}
                cache[g["name"]] = info
                looked_up += 1
                failures = 0
            except Exception as e:
                failures += 1
                errors.append(f"{g['name']}: {type(e).__name__}: {str(e)[:120]}")
                time.sleep(5 * failures)
            time.sleep(1)
        if info and info.get("score"):
            g["metacritic"], g["metacritic_source"] = info["score"], "wikipedia"
    WIKI_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True, ensure_ascii=False))
    print(f"::notice::Wikipedia: {looked_up} lookups, {len(errors)} errors" + (f" (first: {errors[0]})" if errors else "")
          + (" - stopped early, the rest continue next refresh" if failures >= 8 else ""))




# ---------------------------------------------------------------- DLC group names

GROUP_CACHE = ROOT / "trophy_groups.json"   # {list id: {"v": trophy set version, "names": {group id: name}}}
GROUP_BUDGET_S = 10 * 60


def fetch_group_names(me, trophies: list[dict]) -> None:
    """Names of the base game and DLC packs for lists that have DLC (1 request each, cached)."""
    from psnawp_api.models.trophies import PlatformType
    cache = json.loads(GROUP_CACHE.read_text()) if GROUP_CACHE.exists() else {}
    started, fetched = time.time(), 0
    for t in trophies:
        entry = cache.get(t["np_id"])
        if t.get("has_groups") and (not entry or entry.get("v") != t.get("set_version")) and time.time() - started < GROUP_BUDGET_S:
            try:
                plats = [p for p in t["platforms"] if p != "UNKNOWN"]
                plat = PlatformType("PS5" if "PS5" in plats else (plats[0] if plats else "PS4"))
                summary = me.trophy_groups_summary(t["np_id"], plat)
                entry = cache[t["np_id"]] = {"v": t.get("set_version"),
                                             "names": {g.trophy_group_id: g.trophy_group_name for g in summary.trophy_groups}}
                fetched += 1
            except Exception as e:
                print(f"  DLC names skipped for {t['name']!r}: {e}")
        t["group_names"] = (entry or {}).get("names", {})
    GROUP_CACHE.write_text(json.dumps(cache, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    print(f"  DLC names: {fetched} lists fetched")


# ---------------------------------------------------------------- Wikidata: franchise, developer, publisher

ABOUT_CACHE = ROOT / "wikidata_about.json"


def fetch_about(slugs: list[str]) -> dict:
    """{rawg slug: {"series": [...], "developers": [...], "publishers": [...]}} in one query; cached if Wikidata is down."""
    cache = json.loads(ABOUT_CACHE.read_text()) if ABOUT_CACHE.exists() else {}
    if not slugs:
        return cache
    values = " ".join(json.dumps(s) for s in sorted(set(slugs)))
    query = f"""SELECT ?rawg ?seriesLabel ?devLabel ?pubLabel WHERE {{
      VALUES ?rawg {{ {values} }} ?g wdt:P9968 ?rawg .
      OPTIONAL {{ ?g wdt:P179 ?series }} OPTIONAL {{ ?g wdt:P178 ?dev }} OPTIONAL {{ ?g wdt:P123 ?pub }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }} }}"""
    try:
        r = requests.post(WIKIDATA_SPARQL, data={"query": query, "format": "json"}, timeout=90,
                          headers={"User-Agent": "GameShelf/1.0 (https://github.com/astanos-git/gameshelf)",
                                   "Accept": "application/sparql-results+json"})
        r.raise_for_status()
        about: dict[str, dict[str, list[str]]] = {}
        for b in r.json()["results"]["bindings"]:
            a = about.setdefault(b["rawg"]["value"], {"series": [], "developers": [], "publishers": []})
            for key, field in (("seriesLabel", "series"), ("devLabel", "developers"), ("pubLabel", "publishers")):
                v = b.get(key, {}).get("value")
                if v and not re.fullmatch(r"Q\d+", v) and v not in a[field]:   # skip items without an English label
                    a[field].append(v)
        ABOUT_CACHE.write_text(json.dumps(about, sort_keys=True, ensure_ascii=False, indent=1))
        print(f"::notice::Wikidata: {sum(1 for a in about.values() if a['series'])} games with a series, "
              f"{sum(1 for a in about.values() if a['developers'])} with a developer")
        return about
    except Exception as e:
        print(f"::warning::Wikidata series/studios skipped ({e}); keeping the last ones")
        return cache


def add_about(games: list[dict]) -> None:
    about = fetch_about([g["rawg_slug"] for g in games if g.get("rawg_slug")])
    for g in games:
        a = about.get(g.get("rawg_slug") or "", {})
        g["series"], g["developers"], g["publishers"] = a.get("series", []), a.get("developers", []), a.get("publishers", [])


# ---------------------------------------------------------------- insights (from the saved trophy lists)

LOCAL_TZ = "Europe/Zurich"
COUNT_MILESTONES = [1, 100, 250, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 5000, 6000, 7500, 10000]


def load_trophy_file(list_id: str) -> list[dict]:
    path = TROPHY_DIR / f"{list_id}.json"
    return json.loads(path.read_text())["trophies"] if path.exists() else []


def hunter_points(rate: float) -> float:
    """0 for a trophy everyone has, 50 at 10% of players, 100 at 1% or rarer."""
    return max(0.0, min(100.0, 50 * math.log10(100 / max(rate, 0.01))))


def dlc_progress(g: dict) -> list[dict]:
    """Earned / total per DLC pack (every group except the base game), across the game's trophy lists."""
    out = []
    for lst in g.get("trophy_lists") or []:
        counts: dict[str, list[int]] = {}
        for t in load_trophy_file(lst["id"]):
            c = counts.setdefault(t.get("g") or "default", [0, 0])
            c[0] += 1 if t.get("e") else 0
            c[1] += 1
        for gid, (e, n) in sorted(counts.items()):
            if gid != "default":
                out.append({"list": lst["id"], "id": gid, "name": (lst.get("groups") or {}).get(gid) or f"DLC {gid}",
                            "platforms": lst["platforms"], "earned": e, "total": n})
    return out


def build_insights(games: list[dict]) -> dict:
    """Activity by day / weekday / hour (Swiss time), milestones, and per-game trophy facts.

    Adds to each game: first_trophy_at, platinum_at, missing_n and easy (its most common missing trophies).
    """
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(LOCAL_TZ)
    earned = []                   # (local datetime, trophy, game)
    for g in games:
        first = plat = None
        best_missing, missing_n = [], 0
        for i, lst in enumerate(g.get("trophy_lists") or []):
            rows = load_trophy_file(lst["id"])
            for t in rows:
                if t.get("e") and t.get("at"):
                    when = datetime.fromisoformat(t["at"]).astimezone(tz)
                    earned.append((when, t, g))
                    first = min(first, t["at"]) if first else t["at"]
                    if t.get("t") == "platinum":
                        plat = min(plat, t["at"]) if plat else t["at"]
            if i == 0:  # the most advanced list decides what's left to do
                missing = [t for t in rows if not t.get("e")]
                missing_n = len(missing)
                best_missing = sorted(missing, key=lambda t: -(t.get("r") or 0))[:3]
        g["first_trophy_at"], g["platinum_at"] = first, plat
        g["dlc"] = dlc_progress(g)
        g["missing_n"] = missing_n
        g["easy"] = [{k: t.get(k) for k in ("n", "t", "r", "h", "p")} for t in best_missing]

    earned.sort(key=lambda x: x[0])
    days: dict[str, int] = {}
    wh: dict[str, list[int]] = {}   # year -> 7x24 counts (Monday first), plus "all"
    for when, _, _ in earned:
        days[when.strftime("%Y-%m-%d")] = days.get(when.strftime("%Y-%m-%d"), 0) + 1
        for key in (str(when.year), "all"):
            wh.setdefault(key, [0] * 168)[when.weekday() * 24 + when.hour] += 1

    rarity: dict[str, dict] = {}   # year -> {"buckets": [ultra, very rare, rare, common], "score": hunter score}
    for when, t, _ in earned:
        if t.get("r") is None:
            continue
        for key in (str(when.year), "all"):
            e = rarity.setdefault(key, {"buckets": [0, 0, 0, 0], "sum": 0.0, "n": 0})
            e["buckets"][0 if t["r"] < 5 else 1 if t["r"] < 15 else 2 if t["r"] < 50 else 3] += 1
            e["sum"] += hunter_points(t["r"]); e["n"] += 1
    for e in rarity.values():
        e["score"] = round(e.pop("sum") / e.pop("n"))

    milestones = []
    for n, (when, t, g) in enumerate(earned, start=1):
        base = {"at": t["at"], "game": g["name"], "trophy": t.get("n"), "t": t.get("t"), "r": t.get("r"), "i": t.get("i")}
        if n in COUNT_MILESTONES:
            milestones.append({"kind": "first" if n == 1 else "count", "n": n, **base})
        if t.get("t") == "platinum":
            milestones.append({"kind": "platinum", **base})
    print(f"::notice::Insights: {len(earned)} dated trophies, {len(days)} active days, "
          f"{sum(1 for m in milestones if m['kind'] == 'platinum')} platinums")
    return {"tz": LOCAL_TZ, "days": days, "weekday_hour": wh, "milestones": milestones, "rarity": rarity}


# ---------------------------------------------------------------- main

TOKEN_DAYS = 60  # NPSSO tokens last roughly two months


def token_fingerprint(npsso: str) -> str:
    """Short one-way hash, so we can tell when the token changes without publishing it."""
    return hashlib.sha256(npsso.encode()).hexdigest()[:12]


def is_login_error(e: Exception) -> bool:
    name, msg = type(e).__name__, str(e).lower()
    return any(k in name for k in ("Authentication", "InvalidToken", "Unauthorized")) or "npsso" in msg


def main() -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    previous = json.loads(OUT.read_text()) if OUT.exists() else {}
    npsso = os.environ.get("PSN_NPSSO", "").strip()

    try:
        if not npsso:
            raise LookupError("PSN_NPSSO secret is not set")
        raw = fetch_psn(npsso)
    except Exception as e:
        # Keep the last good data, but tell the dashboard what went wrong.
        login = is_login_error(e) or isinstance(e, LookupError)
        previous.setdefault("games", [])
        previous["login"] = {**previous.get("login", {}),
                             "error": "login_expired" if login else "fetch_failed",
                             "message": str(e)[:300], "failed_at": now}
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(previous, indent=1, ensure_ascii=False))
        print(f"::error::{'PSN login failed: renew your NPSSO token (see README).' if login else 'PSN fetch failed'} {e}")
        return  # exit 0 so the status above gets published to the dashboard

    games = build_games(raw)
    enrich(games, os.environ.get("RAWG_API_KEY", "").strip() or None)
    fill_metacritic(games, previous.get("games", []))
    add_about(games)
    enrich_hltb(games)
    games.sort(key=lambda g: g["last_activity"] or g["acquired"] or "", reverse=True)
    try:
        insights = build_insights(games)
    except Exception as e:  # extras only: never block a refresh
        print(f"::warning::Insights skipped: {e}")
        insights = previous.get("insights", {})

    # Track when this token was first used to estimate when it expires.
    fp = token_fingerprint(npsso)
    old = previous.get("login", {})
    since = old.get("since") if old.get("fingerprint") == fp else now
    expires = (datetime.fromisoformat(since) + timedelta(days=TOKEN_DAYS)).isoformat(timespec="seconds")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": now,
        "login": {"fingerprint": fp, "since": since, "expires_estimate": expires},
        "profile": raw["profile"],
        "games": games,
        "insights": insights,
    }, indent=1, ensure_ascii=False))
    print(f"Wrote {len(games)} games to {OUT.name}; token in use since {since[:10]}")


if __name__ == "__main__":
    main()
