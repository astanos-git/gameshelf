"""Extras built from data already in the repo (no network): play sessions, "On this day" memories and a calendar feed.

Runs after every refresh, every Monday, and after you save changes on the dashboard.
Writes:
- docs/sessions.json   play sessions rebuilt from trophy times (all time and per year)
- docs/memories.json   "On this day": platinums, rare trophies and games started, by calendar date
- docs/gameshelf.ics   calendar feed: Up next finish forecasts, release dates (wishlist, coming soon), goals deadline

Sessions are approximate: PSN only gives the time of each trophy. Trophies less than 75 minutes apart count as one
session, which starts ~20 minutes before its first trophy. Sessions without a trophy are invisible.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DOCS = Path(__file__).parent / "docs"
TZ = ZoneInfo("Europe/Zurich")
GAP = timedelta(minutes=75)
LEAD = timedelta(minutes=20)


def load(name: str, default):
    p = DOCS / name
    return json.loads(p.read_text()) if p.exists() else default


def earned_trophies(games: list[dict]) -> list[dict]:
    """Every earned trophy with its time, game, grade and rarity."""
    out = []
    for g in games:
        for tl in g.get("trophy_lists") or []:
            d = load(f"trophies/{tl['id']}.json", None)
            for t in (d or {}).get("trophies", []):
                if t.get("e") and t.get("at"):
                    out.append({"at": datetime.fromisoformat(t["at"]).astimezone(TZ), "game": g["name"], "n": t["n"],
                                "t": t.get("t"), "r": t.get("r")})
    return sorted(out, key=lambda x: x["at"])


# ---------------------------------------------------------------- sessions

def sessions_of(trophies: list[dict]) -> list[dict]:
    out, cur = [], []
    for t in trophies:
        if cur and t["at"] - cur[-1]["at"] > GAP:
            out.append(cur); cur = []
        cur.append(t)
    if cur:
        out.append(cur)
    res = []
    for s in out:
        start = s[0]["at"] - LEAD
        games = Counter(t["game"] for t in s)
        res.append({"start": start, "end": s[-1]["at"], "min": round((s[-1]["at"] - start).total_seconds() / 60),
                    "n": len(s), "games": [g for g, _ in games.most_common()]})
    return res


def summary(ss: list[dict]) -> dict | None:
    if len(ss) < 5:
        return None
    multi = [s["min"] for s in ss if s["n"] >= 2] or [s["min"] for s in ss]
    hours = Counter(s["start"].hour for s in ss)
    longest = max(ss, key=lambda s: s["min"])
    # weekends: Saturday + Sunday of the same week
    wk = defaultdict(lambda: {"min": 0, "games": Counter()})
    for s in ss:
        if s["start"].weekday() >= 5:
            sat = (s["start"] - timedelta(days=s["start"].weekday() - 5)).date()
            wk[sat]["min"] += s["min"]
            for g in s["games"]:
                wk[sat]["games"][g] += 1
    binge = max(wk.items(), key=lambda kv: kv[1]["min"], default=None)
    weeks = max(1, len({(s["start"].isocalendar().year, s["start"].isocalendar().week) for s in ss}))
    per_game = defaultdict(list)
    for s in ss:
        if s["n"] >= 2:                 # a single trophy says nothing about how long you played
            per_game[s["games"][0]].append(s["min"])
    bursts = sorted(((statistics.median(v), g, len(v)) for g, v in per_game.items() if len(v) >= 4 and statistics.median(v) <= 45))[:3]
    marathons = sorted(((statistics.median(v), g, len(v)) for g, v in per_game.items() if len(v) >= 3 and statistics.median(v) >= 120), reverse=True)[:3]
    eve = sum(n for h, n in hours.items() if h >= 20 or h < 2)
    return {
        "n": len(ss), "typical_min": round(statistics.median(multi)), "long_share": round(100 * sum(1 for m in multi if m >= 120) / len(multi)),
        "start_hours": [hours.get(h, 0) for h in range(24)], "evening_share": round(100 * eve / len(ss)),
        "per_active_week": round(len(ss) / weeks, 1),
        "longest": {"date": longest["start"].date().isoformat(), "min": longest["min"], "games": longest["games"][:2]},
        "binge": {"date": binge[0].isoformat(), "min": binge[1]["min"], "games": [g for g, _ in binge[1]["games"].most_common(3)]} if binge else None,
        "bursts": [{"game": g, "median_min": round(m), "sessions": n} for m, g, n in bursts],
        "marathons": [{"game": g, "median_min": round(m), "sessions": n} for m, g, n in marathons],
    }


# ---------------------------------------------------------------- On this day

def memories(games: list[dict], trophies: list[dict], milestones: list[dict]) -> dict:
    by_day: dict[str, list] = defaultdict(list)
    for m in milestones:
        if m.get("kind") == "platinum":
            d = datetime.fromisoformat(m["at"]).astimezone(TZ)
            by_day[d.strftime("%m-%d")].append({"y": d.year, "kind": "platinum", "game": m["game"], "r": m.get("r"), "rank": 0})
    for t in trophies:
        if t["r"] is not None and t["r"] < 10 and t["t"] != "platinum":
            by_day[t["at"].strftime("%m-%d")].append({"y": t["at"].year, "kind": "rare", "game": t["game"], "trophy": t["n"], "r": t["r"], "rank": 1})
    for g in games:                       # 100%: the day of the last trophy in a completed game without a platinum
        if g.get("status") == "completed" and not g.get("platinum") and g.get("last_trophy"):
            d = datetime.fromisoformat(g["last_trophy"]).astimezone(TZ)
            by_day[d.strftime("%m-%d")].append({"y": d.year, "kind": "complete", "game": g["name"], "rank": 0})
    for g in games:
        st = min([x for x in (g.get("first_played"), g.get("first_trophy_at")) if x], default=None)
        if st and ((g.get("hours") or 0) >= 1 or (g.get("trophies_earned") or 0) >= 3):
            d = datetime.fromisoformat(st).astimezone(TZ)
            by_day[d.strftime("%m-%d")].append({"y": d.year, "kind": "started", "game": g["name"], "rank": 2})
    out = {}
    for k, items in by_day.items():
        items.sort(key=lambda x: (x["rank"], x.get("r") or 100))
        seen, keep = set(), []
        for x in items:
            if (x["game"], x["kind"]) not in seen:
                seen.add((x["game"], x["kind"])); keep.append({k2: v for k2, v in x.items() if k2 != "rank"})
        out[k] = keep[:4]
    return dict(sorted(out.items()))


# ---------------------------------------------------------------- calendar feed

def forecast(g: dict, snaps: list[dict], today: date) -> tuple[date, float, float] | None:
    """Finish date at your recent pace (same rule as the dashboard)."""
    beat = (g.get("hltb") or {}).get("extra") or (g.get("hltb") or {}).get("main")
    if not beat or not (g.get("hours") or 0) > 0 or g.get("status") == "completed" or not snaps:
        return None
    names = [g["name"], *g.get("aliases", [])]
    old = next((s for s in reversed(snaps) if (today - date.fromisoformat(s["date"])).days >= 21), snaps[0])
    days = (today - date.fromisoformat(old["date"])).days
    if days < 6:
        return None
    before = next((old["hours"][n] for n in names if n in old["hours"]), 0)
    rate = max(0.0, (g["hours"] - before) / (days / 7))
    left = beat - g["hours"]
    if left <= 0 or rate < 0.5:
        return None
    return today + timedelta(days=round(left / rate * 7)), left, rate


def ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar(games: list[dict], today: date) -> str:
    snaps, queue, flags = load("snapshots.json", []), load("queue.json", []), load("flags.json", {})
    wishlist, upc, goals = load("wishlist.json", {}), load("upcoming.json", {}), load("goals.json", {})
    by_name = {n: g for g in games for n in [g["name"], *g.get("aliases", [])]}
    stamp = "20260101T000000Z"      # fixed on purpose: the file only changes when its events do (no clashes between jobs)
    events = []

    def add(uid: str, day: date, summary: str, desc: str = "", url: str = "") -> None:
        events.append("\r\n".join(filter(None, [
            "BEGIN:VEVENT", f"UID:{uid}@gameshelf", f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}", f"SUMMARY:{ics_escape(summary)}",
            f"DESCRIPTION:{ics_escape(desc)}" if desc else "", f"URL:{url}" if url else "", "TRANSP:TRANSPARENT", "END:VEVENT"])))

    # Up next and other games in progress: when you'd finish at your recent pace
    for name in queue + [g["name"] for g in games if g.get("status") == "started"]:
        g = by_name.get(name)
        if not g or (flags.get(g["name"]) or {}).get("flag") in ("beaten", "dropped"):
            continue
        f = forecast(g, snaps, today)
        if f and f[0] <= today + timedelta(days=365) and not any(f"finish-{g['name']}" in e for e in events):
            add(f"finish-{hashlib.md5(g['name'].encode()).hexdigest()[:12]}", f[0], f"🎮 Finish {g['name']}? (forecast)",
                f"About {round(f[1])} h left at ~{f[2]:.1f} h/week{' · in Up next' if g['name'] in queue else ''}. Moves as you play.")
    # Release dates: wishlist first, then Coming soon
    det = upc.get("details") or {}
    seen = set()
    for slug, w in wishlist.items():
        rel = (det.get(slug) or {}).get("released") or w.get("released")
        if rel and rel >= today.isoformat() and not (det.get(slug) or {}).get("tba"):
            seen.add(slug); add(f"release-{slug}", date.fromisoformat(rel), f"⭐ {w['name']} is out", "On your wishlist.", w.get("url") or "")
    for x in upc.get("upcoming") or []:
        if x["slug"] not in seen and x.get("released") and not x.get("tba") and x["released"] >= today.isoformat():
            add(f"release-{x['slug']}", date.fromisoformat(x["released"]), f"🗓 {x['name']} is out", x.get("reason", ""), x.get("url") or "")
    # Goals for this year: a reminder on 1 December
    g = goals.get(str(today.year))
    if g and today < date(today.year, 12, 1):
        bits = ", ".join(f"{v} {k}" for k, v in g.items() if v)
        add(f"goals-{today.year}", date(today.year, 12, 1), f"🎯 One month left for your {today.year} goals", f"Goals: {bits}. Check Review for progress.")
    return "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Game Shelf//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
                        "X-WR-CALNAME:Game Shelf", "X-WR-TIMEZONE:Europe/Zurich", "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
                        "X-PUBLISHED-TTL:PT12H", *events, "END:VCALENDAR"]) + "\r\n"


def main() -> None:
    data = load("data.json", {})
    games = data.get("games", [])
    if not games:
        return
    today = datetime.now(TZ).date()
    trophies = earned_trophies(games)
    ss = sessions_of(trophies)
    out = {"all": summary(ss)}
    for y in sorted({s["start"].year for s in ss}):
        out[str(y)] = summary([s for s in ss if s["start"].year == y])
    (DOCS / "sessions.json").write_text(json.dumps({k: v for k, v in out.items() if v}, ensure_ascii=False, separators=(",", ":")))
    mem = memories(games, trophies, (data.get("insights") or {}).get("milestones") or [])
    (DOCS / "memories.json").write_text(json.dumps(mem, ensure_ascii=False, separators=(",", ":")))
    ics = calendar(games, today)
    (DOCS / "gameshelf.ics").write_text(ics)
    print(f"::notice::Extras: {len(ss)} sessions · {sum(len(v) for v in mem.values())} memories on {len(mem)} dates · "
          f"{ics.count('BEGIN:VEVENT')} calendar events")


if __name__ == "__main__":
    main()
