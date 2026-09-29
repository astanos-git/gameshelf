"""Fetch PlayStation data + Metacritic scores and write docs/data.json for the dashboard.

Env vars (set as GitHub Actions secrets):
  PSN_NPSSO     your NPSSO token (required)
  RAWG_API_KEY  free key from https://rawg.io/apidocs (optional, for Metacritic/genres)
"""
from __future__ import annotations

import hashlib
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

    return {"profile": profile, "trophies": trophies, "stats": stats, "owned": owned, "title_to_np": title_to_np}


# ---------------------------------------------------------------- trophy dates

TIER_INDEX = {"bronze": 0, "silver": 1, "gold": 2, "platinum": 3}


def fetch_trophy_dates(me, trophies: list[dict]) -> None:
    """Attach {"YYYY-MM": [bronze, silver, gold, platinum]} to each trophy list.

    Only lists that changed since the last run are fetched (2 requests each), so the
    first run is slow and later runs are quick. Stops after a time budget and
    continues on the next refresh.
    """
    from psnawp_api.models.trophies import PlatformType

    cache = json.loads(TROPHY_CACHE.read_text()) if TROPHY_CACHE.exists() else {}
    started, fetched, pending = time.time(), 0, 0
    for t in trophies:
        entry = cache.get(t["np_id"])
        if not entry or entry.get("updated") != t["last_trophy"]:
            if time.time() - started > TROPHY_BUDGET_S:
                pending += 1
            else:
                try:
                    plats = [p for p in t["platforms"] if p != "UNKNOWN"]
                    plat = PlatformType("PS5" if "PS5" in plats else (plats[0] if plats else "PS4"))
                    months: dict[str, list[int]] = {}
                    for tr in me.trophies(t["np_id"], plat, include_progress=True, trophy_group_id="all"):
                        if tr.earned and tr.earned_date_time and tr.trophy_type:
                            m = months.setdefault(tr.earned_date_time.strftime("%Y-%m"), [0, 0, 0, 0])
                            m[TIER_INDEX[tr.trophy_type.value]] += 1
                    entry = cache[t["np_id"]] = {"updated": t["last_trophy"], "months": months}
                    fetched += 1
                except Exception as e:
                    print(f"  trophy dates skipped for {t['name']!r}: {e}")
        t["months"] = (entry or {}).get("months", {})
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


# ---------------------------------------------------------------- merge

def build_games(raw: dict) -> list[dict]:
    """Merge trophies, playtime and ownership into one row per game."""
    games: dict[str, dict] = {}
    key_of_title: dict[str, str] = {}   # title_id -> game key
    key_of_concept: dict[str, str] = {}
    key_of_np: dict[str, str] = {}

    def row(key: str, name: str) -> dict:
        return games.setdefault(key, {
            "name": name, "image": None, "platforms": set(), "owned": False, "acquired": None,
            "hours": 0.0, "first_played": None, "last_played": None,
            "progress": None, "earned": None, "defined": None, "last_trophy": None, "has_trophies": False, "months": {},
        })

    # 1. Owned games (group PS4/PS5 versions by concept)
    for o in raw["owned"]:
        key = key_of_concept.get(o["concept_id"]) or norm(o["name"])
        if o["concept_id"]:
            key_of_concept[o["concept_id"]] = key
        if o["title_id"]:
            key_of_title[o["title_id"]] = key
        g = row(key, o["name"])
        g["owned"] = True
        g["platforms"].add(o["platform"])
        g["image"] = g["image"] or o["image"]
        if o["acquired"] and (not g["acquired"] or o["acquired"] < g["acquired"]):
            g["acquired"] = o["acquired"]

    # 2. Playtime (summed across versions)
    for s in raw["stats"]:
        key = key_of_title.get(s["title_id"]) or norm(s["name"])
        key_of_title.setdefault(s["title_id"], key)
        g = row(key, s["name"])
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
        g = row(key, t["name"])
        g["platforms"].update(p for p in t["platforms"] if p != "UNKNOWN")
        g["image"] = g["image"] or t["icon"]
        g["months"] = add_months(g["months"], t.get("months") or {})  # every list counts toward yearly stats
        if g["progress"] is None or t["progress"] > g["progress"]:
            g.update(progress=t["progress"], earned=t["earned"], defined=t["defined"],
                     last_trophy=t["last_trophy"], has_trophies=True)

    out = []
    for g in games.values():
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
    s = re.sub(r"[™®©]", "", s)
    s = SEARCH_NOISE.sub(" ", s)
    s = re.sub(r"\s*[—–]\s*remastered$|\s+vr$|\s+\([^)]*\)$|\s+trophy set$", "", s.strip(), flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" -–:")


HLTB_VERSION = 2  # bump to retry earlier misses after improving matching


def enrich_hltb(games: list[dict]) -> None:
    """Add HowLongToBeat times (hours). Unofficial and best-effort: any failure leaves the fields empty."""
    cache = json.loads(HLTB_CACHE.read_text()) if HLTB_CACHE.exists() else {}
    loose = lambda n: re.sub(r"\s+", " ", n.replace("\xa0", " ")).strip()  # tolerate odd spaces in names
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
        if info is not None and (info.get("query", query) != query or (not info.get("url") and info.get("v", 1) < HLTB_VERSION)):
            info = None  # override changed, or a miss from an older matching method -> look up again
        if info is None and hltb and failures < 5:
            try:
                results = hltb.search(query, similarity_case_sensitive=False) or []
                best = max(results, key=lambda r: r.similarity, default=None)
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
    enrich_hltb(games)
    games.sort(key=lambda g: g["last_activity"] or g["acquired"] or "", reverse=True)

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
    }, indent=1, ensure_ascii=False))
    print(f"Wrote {len(games)} games to {OUT.name}; token in use since {since[:10]}")


if __name__ == "__main__":
    main()
