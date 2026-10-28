"""Platinum difficulty from trophy-guide sites, for every game in your library.

Sources (public pages; neither has an official API):
- PowerPyx      www.powerpyx.com: the roadmap at the top of each trophy guide (difficulty /10, time to platinum,
                missable / online / glitched trophies, minimum playthroughs).
- TrueTrophies  www.truetrophies.com: community completion time and the number of missable trophies.
PSNProfiles and PlayStationTrophies.org were tried too, but they block GitHub's servers (HTTP 403).

Results are kept in docs/difficulty.json. A game found on a site is not checked there again; a game not found
is retried after 30 days. A site that blocks us is skipped for the rest of the run and retried next time.
Runs stop after --minutes so the weekly job stays short; the next run carries on.

  python difficulty.py                 # weekly: new games and due retries
  python difficulty.py --minutes 55    # longer backfill
  python difficulty.py --probe "Metaphor: ReFantazio"   # what each site returns for one game
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
    return re.sub(r"[ \t\xa0]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)).replace("\xa0", " "))


NUM = r"(\d+(?:[.,]\d+)?)"


DASH = r"\s*(?:[-–—‑−~]|to)\s*"


def roadmap(t: str) -> str:
    """Just the roadmap summary: from its first label to ~1,500 characters later. Menus, related-guide blocks and
    comments elsewhere on the page also mention difficulties and hours, and must not be read."""
    m = re.search(r"(?i)estimated (?:trophy |platinum )?difficulty", t) or re.search(r"(?i)(?:trophy|platinum) difficulty\s*:|difficulty\s*:\s*\d", t)
    return t[max(0, m.start() - 300): m.start() + 3000] if m else t


def parse_summary(t: str) -> dict:
    """The roadmap summary most guide writers use, in its common wordings. Labelled lines first."""
    t = roadmap(t)
    out = {}
    nxt = r"(?=approximate|estimated time|offline trophies|online trophies|number of missable|missable trophies|glitched|does difficulty|hardest trophy|minimum playthrough|$)"
    mid = lambda a, b: (float(a.replace(",", ".")) + float((b or a).replace(",", "."))) / 2
    # difficulty: the block after its label. Ranges are averaged ("5-6/10", "4.5/10 – 6/10"); when the guide lists
    # several routes ("1/10 on Story Mode, 3/10 on Adventure Mode"), the first one: the route the guide recommends.
    m = re.search(r"(?is)(?:estimated (?:trophy |platinum )?difficulty|(?:trophy|platinum) difficulty)(.{0,600}?)" + nxt, t)
    first = re.search(NUM + r"(?:\s*/\s*10)?(?:" + DASH + NUM + r")?\s*/\s*10", m.group(1)) if m else None
    vals = [mid(first.group(1), first.group(2))] if first else []
    if not vals:
        m2 = re.search(r"(?i)difficulty[^\n\d]{0,20}?" + NUM + r"(?:" + DASH + NUM + r")?\s*/\s*10", t) \
            or re.search(r"(?i)" + NUM + r"(?:" + DASH + NUM + r")?\s*/\s*10\s*\n?\s*difficulty", t)
        vals = [mid(m2.group(1), m2.group(2))] if m2 else []
    if vals:
        out["difficulty"] = round(vals[0], 1)
    # time: same idea, the first route listed ("40-50 hours on Story / 50-60 hours on Balance" -> 40-50)
    m = re.search(r"(?is)(?:time to (?:platinum|100%)|hours? to platinum|approximate (?:amount of )?time|estimated time)(.{0,400}?)" + nxt.replace("approximate|estimated time|", "offline trophies|"), t)
    hrs = re.findall(r"(\d+)(?:" + DASH + r"(\d+))?\+?\s*(?:hours|hrs)\b", m.group(1), re.I) if m else []   # not "8-12h" sub-parts
    if m and not hrs:
        hrs = re.findall(r"(\d+)(?:" + DASH + r"(\d+))?\+?\s*h\b", m.group(1), re.I)[:1]
    if not hrs:
        m2 = re.search(r"(?i)\b(\d+)(?:" + DASH + r"(\d+))?\+?\s*\n?\s*hours\b", t)
        hrs = [(m2.group(1), m2.group(2))] if m2 else []
    if hrs:
        lo, hi = hrs[0]
        lo, hi = int(lo), int(hi) if hi else None
        out["hours"] = round((lo + hi) / 2) if hi and hi >= lo else lo
        out["hours_text"] = f"{lo}–{hi}" if hi and hi > lo else str(lo)
    for key, pat in (("missable", r"missable trophies"), ("online", r"online trophies"), ("glitched", r"glitched trophies")):
        m = re.search(r"(?i)" + pat + r"\s*:?\s*(\d+|none|no)\b", t)
        if m:
            out[key] = 0 if m.group(1).lower() in ("none", "no") else int(m.group(1))
    m = re.search(r"(?i)(?:minimum (?:number of )?)?playthroughs?\s*(?:required)?\s*:\s*(\d+)", t) or re.search(r"(?i)\b(\d+)\s*\n?\s*(?:full )?playthroughs?\b", t)
    if m:
        out["playthroughs"] = int(m.group(1))
    return out


def match_score(title: str, names: list[str]) -> float:
    """1 = same title; 0.9+ = near-identical; 0.8 = the guide's title is the start of ours
    ("The Witcher 3: Wild Hunt" for "... — Remastered"); 0 = different game."""
    t = norm(re.sub(r"(?i)\s*(trophy guide.*|achievement guide.*|guide\s*&\s*roadmap.*|trophy roadmap.*|-\s*psnprofiles.*)$", "", html.unescape(title).replace("\xa0", " ")))
    best = 0.0
    for n in names:
        for v in {norm(n), norm(search_name(n))}:
            if not v or not t:
                continue
            r = 1.0 if t == v else SequenceMatcher(None, t, v).ratio()
            if r < 0.9 and len(t) >= 8 and v.startswith(t + " ") and re.search(r"(?i)remaster|edition|director|complete|definitive|goty|ps[45]", v[len(t):]):
                r = 0.8
            best = max(best, r if r >= 0.8 else 0.0)
    return best


def same_game(title: str, names: list[str]) -> bool:
    return match_score(title, names) >= 0.9


# ---------------------------------------------------------------- sources

def slugify(name: str) -> str:
    s = search_name(name).lower().replace("&", " ").replace(":", " ")
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['’.!,]", "", s)).strip("-")


ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8"}


def guide_urls(names: list[str]) -> list[str]:
    """Likely PowerPyx addresses: the name as is, with roman/arabic numbers swapped, without "remastered",
    then the older "-trophy-guide/" form."""
    slugs = []
    for n in names:
        base = slugify(n)
        slugs.append(base)
        slugs.append("-".join(ROMAN.get(w, w) for w in base.split("-")))
        slugs.append("-".join({v: k for k, v in ROMAN.items()}.get(w, w) for w in base.split("-")))
        slugs.append(re.sub(r"-(remastered|remaster|definitive-edition|complete-edition|game-of-the-year-edition|goty-edition|directors-cut)$", "", base))
    slugs = list(dict.fromkeys(x for x in slugs if x))[:4]
    return [f"https://www.powerpyx.com/{x}-trophy-guide-roadmap/" for x in slugs] + [f"https://www.powerpyx.com/{x}-trophy-guide/" for x in slugs[:2]]


def powerpyx(names: list[str]) -> dict | None:
    # 1. the usual address of a guide; 2. the site's search (posts come back with their text)
    for url in guide_urls(names):
        page = fetch(url, delay=0.6)
        if page:
            found = parse_summary(text_of(page.text))
            if found.get("difficulty") is not None:
                return {**found, "url": url}
    # search "<game> trophy guide" (big games have dozens of collectible guides that would crowd it out otherwise)
    cands = []
    for q in dict.fromkeys(search_name(n) for n in names):
        words = re.sub(r"[:\-–—]+", " ", q)
        r = fetch(f"https://www.powerpyx.com/wp-json/wp/v2/posts?search={quote_plus(words + ' trophy guide')}&orderby=relevance&per_page=20")
        try:
            posts = r.json() if r else []
        except ValueError:
            posts = []
        for p in posts if isinstance(posts, list) else []:
            title = html.unescape(p.get("title", {}).get("rendered", "")).replace("\xa0", " ")
            score = match_score(title, names) if re.search(r"(?i)trophy (guide|roadmap)", title) else 0
            if score:
                cands.append((score, p))
        if any(sc == 1.0 for sc, _ in cands):
            break
    for _, p in sorted(cands, key=lambda c: -c[0]):          # the closest title first
        found = parse_summary(text_of(p.get("content", {}).get("rendered", "")))
        if found.get("difficulty") is not None:
            return {**found, "url": p.get("link")}
    return None


def truetrophies(names: list[str], platforms: list[str]) -> dict | None:
    for q in dict.fromkeys(search_name(n) for n in names):
        r = fetch(f"https://www.truetrophies.com/searchresults.aspx?search={quote_plus(q)}")
        if not r:
            continue
        games = list(dict.fromkeys(re.findall(r'href="/game/([^/"]+)/trophies"', r.text)))
        cands = []
        for g in games:
            base, plat = re.match(r"(.*?)(?:-(PS[345]|PS-Vita))?$", g).groups()
            if same_game(base.replace("-", " "), names):
                cands.append((0 if (plat or "PS5") in platforms or not plat else 1, g))
        for _, g in sorted(cands)[:1]:
            url = f"https://www.truetrophies.com/game/{g}/trophies"
            page = fetch(url)
            if not page:
                continue
            t = " ".join(text_of(page.text).split())
            out = {}
            m = re.search(r"(?i)Completion est\s*(\d+)\s*(?:-\s*(\d+))?\+?\s*hours", t)
            if m:
                lo, hi = int(m.group(1)), int(m.group(2)) if m.group(2) else None
                out["hours"] = round((lo + hi) / 2) if hi else lo
                out["hours_text"] = f"{lo}–{hi}" if hi and hi > lo else str(lo)
            m = re.search(r"\bMissable (\d+)\b", t)
            out["missable"] = int(m.group(1)) if m else 0
            m = re.search(r"\bOnline (?:Game )?Mode (\d+)\b", t)
            if m:
                out["online"] = int(m.group(1))
            if "Multiple Playthroughs Req" in t:
                out["several_playthroughs"] = True
            if out.get("hours"):
                return {**out, "url": url}
    return None


def from_url(url: str) -> dict | None:
    """A guide you picked yourself ("Wrong info?" on the dashboard): read its summary, whatever the site."""
    page = fetch(url)
    if not page:
        return None
    found = parse_summary(text_of(page.text))
    return {**found, "url": url} if found.get("difficulty") is not None or found.get("hours") else None


SOURCES = {"powerpyx": lambda g: from_url(g["guide"]) if g.get("guide") else None if g.get("no_guide") else powerpyx(g["names"]), "truetrophies": lambda g: truetrophies(g["names"], g.get("platforms", []))}
LABELS = {"powerpyx": "PowerPyx", "truetrophies": "TrueTrophies"}


# ---------------------------------------------------------------- main

def combine(src: dict) -> dict:
    vals = [v for v in src.values() if v]
    pick = lambda k: [v[k] for v in vals if v.get(k) is not None]
    d, h = pick("difficulty"), pick("hours")
    out = {}
    if d:
        out["difficulty"] = round(sum(d) / len(d), 1)
    if h:
        out["hours"] = round(sum(h) / len(h))          # average of the guides' estimates
    for k in ("missable", "online", "glitched", "playthroughs"):        # the most cautious answer
        if pick(k):
            out[k] = max(pick(k))
    return out


def guide_info(g: dict, guides: dict) -> dict:
    """What to look up for a game: its names, or the guide you chose ("guides" in overrides.json: URL, or null = no guide)."""
    o = guides.get(g["name"], "")
    return {"names": [g["name"], *g.get("aliases", [])], "platforms": g.get("platforms", []),
            "guide": o if isinstance(o, str) and o.startswith("http") else None, "no_guide": g["name"] in guides and o is None}


def check_one(name: str) -> str:
    """Look one game up now (after a fix from the dashboard) and save it. Returns a short summary."""
    data = json.loads((ROOT / "docs" / "data.json").read_text())
    g = next(x for x in data["games"] if x["name"] == name or name in x.get("aliases", []))
    store = json.loads(OUT.read_text()) if OUT.exists() else {"games": {}}
    guides = (json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}).get("guides", {})
    info, today = guide_info(g, guides), date.today().isoformat()
    entry = store["games"][g["name"]] = {"sources": {}, "checked": {}}
    for key, fn in SOURCES.items():
        try:
            entry["sources"][key] = fn(info)
        except Blocked:
            continue
        entry["checked"][key] = today
    entry["combined"] = combine(entry["sources"])
    OUT.write_text(json.dumps(store, ensure_ascii=False, indent=0, sort_keys=True))
    c = entry["combined"]
    return " · ".join(x for x in [f"{c['difficulty']}/10" if c.get("difficulty") is not None else "", f"~{c['hours']} h" if c.get("hours") else "",
                                  f"{c['missable']} missable" if c.get("missable") else ""] if x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=20)
    ap.add_argument("--probe")
    ap.add_argument("--reparse", default="", help="source(s) whose saved guide pages to read again, e.g. powerpyx")
    ap.add_argument("--retry", default="", help="source(s) whose 'not found' results to check again now, e.g. powerpyx")
    args = ap.parse_args()

    if args.probe:
        g = {"names": [args.probe.strip()], "platforms": ["PS5", "PS4"]}
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
    if args.reparse:                                          # after a parsing fix: read every saved guide page again
        n = 0
        for e in store["games"].values():
            for src, v in (e.get("sources") or {}).items():
                if v and v.get("url") and src in args.reparse.split(","):
                    try:
                        page = fetch(v["url"], delay=0.5)
                    except Blocked:
                        break
                    found = parse_summary(text_of(page.text)) if page else {}
                    if found.get("difficulty") is not None or found.get("hours"):
                        e["sources"][src] = {**found, "url": v["url"]}; n += 1
            if e.get("sources"):
                e["combined"] = combine(e["sources"])
        print(f"::notice::Re-read {n} saved guide pages")
    for src in filter(None, args.retry.split(",")):          # after a matching fix: forget earlier misses
        for e in store["games"].values():
            if not e.get("sources", {}).get(src):
                e.get("checked", {}).pop(src, None)
    blocked: dict[str, str] = {}
    stats = {k: {"found": 0, "missing": 0} for k in SOURCES}
    done = 0

    for g in games:
        if time.time() > deadline:
            break
        if not g.get("trophies_total") and (g.get("hours") or 0) > 0 and g.get("status") != "unplayed":
            continue        # played but no trophies at all: an app (Netflix, Spotify…), not a game
        entry = store["games"].setdefault(g["name"], {"sources": {}, "checked": {}})
        info = guide_info(g, names_override)
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
