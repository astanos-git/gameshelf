"""Platinum difficulty from trophy-guide sites, for every game in your library.

Sources (each read from its public guide page; none has an official API):
- PowerPyx        www.powerpyx.com            (found through the site's WordPress search)
- PSNProfiles     psnprofiles.com/guide/...   (found through the site's guide search)
- PlayStationTrophies  www.playstationtrophies.org/game/<slug>/guide/
From each guide's summary: difficulty (/10), hours to platinum, missable, online and glitched trophies,
minimum playthroughs.

Results are kept in docs/difficulty.json. A game found on a site is not checked there again; a game not found
is retried after 30 days. A site that blocks us (HTTP 403/429/503) is skipped for the rest of the run and
the game is retried next time. Runs stop after --minutes so the weekly job stays short; the next run carries on.

  python difficulty.py                 # weekly: new games and due retries
  python difficulty.py --minutes 50    # longer backfill
  python difficulty.py --probe "Metaphor: ReFantazio"   # show what each site returns for one game
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus

import requests

from fetch import norm, search_name

ROOT = Path(__file__).parent
OUT = ROOT / "docs" / "difficulty.json"
OVERRIDES = ROOT / "overrides.json"
RETRY_DAYS = 30
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
      "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8", "Accept-Language": "en-GB,en;q=0.9"}


class Blocked(Exception):
    pass


S = requests.Session()
S.headers.update(UA)


def fetch(url: str, delay: float = 1.0) -> requests.Response | None:
    time.sleep(delay)
    try:
        r = S.get(url, timeout=25)
    except requests.RequestException as e:
        print(f"    {url}: {e}")
        return None
    if r.status_code in (403, 429, 503) or "cf-chl" in r.text[:5000] or "Just a moment..." in r.text[:3000]:
        raise Blocked(f"{r.status_code} at {url}")
    return r if r.ok else None


def text_of(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>|</(p|li|div|tr|h\d|td|th|span)>", "\n", page)
    return re.sub(r"[ \t\xa0]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))


NUM = r"(\d+(?:[.,]\d+)?)"


def parse_summary(t: str) -> dict:
    """The roadmap summary most guide writers use, in its common wordings."""
    out = {}
    m = re.search(r"(?i)difficulty[^\n\d]{0,40}?" + NUM + r"\s*/\s*10", t) or re.search(r"(?i)" + NUM + r"\s*/\s*10\s*\n?\s*difficulty", t)
    if m:
        out["difficulty"] = float(m.group(1).replace(",", "."))
    m = re.search(r"(?i)(?:time to (?:platinum|100%)|hours? to platinum|approximate time[^:\n]*|estimated time[^:\n]*)\s*:?[^\n\d]{0,25}?(\d+)\s*(?:[-–~to]+\s*(\d+))?\+?\s*(?:hours|hrs|h)\b", t) \
        or re.search(r"(?i)\b(\d+)\s*(?:[-–]\s*(\d+))?\+?\s*\n?\s*hours\b", t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2)) if m.group(2) else None
        out["hours"] = round((lo + hi) / 2) if hi and hi >= lo else lo
        out["hours_text"] = f"{lo}–{hi}" if hi and hi > lo else str(lo)
    for key, pat in (("missable", r"missable trophies"), ("online", r"online trophies"), ("glitched", r"glitched trophies")):
        m = re.search(r"(?i)" + pat + r"\s*:?\s*(\d+|none|no)\b", t)
        if m:
            out[key] = 0 if m.group(1).lower() in ("none", "no") else int(m.group(1))
    m = re.search(r"(?i)(?:minimum (?:number of )?)?playthroughs?\s*(?:required)?\s*:\s*(\d+)", t) or re.search(r"(?i)\b(\d+)\s*\n?\s*playthroughs?\b", t)
    if m:
        out["playthroughs"] = int(m.group(1))
    return out


def same_game(title: str, names: list[str]) -> bool:
    t = norm(re.sub(r"(?i)\s*(trophy guide.*|achievement guide.*|guide\s*&\s*roadmap.*|-\s*psnprofiles.*)$", "", html.unescape(title)))
    return any(t == norm(n) or SequenceMatcher(None, t, norm(n)).ratio() >= 0.9 for n in names if n)


# ---------------------------------------------------------------- sources

def powerpyx(names: list[str]) -> dict | None:
    for q in dict.fromkeys(search_name(n) for n in names):
        r = fetch(f"https://www.powerpyx.com/wp-json/wp/v2/posts?search={quote_plus(q + ' trophy guide')}&per_page=10&_fields=link,title")
        if not r:
            continue
        try:
            posts = r.json()
        except ValueError:
            continue
        for p in posts:
            title = html.unescape(p.get("title", {}).get("rendered", ""))
            if "trophy guide" in title.lower() and same_game(title, names):
                page = fetch(p["link"])
                if page:
                    found = parse_summary(text_of(page.text))
                    if found.get("difficulty") is not None:
                        return {**found, "url": p["link"]}
    return None


def psnprofiles(names: list[str]) -> dict | None:
    for q in dict.fromkeys(search_name(n) for n in names):
        r = fetch(f"https://psnprofiles.com/search/guides?q={quote_plus(q)}")
        if not r:
            continue
        for path, title in re.findall(r'href="(/guide/\d+-[^"]+)"[^>]*>\s*([^<]{3,120})<', r.text):
            if "trophy guide" in title.lower() and same_game(title, names):
                page = fetch("https://psnprofiles.com" + path)
                if page:
                    found = parse_summary(text_of(page.text))
                    if found.get("difficulty") is not None:
                        return {**found, "url": "https://psnprofiles.com" + path}
    return None


def pst_slugs(names: list[str], rawg: str | None) -> list[str]:
    out = []
    for n in names:
        s = search_name(n).lower().replace("&", "and")
        s = re.sub(r"[^a-z0-9]+", "-", re.sub(r"['’:.]", "", s)).strip("-")
        out.append(s)
    if rawg:
        out.append(re.sub(r"-\d+$", "", rawg))
    return list(dict.fromkeys(x for x in out if x))


def pst(names: list[str], rawg: str | None = None) -> dict | None:
    for slug in pst_slugs(names, rawg)[:3]:
        url = f"https://www.playstationtrophies.org/game/{slug}/guide/"
        page = fetch(url)
        if not page:
            continue
        m = re.search(r"(?is)<title>(.*?)</title>", page.text)
        if m and not same_game(re.sub(r"(?i)\s*(trophy guide|guide).*$", "", m.group(1)), names):
            continue
        found = parse_summary(text_of(page.text))
        if found.get("difficulty") is not None:
            return {**found, "url": url}
    return None


SOURCES = {"powerpyx": lambda g: powerpyx(g["names"]), "psnprofiles": lambda g: psnprofiles(g["names"]), "pst": lambda g: pst(g["names"], g.get("rawg"))}
LABELS = {"powerpyx": "PowerPyx", "psnprofiles": "PSNProfiles", "pst": "PlayStationTrophies"}


# ---------------------------------------------------------------- main

def combine(src: dict) -> dict:
    vals = [v for v in src.values() if v]
    pick = lambda k: [v[k] for v in vals if v.get(k) is not None]
    d, h = pick("difficulty"), pick("hours")
    out = {}
    if d:
        out["difficulty"] = round(sum(d) / len(d), 1)
    if h:
        out["hours"] = sorted(h)[len(h) // 2]
    for k in ("missable", "online", "glitched", "playthroughs"):
        if pick(k):
            out[k] = max(pick(k))      # the most cautious answer
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=20)
    ap.add_argument("--probe")
    ap.add_argument("--raw", action="store_true")
    args = ap.parse_args()

    if args.raw:
        for url in ["https://www.truetrophies.com/game/Metaphor-ReFantazio/",
                    "https://www.truetrophies.com/game/Metaphor-ReFantazio/trophies",
                    "https://www.truetrophies.com/game/Metaphor-ReFantazio/walkthrough",
                    "https://www.truetrophies.com/searchresults.aspx?search=metaphor+refantazio",
                    "https://www.knoef.info/en/?s=metaphor",
                    "https://www.knoef.info/?s=metaphor"]:
            try:
                r = S.get(url, timeout=25)
                t = " ".join(text_of(r.text).split())
                hits = [m.start() for m in re.finditer(r"(?i)estimated|/10|difficulty|time to|hours", t)][:6]
                snip = " || ".join(t[max(0, h - 60):h + 90] for h in hits)
                links = sorted(set(re.findall(r'href="([^"]*(?:metaphor|guide)[^"]*)"', r.text, re.I)))[:8]
                print(f"::notice::RAW {r.status_code} {len(r.text)}b {url} :: {snip[:900]} :: LINKS {links}")
            except Exception as e:
                print(f"::notice::RAW ERR {url} {e}")
            time.sleep(1)
        return

    if args.probe:
        g = {"names": [args.probe], "rawg": None}
        for key, fn in SOURCES.items():
            try:
                print(f"::notice::Probe {key}: {fn(g)}")
            except Blocked as e:
                print(f"::notice::Probe {key}: BLOCKED {e}")
        return

    data = json.loads((ROOT / "docs" / "data.json").read_text())
    store = json.loads(OUT.read_text()) if OUT.exists() else {"games": {}}
    names_override = (json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}).get("guides", {})
    today = date.today()
    order = {"started": 0, "unplayed": 1, "completed": 3}
    games = sorted(data["games"], key=lambda g: (order.get(g.get("status"), 2), -(g.get("hours") or 0)))
    deadline = time.time() + args.minutes * 60
    blocked: dict[str, str] = {}
    stats = {k: {"found": 0, "missing": 0} for k in SOURCES}
    done = 0

    for g in games:
        if time.time() > deadline:
            break
        if not g.get("has_trophies", True) and not g.get("trophies_total"):
            continue
        entry = store["games"].setdefault(g["name"], {"sources": {}, "checked": {}})
        names = [names_override.get(g["name"], g["name"]), *g.get("aliases", [])]
        info = {"names": names, "rawg": g.get("rawg_slug")}
        touched = False
        for key, fn in SOURCES.items():
            if key in blocked or entry["sources"].get(key):
                continue
            last = entry["checked"].get(key)
            if last and (today - date.fromisoformat(last)).days < RETRY_DAYS:
                continue
            try:
                res = fn(info)
            except Blocked as e:
                blocked[key] = str(e)
                print(f"  {LABELS[key]} is blocking us ({e}); skipping it for this run")
                continue
            except Exception as e:      # one bad page shouldn't stop the run
                print(f"  {LABELS[key]} failed for {g['name']!r}: {e}")
                continue
            entry["checked"][key] = today.isoformat()
            entry["sources"][key] = res
            stats[key]["found" if res else "missing"] += 1
            touched = True
        if touched:
            entry["combined"] = combine(entry["sources"])
            done += 1
            if done % 10 == 0:
                OUT.write_text(json.dumps(store, ensure_ascii=False, indent=0, sort_keys=True))

    store["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store["blocked"] = blocked
    OUT.write_text(json.dumps(store, ensure_ascii=False, indent=0, sort_keys=True))
    have = sum(1 for e in store["games"].values() if e.get("combined", {}).get("difficulty") is not None)
    pending = sum(1 for g in games if any(not store["games"].get(g["name"], {}).get("checked", {}).get(k) for k in SOURCES))
    print(f"::notice::Platinum difficulty: checked {done} games this run · "
          + " · ".join(f"{LABELS[k]} {v['found']} found / {v['missing']} not found" + (" (blocked)" if k in blocked else "") for k, v in stats.items())
          + f" · {have} games rated in total · {pending} still to check")


if __name__ == "__main__":
    sys.exit(main())
