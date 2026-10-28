"""Coming soon + game details for the Discover tab. Runs every Monday after recommend.py.

Needs RAWG_API_KEY. Writes docs/upcoming.json:
- "upcoming": unreleased PS4/PS5 games in categories (a game can be in several):
    series  – next games in the series you played most
    studio  – from the studios you spent most hours with (at least two of their games)
    taste   – matching your taste profile (genres and RAWG tags, same profile as the weekly picks)
    indie   – most-awaited indie games
    big     – most-awaited big releases (PS5, not indie)
    soon    – anything above out in the next 60 days (computed on the page, not stored)
  "Most-awaited" = how many RAWG users added the game. Games you own, dismissed (👎) or adult-only are left out.
- "details": a short description, studios and release date for this week's picks, your wishlist and the
  upcoming games, shown when you tap them on Play next → Discover.
Details of released games are cached in rawg_details.json; unreleased ones are refreshed every week
(release dates move).
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fetch import norm
import math

from recommend import IGNORED_TAGS, build_profile, engagement, fit, get, load

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
OUT = DOCS / "upcoming.json"
CACHE = ROOT / "rawg_details.json"
PS = {"PlayStation 5": "PS5", "PlayStation 4": "PS4"}
PER_CATEGORY = 8
ADULT = {"nsfw", "sexual-content", "hentai", "nudity", "erotic", "adult"}


def short_description(text: str, limit: int = 420) -> str:
    """First paragraph or two, cut at a sentence end."""
    text = re.sub(r"#+\s*\w[\w ]{0,30}?(?=[A-Z\n]|$)", "\n", text or "")   # RAWG headings like "###Plot"
    text = re.sub(r"\s+\n", "\n", text.strip())
    paras = [p.strip() for p in re.split(r"\n+", text) if p.strip() and not re.match(r"^(english|español|deutsch|français)\b", p.strip(), re.I)]
    out = ""
    for p in paras:
        if len(out) + len(p) > limit and out:
            break
        out = (out + " " + p).strip()
    if len(out) > limit:
        cut = out[:limit]
        out = cut[: cut.rfind(". ") + 1] if ". " in cut else cut.rsplit(" ", 1)[0] + "…"
    return out


def unreleased(x: dict, today: str) -> bool:
    return bool(x.get("tba")) or (x.get("released") or "") > today


def details(slug: str, key: str, cache: dict, today: str) -> dict | None:
    hit = cache.get(slug)
    if hit and not unreleased(hit, today):
        return hit
    try:
        x = get(f"games/{slug}", key)
    except Exception as e:
        print(f"  details skipped for {slug}: {e}")
        return hit
    cache[slug] = {
        "name": x.get("name"), "released": x.get("released"), "tba": bool(x.get("tba")),
        "description": short_description(x.get("description_raw") or ""),
        "developers": [d["name"] for d in x.get("developers") or []][:3],
        "developer_ids": [[d["id"], d["name"]] for d in x.get("developers") or []][:3],
        "publishers": [p["name"] for p in x.get("publishers") or []][:3],
        "website": x.get("website") or None, "metacritic": x.get("metacritic"),
        "esrb": (x.get("esrb_rating") or {}).get("name"),
    }
    return cache[slug]


def summary(x: dict) -> dict:
    return {"slug": x["slug"], "name": x["name"], "image": x.get("background_image"), "released": x.get("released"),
            "tba": bool(x.get("tba")), "metacritic": x.get("metacritic"), "genres": [g["name"] for g in x.get("genres") or []][:3],
            "platforms": [PS[p["platform"]["name"]] for p in x.get("platforms") or [] if p["platform"]["name"] in PS],
            "url": f"https://rawg.io/games/{x['slug']}"}


def on_playstation(x: dict) -> bool:
    plats = {p["platform"]["name"] for p in x.get("platforms") or []}
    parents = {p["platform"]["name"] for p in x.get("parent_platforms") or []}
    return bool(plats & set(PS)) or (not plats and "PlayStation" in parents)


def main() -> None:
    key = os.environ.get("RAWG_API_KEY", "").strip()
    if not key:
        raise SystemExit("RAWG_API_KEY is not set")
    data = load(DOCS / "data.json", {})
    games = data.get("games", [])
    flags, ratings = load(DOCS / "flags.json", {}), load(DOCS / "ratings.json", {})
    recs, wishlist = load(DOCS / "recommendations.json", {}), load(DOCS / "wishlist.json", {})
    cache = load(CACHE, {})
    today = date.today().isoformat()
    horizon = (date.today() + timedelta(days=3 * 365)).isoformat()

    owned_slugs = {g["rawg_slug"] for g in games if g.get("rawg_slug")}
    owned_names = {norm(n) for g in games for n in [g["name"], *g.get("aliases", [])]}
    mine = lambda x: x["slug"] in owned_slugs or norm(x["name"]) in owned_names
    found: dict[str, dict] = {}
    log: list[str] = []
    feedback = load(DOCS / "pick_feedback.json", {})
    skip = lambda x: mine(x) or feedback.get(x["slug"], {}).get("feedback") == "down" \
        or ADULT & {t.get("slug") for t in x.get("tags") or []} or x.get("esrb_rating", {}) and (x.get("esrb_rating") or {}).get("slug") == "adults-only"

    def add(x: dict, cat: str, reason: str) -> bool:
        if skip(x) or not unreleased(x, today) or not on_playstation(x) or (x.get("released") or "") > horizon:
            return False
        e = found.setdefault(x["slug"], {**summary(x), "cats": [], "reasons": {}, "added": x.get("added") or 0})
        if cat not in e["cats"]:
            e["cats"].append(cat); e["reasons"][cat] = reason
        return True

    # 1. Series: the games you engaged with most, one per series
    ranked = sorted((g for g in games if g.get("rawg_slug")), key=lambda g: -engagement(g, flags, ratings))
    seen_series, n_series = set(), 0
    for g in ranked:
        if n_series >= 12:
            break
        label = (g.get("series") or [None])[0]
        if label and label in seen_series:
            continue
        seen_series.add(label or g["name"]); n_series += 1
        try:
            res = get(f"games/{g['rawg_slug']}/game-series", key, page_size=40).get("results", [])
        except Exception as e:
            print(f"  series skipped for {g['name']!r}: {e}")
            continue
        log.append(f"{g['name']}: {len(res)} in series, {sum(1 for x in res if unreleased(x, today))} unreleased")
        n_added = 0
        for x in res:
            if n_added < 2 and add(x, "series", f"Series: {label}" if label else f"Follows {g['name']}"):
                n_added += 1

    # 2. Studios: where you spent the most hours, at least two of their games played
    by_dev: dict[str, list] = {}
    for g in games:
        if (g.get("hours") or 0) > 0:
            for d in g.get("developers") or []:
                by_dev.setdefault(d, []).append(g)
    studios = sorted(((sum(x.get("hours") or 0 for x in gs), d, gs) for d, gs in by_dev.items() if len(gs) >= 2), reverse=True)[:5]
    for hours, dev, gs in studios:
        dev_id = None
        for g in gs:
            if not g.get("rawg_slug"):
                continue
            det = details(g["rawg_slug"], key, cache, today) or {}
            dev_id = next((i for i, n in det.get("developer_ids", []) if norm(n) == norm(dev) or norm(dev) in norm(n) or norm(n) in norm(dev)), None)
            if dev_id:
                break
        if not dev_id:
            log.append(f"studio {dev}: not found on RAWG")
            continue
        res = []
        for order in ("-released", "-added"):          # dated releases, then recently announced (often no date yet)
            try:
                res += get("games", key, developers=dev_id, parent_platforms=2, ordering=order, page_size=40).get("results", [])
            except Exception as e:
                print(f"  studio search skipped for {dev}: {e}")
        res = [x for x in {x["slug"]: x for x in res}.values() if unreleased(x, today) and (x.get("released") or "") <= horizon]
        log.append(f"studio {dev} (#{dev_id}): {len(res)} upcoming, {sum(1 for x in res if on_playstation(x))} on PlayStation")
        for x in res:
            add(x, "studio", f"Studio: {dev}")

    # 3-5. Taste, indie, big releases: announced games with a date in the next 18 months
    window = f"{today},{(date.today() + timedelta(days=548)).isoformat()}"
    def search(**q) -> list[dict]:
        try:
            return get("games", key, dates=window, parent_platforms=2, ordering="-added", page_size=40, **q).get("results", [])
        except Exception as e:
            print(f"  search skipped {q}: {e}")
            return []

    profile = build_profile(games, flags, ratings, key, feedback)
    pool: dict[str, dict] = {}
    genre_slugs = {g["name"]: g["slug"] for g in get("genres", key, page_size=40).get("results", [])}
    for gn, _ in sorted(profile["genres"].items(), key=lambda x: -x[1])[:3]:
        if gn in genre_slugs:
            pool.update({x["slug"]: x for x in search(genres=genre_slugs[gn])})
    for tg, _ in sorted(profile["tags"].items(), key=lambda x: -x[1])[:4]:
        pool.update({x["slug"]: x for x in search(tags=tg)})
    scored = []
    for x in pool.values():
        taste, genres_x, shared = fit(x, profile)
        if taste >= 0.45 and (x.get("added") or 0) >= 10:
            scored.append((taste * (1 + math.log10(1 + (x.get("added") or 0)) / 4), x, shared))
    n = 0
    for _, x, shared in sorted(scored, key=lambda c: -c[0]):
        why = ", ".join(profile["tag_names"].get(t, t).lower() for t in shared[:2]) or ", ".join(g["name"] for g in (x.get("genres") or [])[:2]).lower()
        if n < PER_CATEGORY and add(x, "taste", f"Your taste: {why}"):
            n += 1
    log.append(f"taste: {len(pool)} candidates, {len(scored)} good fits")

    n = 0
    for x in search(genres="indie"):
        if n < PER_CATEGORY and (x.get("added") or 0) >= 3 and add(x, "indie", "Indie, much awaited"):
            n += 1
    n = 0
    for x in search(platforms=187):
        if n < PER_CATEGORY and "Indie" not in {g["name"] for g in x.get("genres") or []} and (x.get("added") or 0) >= 30 \
                and add(x, "big", "Big release, much awaited"):
            n += 1
    log.append("per category: " + ", ".join(f"{c} {sum(1 for x in found.values() if c in x['cats'])}" for c in ("series", "studio", "taste", "indie", "big")))

    # one reason to show: the most personal category first
    order = ["series", "studio", "taste", "big", "indie"]
    for x in found.values():
        x["cats"].sort(key=order.index)
        x["reason"] = x["reasons"][x["cats"][0]]
        del x["reasons"]
    upcoming = sorted(found.values(), key=lambda x: (bool(x["tba"] or not x["released"]), x["released"] or "9999", -x["added"]))

    # 3. Details for everything shown on Discover
    det_out = {}
    for slug in {*(p["slug"] for p in recs.get("picks", [])), *wishlist, *(x["slug"] for x in upcoming)}:
        d = details(slug, key, cache, today)
        if d:
            det_out[slug] = {k: v for k, v in d.items() if k != "developer_ids"}

    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True, ensure_ascii=False))
    OUT.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "upcoming": upcoming, "details": det_out}, indent=1, ensure_ascii=False))
    print("::notice::Coming soon details: " + " | ".join(log))
    print(f"::notice::Coming soon: {len(upcoming)} games" + (": " + ", ".join(f"{x['name']} ({x['released'] or 'TBA'})" for x in upcoming[:5]) if upcoming else ""))


if __name__ == "__main__":
    main()
