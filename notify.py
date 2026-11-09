"""Monday push to your phone through ntfy (https://ntfy.sh): last week, this week's picks, what's coming
out soon, and a warning when the PSN login is about to expire.

Set the repo secret NTFY_TOPIC to the topic you subscribed to in the ntfy app. Without it nothing is sent.
Anyone who knows the topic name can read the messages, so use a long random one.
`python notify.py --test` sends the same message marked as a test.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

DOCS = Path(__file__).parent / "docs"
SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def load(name: str, default):
    p = DOCS / name
    return json.loads(p.read_text()) if p.exists() else default


def fmt_h(h: float) -> str:
    return f"{round(h)} h" if h >= 10 else f"{round(h * 2) / 2:g} h"


def week_bounds(today: date) -> tuple[date, date]:
    """Last full week, Monday to Sunday (the job runs on Monday)."""
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7), this_monday


def build(today: date | None = None) -> tuple[str, str, list[str]]:
    today = today or datetime.now(timezone.utc).date()
    data, recs, snaps = load("data.json", {}), load("recommendations.json", {}), load("snapshots.json", [])
    upcoming, wishlist = load("upcoming.json", {}), load("wishlist.json", {})
    games = data.get("games", [])
    start, end = week_bounds(today)
    ins = data.get("insights") or {}
    trophies = sum(n for d, n in (ins.get("days") or {}).items() if start.isoformat() <= d < end.isoformat())
    plats = [m["game"] for m in ins.get("milestones") or [] if m.get("kind") == "platinum" and start.isoformat() <= m["at"][:10] < end.isoformat()]

    # hours from this Monday's snapshot minus last Monday's, matching renamed games through their old names
    snap_on = lambda d: next((s for s in snaps if d.isoformat() <= s["date"] <= (d + timedelta(days=2)).isoformat()), None)
    a, b = snap_on(start), snap_on(end)
    lines, tags = [], ["video_game"]
    if a and b:
        by_name = {n: g for g in games for n in [g["name"], *g.get("aliases", [])]}
        played = []
        for n, h in b["hours"].items():
            g = by_name.get(n, {})
            before = next((a["hours"][m] for m in [n, *g.get("aliases", [])] if m in a["hours"]), 0)
            last = g.get("last_played")
            if h - before >= 0.2 and (not last or last[:10] >= start.isoformat()):
                played.append((h - before, n))
        played.sort(reverse=True)
        total = sum(d for d, _ in played)
        top = ", ".join(f"{n} ({fmt_h(d)})" for d, n in played[:3])
        lines.append(f"Last week: {fmt_h(total)} played" + (f", {top}" if top else "") + f" · {trophies} troph{'y' if trophies == 1 else 'ies'}")
    else:
        lines.append(f"Last week: {trophies} troph{'y' if trophies == 1 else 'ies'}")
    if plats:
        lines.append("🏆 Platinum: " + ", ".join(plats)); tags.append("trophy")

    # only this week's picks: if the pick step failed, last week's list must not come back as "new"
    this_week = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
    picks = recs.get("picks") or [] if recs.get("week") == this_week else []
    if not picks and recs.get("week") != this_week:
        lines.append("New picks: not ready yet (RAWG was down), they'll come with the next run")
    if picks:
        lines.append("New picks: " + ", ".join(f"{p['name']}" + (f" ({p['metacritic']})" if p.get("metacritic") else "") for p in picks))

    # out in the next 30 days: wishlist first, then upcoming games from your series and studios
    soon_end = (today + timedelta(days=30)).isoformat()
    det = upcoming.get("details") or {}
    soon = []
    for slug, w in wishlist.items():
        rel = (det.get(slug) or {}).get("released") or w.get("released")
        if rel and today.isoformat() <= rel <= soon_end:
            soon.append((rel, w["name"]))
    for x in upcoming.get("upcoming") or []:
        if x.get("released") and today.isoformat() <= x["released"] <= soon_end and x["name"] not in {n for _, n in soon}:
            soon.append((x["released"], x["name"]))
    if soon:
        lines.append("Out soon: " + ", ".join(f"{n} ({datetime.fromisoformat(r).strftime('%-d %b')})" for r, n in sorted(soon)[:4]))

    # wishlist games added by name only that now have details (discover.py, this run)
    found = [w["name"] for w in wishlist.values() if w.get("found") and w["found"] >= (today - timedelta(days=6)).isoformat()]
    if found:
        lines.append("🔎 News on your wishlist: " + ", ".join(found))

    # PS Plus watch: games you only have through PS Plus that leave the catalogue soon, wishlist games that joined it
    plus = load("psplus.json", {}).get("games", [])
    prices = load("prices.json", {})
    key = lambda t: re.sub(r"[^a-z0-9]+", " ", re.sub(r"[™®©]", "", (t or "").lower().replace("&", "and"))).strip()
    in_plus = {key(g["name"]): g for g in plus if not g.get("from")}
    soon_iso, week_ago = (today + timedelta(days=30)).isoformat(), (today - timedelta(days=6)).isoformat()
    leaving = []
    for g in games:
        if not g.get("via_plus") or g.get("status") == "completed" or (g.get("progress") or 0) >= 100:
            continue
        hit = next((in_plus[k] for k in map(key, [g["name"], *g.get("aliases", [])]) if k in in_plus), None)
        if hit and hit.get("until") and today.isoformat() <= hit["until"] <= soon_iso and hit["tier"] != "Essential":
            leaving.append((hit["until"], g["name"]))
    if leaving:
        lines.append("⏳ Leaving PS Plus: " + ", ".join(f"{n} ({datetime.fromisoformat(d).strftime('%-d %b')})" for d, n in sorted(leaving)[:4])); tags.append("hourglass")
    pp = load("psplus.json", {})
    def new_in_plus(slug, w):
        p = prices.get(slug, {})
        if p.get("plus") and p.get("plus_since", "") >= week_ago and p.get("plus_since") != p.get("first_checked"):
            return True
        h = in_plus.get(key(w["name"]))
        return bool(h) and h.get("first_seen", "") >= week_ago and h.get("first_seen") != pp.get("started")
    joined = [w["name"] for slug, w in wishlist.items() if new_in_plus(slug, w)]
    if joined:
        lines.append("🎮 In PS Plus now, no need to buy: " + ", ".join(joined[:4]))

    # wishlist price alerts (Swiss PS Store, checked each Monday)
    hits = []
    for s, w in wishlist.items():
        p = prices.get(s) or {}
        if w.get("alert") is not None and p.get("price") is not None and p["price"] <= w["alert"]:
            extra = " ".join(x for x in [p.get("discount"), f"until {datetime.fromisoformat(p['until']).strftime('%-d %b')}" if p.get("until") else ""] if x)
            hits.append(f"{w['name']} CHF {p['price']:.2f}" + (f" ({extra})" if extra else ""))
    if hits:
        lines.append("💸 Price alert: " + ", ".join(hits)); tags.append("moneybag")

    # backlog tidy-up, every 3 months
    tidy = load("tidy.json", {})
    last = (tidy.get("reviews") or [{}])[-1].get("at")
    if not last or last <= (today - timedelta(days=90)).isoformat():
        kept, old = tidy.get("kept", {}), (today - timedelta(days=730)).isoformat()
        flags = load("flags.json", {})
        n = sum(1 for g in games if g.get("status") == "unplayed" and g.get("owned") and (g.get("acquired") or "9") < old
                and g["name"] not in kept and g["name"] not in flags)
        if n >= 5:
            lines.append(f"🧹 Backlog tidy-up is due: {n} long-untouched games to review (Play next)")

    # Wrapped: the Monday of 14-20 December
    if today.month == 12 and 14 <= today.day <= 20:
        lines.append(f"🎁 Your {today.year} Wrapped is ready")
        tags.append("gift")

    # a memory from this week in past years (memories.json, built by extras.py)
    mem, best = load("memories.json", {}), None
    order = {"platinum": 0, "complete": 1, "rare": 2, "started": 3}
    for i in range(7):
        d = today + timedelta(days=i)
        for x in mem.get(d.strftime("%m-%d"), []):
            if x["y"] < today.year and (best is None or order[x["kind"]] < order[best[1]["kind"]]):
                best = (d, x)
    if best:
        d, x = best
        what = {"platinum": f"platinum in {x['game']}", "complete": f"100% in {x['game']}", "rare": f"{x.get('trophy')} in {x['game']} ({x.get('r')}%)",
                "started": f"you started {x['game']}"}[x["kind"]]
        n = today.year - x['y']
        lines.append(f"📅 {n} year{'s' if n > 1 else ''} ago this {d.strftime('%A')}: {what}")

    login = data.get("login") or {}
    if login.get("error") == "login_expired":
        lines.append("⚠️ PSN login expired: renew it to keep the dashboard updated."); tags.append("warning")
    elif login.get("expires_estimate"):
        days = (datetime.fromisoformat(login["expires_estimate"]).date() - today).days
        if days <= 14:
            lines.append(f"⚠️ PSN login expires in about {max(days, 0)} days: renew it soon."); tags.append("warning")

    title = f"Game Shelf · week of {start.strftime('%-d %b')}"
    return title, "\n".join(lines), tags


def main() -> None:
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        print("NTFY_TOPIC is not set: no push sent.")
        return
    test = "--test" in sys.argv
    title, message, tags = build()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    click = f"https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}/play.html" if "/" in repo else None
    body = {"topic": topic, "title": ("[Test] " if test else "") + title, "message": message, "tags": tags}
    if click:
        body["click"] = click
        if "Wrapped is ready" in message:
            body["actions"] = [{"action": "view", "label": "Open Wrapped", "url": click.replace("play.html", "wrapped.html")}]
    for attempt in range(3):
        r = requests.post(SERVER, json=body, timeout=30)
        if r.status_code != 429:
            break
        time.sleep(15 * (attempt + 1))
    r.raise_for_status()
    print("::notice::Push sent" + (" (test)" if test else "") + ": " + message.replace("\n", " | "))


if __name__ == "__main__":
    main()
