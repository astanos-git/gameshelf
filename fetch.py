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

    return {"profile": profile, "trophies": trophies, "stats": stats, "owned": owned, "title_to_np": title_to_np}


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
            "progress": None, "earned": None, "defined": None, "last_trophy": None, "has_trophies": False,
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
