"""Monday push to your phone through ntfy (https://ntfy.sh): last week, this week's picks, what's coming
out soon, and a warning when the PSN login is about to expire.

Set the repo secret NTFY_TOPIC to the topic you subscribed to in the ntfy app. Without it nothing is sent.
Anyone who knows the topic name can read the messages, so use a long random one.
`python notify.py --test` sends the same message marked as a test.
"""
from __future__ import annotations

import json
import os
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

    picks = recs.get("picks") or []
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
        lines.append(f"📅 {today.year - x['y']} years ago this {d.strftime('%A')}: {what}")

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
    for attempt in range(3):
        r = requests.post(SERVER, json=body, timeout=30)
        if r.status_code != 429:
            break
        time.sleep(15 * (attempt + 1))
    r.raise_for_status()
    print("::notice::Push sent" + (" (test)" if test else "") + ": " + message.replace("\n", " | "))


if __name__ == "__main__":
    main()
