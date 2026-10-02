"""Weekly game recommendations: 3 games you don't own or haven't played, matched to your profile.

Run every Monday by .github/workflows/recommend.yml (or by hand from the Actions tab).
Needs RAWG_API_KEY. Reads docs/data.json, flags and ratings; writes docs/recommendations.json.

How it works:
1. Taste profile from your library: genres and RAWG tags weighted by hours played, games finished,
   your ratings, and games you dropped (negative). Plus your usual game length.
2. Candidates: well-rated PS4/PS5 games from RAWG in your favourite genres and tags.
3. Each candidate is scored on taste fit, Metacritic, and length fit (HowLongToBeat),
   excluding games you own or played and anything recommended in the last 12 weeks.
4. Top 3, kept varied (different main genres), with a short reason for each.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from fetch import IGNORED_TAGS, norm, search_name

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
OUT = DOCS / "recommendations.json"
TAGS_CACHE = ROOT / "rawg_tags.json"      # tags of your own games (fetched once per game)
API = "https://api.rawg.io/api"
HISTORY_WEEKS = 12
PICKS = 3


def get(path: str, key: str, **params) -> dict:
    for attempt in range(3):
        r = requests.get(f"{API}/{path}", params={"key": key, **params}, timeout=30)
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        time.sleep(0.3)
        return r.json()
    raise RuntimeError("RAWG kept asking to slow down")


def load(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


# ---------------------------------------------------------------- your profile

def engagement(g: dict, flags: dict, ratings: dict) -> float:
    """How much a game says about your taste: positive = you liked it, negative = you dropped it."""
    f = flags.get(g["name"]) or next((flags[a] for a in g.get("aliases", []) if a in flags), None)
    r = ratings.get(g["name"]) or next((ratings[a] for a in g.get("aliases", []) if a in ratings), None)
    w = math.sqrt(g.get("hours") or 0) + 0.15 * (g.get("progress") or 0) ** 0.5
    if g.get("platinum") or g.get("status") == "completed":
        w += 4
    if f and f.get("flag") == "beaten":
        w += 3
    if f and f.get("flag") == "dropped":
        w = -max(2.0, w * 0.5)
    if r:
        w += (r["score"] - 65) / 6          # 95 -> +5, 50 -> -2.5
    return w


def build_profile(games: list[dict], flags: dict, ratings: dict, key: str, feedback: dict | None = None) -> dict:
    played = [g for g in games if (g.get("hours") or 0) > 0 or (g.get("progress") or 0) > 0]
    scored = sorted(((engagement(g, flags, ratings), g) for g in played), key=lambda x: -abs(x[0]))
    genre_w: dict[str, float] = {}
    for w, g in scored:
        for gn in g.get("genres") or []:
            genre_w[gn] = genre_w.get(gn, 0) + w

    # Tags of your most telling games (liked and dropped), fetched once and cached
    cache = load(TAGS_CACHE, {})
    tag_w: dict[str, float] = {}
    tag_names: dict[str, str] = {}
    top = [(w, g) for w, g in scored if g.get("rawg_slug")][:45]
    for w, g in top:
        slug = g["rawg_slug"]
        if slug not in cache:
            try:
                cache[slug] = [[t["slug"], t["name"]] for t in get(f"games/{slug}", key).get("tags", []) if t.get("language") == "eng"]
            except Exception as e:
                print(f"  tags skipped for {g['name']!r}: {e}")
                cache[slug] = []
        for slug_t, name_t in cache[slug]:
            if slug_t not in IGNORED_TAGS:
                tag_w[slug_t] = tag_w.get(slug_t, 0) + w
                tag_names[slug_t] = name_t
    TAGS_CACHE.write_text(json.dumps(cache, sort_keys=True, indent=1))

    # Your 👍 / 👎 on past picks: like a game you enjoyed (+4) or dropped (-4)
    for fb in (feedback or {}).values():
        w = 4.0 if fb.get("feedback") == "up" else -4.0
        for gn in fb.get("genres", []):
            genre_w[gn] = genre_w.get(gn, 0) + w / 2
        for slug_t, name_t in fb.get("tags", []):
            if slug_t not in IGNORED_TAGS:
                tag_w[slug_t] = tag_w.get(slug_t, 0) + w
                tag_names.setdefault(slug_t, name_t)

    lengths = sorted(g["hltb"].get("extra") or g["hltb"].get("main") for w, g in scored
                     if w > 3 and g.get("hltb") and (g["hltb"].get("extra") or g["hltb"].get("main")))
    pref_len = lengths[len(lengths) // 2] if lengths else 25
    norm_max = lambda d: {k: v / max(d.values()) for k, v in d.items() if v > 0} if d and max(d.values()) > 0 else {}
    return {"genres": norm_max(genre_w), "tags": norm_max(tag_w), "tag_names": tag_names, "pref_len": pref_len,
            "liked": [(w, g) for w, g in scored if w > 3], "tag_cache": cache}


# ---------------------------------------------------------------- candidates

def candidates(profile: dict, key: str) -> dict[str, dict]:
    genre_slugs = {gn["name"]: gn["slug"] for gn in get("genres", key, page_size=40).get("results", [])}
    top_genres = [g for g, _ in sorted(profile["genres"].items(), key=lambda x: -x[1])][:4]
    top_tags = [t for t, _ in sorted(profile["tags"].items(), key=lambda x: -x[1])][:5]
    queries = []
    for gn in top_genres:
        if gn in genre_slugs:
            queries.append({"genres": genre_slugs[gn], "ordering": "-metacritic"})
            queries.append({"genres": genre_slugs[gn], "ordering": "-added", "dates": f"{datetime.now().year - 4}-01-01,{datetime.now():%Y-%m-%d}"})
    for tg in top_tags:
        queries.append({"tags": tg, "ordering": "-metacritic"})
    pool: dict[str, dict] = {}
    for q in queries:
        try:
            for x in get("games", key, parent_platforms=2, metacritic="72,100", page_size=40, exclude_additions="true", **q).get("results", []):
                pool.setdefault(x["slug"], x)
        except Exception as e:
            print(f"  candidate query skipped {q}: {e}")
    print(f"  {len(pool)} candidates from {len(queries)} searches")
    return pool


def fit(x: dict, profile: dict) -> tuple[float, list[str], list[str]]:
    genres = [g["name"] for g in x.get("genres") or []]
    tags = [t["slug"] for t in x.get("tags") or [] if t.get("language") == "eng" and t["slug"] not in IGNORED_TAGS]
    g_score = sum(profile["genres"].get(g, 0) for g in genres) / max(1, len(genres)) ** 0.5
    shared = sorted((t for t in tags if t in profile["tags"]), key=lambda t: -profile["tags"][t])
    t_score = sum(profile["tags"][t] for t in shared[:8]) / 4
    return g_score * 0.45 + min(t_score, 1.5) * 0.55, genres, shared


def most_similar(x: dict, profile: dict) -> str | None:
    tags = {t["slug"] for t in x.get("tags") or []} - IGNORED_TAGS
    best, best_s = None, 0.0
    for w, g in profile["liked"][:40]:
        mine = {t for t, _ in profile["tag_cache"].get(g.get("rawg_slug") or "", [])} - IGNORED_TAGS
        if mine and tags:
            s = len(mine & tags) / len(mine | tags) * (1 + w / 20)
            if s > best_s:
                best, best_s = g["name"], s
    return best if best_s > 0.12 else None


def hltb_extra(name: str) -> float | None:
    try:
        from howlongtobeatpy import HowLongToBeat
        res = HowLongToBeat().search(search_name(name), similarity_case_sensitive=False) or []
        best = max(res, key=lambda r: r.similarity, default=None)
        if best and best.similarity >= 0.6:
            return best.main_extra or best.main_story or None
    except Exception as e:
        print(f"  HLTB skipped for {name!r}: {e}")
    return None


# ---------------------------------------------------------------- weekly snapshot (for the Monday digest)

SNAPSHOTS = DOCS / "snapshots.json"


def save_snapshot(games: list[dict], now: datetime) -> None:
    """Hours per game each Monday, so the digest can show what you played last week (PSN only gives totals)."""
    snaps = load(SNAPSHOTS, [])
    day = now.date().isoformat()
    snaps = [s for s in snaps if s["date"] != day]
    snaps.append({"date": day, "hours": {g["name"]: g["hours"] for g in games if g.get("hours")},
                  "trophies": sum(g.get("trophies_earned") or 0 for g in games)})
    SNAPSHOTS.write_text(json.dumps(snaps[-12:], ensure_ascii=False, separators=(",", ":")))


def clean_wishlist(games: list[dict]) -> None:
    """Drop wishlist entries for games now in your library."""
    path = DOCS / "wishlist.json"
    wl = load(path, {})
    owned = {g.get("rawg_slug") for g in games}
    left = {k: v for k, v in wl.items() if k not in owned}
    if len(left) != len(wl):
        path.write_text(json.dumps(left, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        print(f"  wishlist: removed {len(wl) - len(left)} game(s) now in your library")


# ---------------------------------------------------------------- main

def main() -> None:
    key = os.environ.get("RAWG_API_KEY", "").strip()
    if not key:
        raise SystemExit("RAWG_API_KEY is not set")
    data = load(DOCS / "data.json", {})
    games = data.get("games", [])
    flags, ratings = load(DOCS / "flags.json", {}), load(DOCS / "ratings.json", {})
    feedback, wishlist = load(DOCS / "pick_feedback.json", {}), load(DOCS / "wishlist.json", {})
    previous = load(OUT, {})
    now = datetime.now(timezone.utc)
    week = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"

    profile = build_profile(games, flags, ratings, key, feedback)
    save_snapshot(games, now)
    owned_slugs = {g["rawg_slug"] for g in games if g.get("rawg_slug")}
    same = lambda n: norm(re.sub(r"\(\d{4}\)", "", n))   # "God of War (2018)" is the same game as "God of War"
    owned_names = {same(n) for g in games for n in [g["name"], *g.get("aliases", [])]}
    # games recommended in the last 12 weeks (a re-run in the same week may pick again)
    earlier = [h["slug"] for h in previous.get("history", []) if h.get("week") != week]
    recent = set(earlier[: HISTORY_WEEKS * PICKS])

    scored = []
    for slug, x in candidates(profile, key).items():
        if slug in owned_slugs or same(x["name"]) in owned_names or slug in recent or slug in wishlist \
                or feedback.get(slug, {}).get("feedback") == "down":
            continue
        if not {"PlayStation 5", "PlayStation 4"} & {p["platform"]["name"] for p in x.get("platforms") or []}:
            continue
        taste, genres, shared = fit(x, profile)
        quality = ((x.get("metacritic") or 72) - 70) / 25
        scored.append({"x": x, "genres": genres, "shared": shared, "score": taste * 0.7 + quality * 0.3})
    scored.sort(key=lambda c: -c["score"])

    # Length fit for the finalists, then pick 3 with different main genres
    finalists = scored[:10]
    for c in finalists:
        c["length"] = hltb_extra(c["x"]["name"])
        if c["length"]:
            ratio = c["length"] / profile["pref_len"]
            c["score"] -= 0.12 * abs(math.log(max(ratio, 0.05)))   # far from your usual length -> lower
    finalists.sort(key=lambda c: -c["score"])
    picks, used = [], set()
    for c in finalists + scored[10:]:
        main = (c["genres"] or ["?"])[0]
        if main in used and len(finalists) > PICKS:
            continue
        picks.append(c); used.add(main)
        if len(picks) == PICKS:
            break

    out_picks = []
    for c in picks:
        x = c["x"]
        like = most_similar(x, profile)
        tag_txt = ", ".join(profile["tag_names"].get(t, t).lower() for t in c["shared"][:3])
        why = []
        if like:
            why.append(f"Close to {like}, which you enjoyed")
        if tag_txt:
            why.append(f"matches your taste for {tag_txt}")
        elif c["genres"]:
            why.append(f"one of your favourite genres ({c['genres'][0]})")
        if c.get("length"):
            near = 0.6 <= c["length"] / profile["pref_len"] <= 1.6
            why.append(f"about {round(c['length'])} h" + (f", close to your usual {round(profile['pref_len'])} h" if near else ""))
        out_picks.append({
            "slug": x["slug"], "name": x["name"], "image": x.get("background_image"), "metacritic": x.get("metacritic"),
            "released": x.get("released"), "genres": c["genres"][:3],
            "platforms": [p["platform"]["name"].replace("PlayStation ", "PS") for p in x.get("platforms") or []
                          if p["platform"]["name"] in ("PlayStation 5", "PlayStation 4")],
            "length": round(c["length"]) if c.get("length") else None, "why": "; ".join(why) + ".",
            "url": f"https://rawg.io/games/{x['slug']}",
            "tags": [[t["slug"], t["name"]] for t in x.get("tags") or [] if t.get("language") == "eng" and t["slug"] not in IGNORED_TAGS][:10],
        })

    history = [{"slug": p["slug"], "week": week} for p in out_picks] + [h for h in previous.get("history", []) if h.get("week") != week]
    OUT.write_text(json.dumps({
        "week": week, "generated_at": now.isoformat(timespec="seconds"), "picks": out_picks,
        "profile": {"top_genres": [g for g, _ in sorted(profile["genres"].items(), key=lambda x: -x[1])][:4],
                    "top_tags": [profile["tag_names"].get(t, t) for t, _ in sorted(profile["tags"].items(), key=lambda x: -x[1])][:8],
                    "usual_length": round(profile["pref_len"])},
        "history": history[:60],
    }, indent=1, ensure_ascii=False))
    clean_wishlist(games)
    print("::notice::This week's picks: " + " | ".join(f"{p['name']} ({p['metacritic']})" for p in out_picks))


if __name__ == "__main__":
    main()
