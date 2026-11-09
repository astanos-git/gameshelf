"""Weekly: the PS Plus catalogue and Swiss PS Store prices for your wishlist.

- docs/psplus.json: every game in PS Plus (Essential / Extra / Premium) with the date it leaves ("until")
  or arrives ("from"), from Push Square's always-updated list. "first_seen" tells what's new this week.
- docs/prices.json: for each wishlist game, its PS Store price in Switzerland (CHF), discount and end date,
  whether it's included with PS Plus, and the lowest price seen so far.
- store_ids.json (cache): wishlist game -> PS Store concept id, found through playstation.com's game pages.

Nothing is bought or changed on your account: these are public store pages.
`python store.py --plus-only` or `--prices-only` runs one half.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
LOCALE = "fr-ch"        # Swiss store (prices in CHF); playstation.com uses the same locale codes
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
      "Accept-Language": "fr-CH,fr;q=0.9,en;q=0.8"}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def load(name: str, default):
    p = DOCS / name
    return json.loads(p.read_text()) if p.exists() else default


def save(name: str, value) -> None:
    (DOCS / name).write_text(json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def get(url: str, **kw) -> requests.Response | None:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=30, **kw)
            if r.status_code in (429,) or r.status_code >= 500:
                raise requests.HTTPError(str(r.status_code))
            return r
        except (requests.RequestException,) as e:
            if attempt == 2:
                print(f"  {url}: {e}")
                return None
            time.sleep(5 * (attempt + 1))


def norm(t: str) -> str:
    t = (t or "").lower().replace("&", "and")
    t = re.sub(r"[™®©]", "", t)
    t = re.sub(r"\b(ps4|ps5|ps vr2|playstation ?[45]|edition|remastered|director'?s cut|the)\b", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


# ---------- PS Plus ----------
def parse_date(text: str, today: date) -> str | None:
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*\.?(?:\s+(\d{4}))?", text)
    if not m or m.group(2).lower()[:3] not in MONTHS:
        return None
    y = int(m.group(3)) if m.group(3) else today.year
    d = date(y, MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
    if not m.group(3) and d < today - timedelta(days=60):
        d = d.replace(year=y + 1)
    return d.isoformat()


def psplus(today: date) -> dict | None:
    rows = []
    for status in ("all", "soon"):
        r = get(f"https://www.pushsquare.com/guides/all-ps-plus-games-available-now?status={status}")
        if not r or r.status_code != 200:
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S):
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            cells = [c for c in cells if c]
            if len(cells) < 3:
                continue
            name, avail = cells[0], cells[-1]
            tier = next((c for c in cells if c.startswith("PS+")), "")
            systems = sorted(set(re.findall(r"\bPS[1-5]\b|PS VR2|PSP", " ".join(cells[1:-1]))))
            if not tier:
                continue
            rows.append({"name": name, "tier": tier.replace("PS+ ", ""), "systems": systems,
                         "until": parse_date(avail, today) if avail.lower().startswith("until") else None,
                         "from": parse_date(avail, today) if avail.lower().startswith(("from", "coming")) or status == "soon" and avail.lower() != "now" else None})
    if len(rows) < 100:          # the page changed or didn't load: keep last week's list
        print(f"  PS Plus: only {len(rows)} rows read, keeping the previous list")
        return None
    old = {g["name"]: g for g in load("psplus.json", {}).get("games", [])}
    games = {}
    for g in rows:
        prev = games.get(g["name"])
        if prev and (prev.get("from") and not g.get("from")):
            continue                                     # "available now" beats "coming soon"
        g["first_seen"] = (old.get(g["name"]) or {}).get("first_seen") or today.isoformat()
        games[g["name"]] = g
    out = {"checked": today.isoformat(), "started": load("psplus.json", {}).get("started") or today.isoformat(), "games": sorted(games.values(), key=lambda g: g["name"].lower())}
    leaving = sum(1 for g in out["games"] if g["until"])
    print(f"::notice::PS Plus: {len(out['games'])} games in the catalogue lists, {leaving} with a leaving date")
    return out


# ---------- prices ----------
def slugs_for(name: str) -> list[str]:
    base = name.lower().replace("&", "and").replace("’", "'")
    base = re.sub(r"[™®©]", "", base)
    variants = [base, re.sub(r"\s*[:\-–].*$", "", base), base.replace("marvel's", "marvels")]
    out = []
    for v in variants:
        s = re.sub(r"'", "", v)
        s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
        if s and s not in out:
            out.append(s)
    return out


def concept_for(name: str) -> tuple[str | None, str | None]:
    """playstation.com/<locale>/games/<slug>/ pages carry the store's concept id."""
    for slug in slugs_for(name):
        r = get(f"https://www.playstation.com/{LOCALE}/games/{slug}/")
        if r is None or r.status_code != 200:
            continue
        ids = re.findall(r"store\.playstation\.com/[a-z-]+/concept/(\d{4,9})", r.text) or re.findall(r'"conceptId"\s*:\s*"?(\d{4,9})', r.text)
        if ids:
            return ids[0], slug
        time.sleep(0.5)
    return None, None


def money(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d[\d'’  ]*(?:[.,]\d{1,2})?)", text)
    return float(re.sub(r"['’  ]", "", m.group(1)).replace(",", ".")) if m else None


def price_blocks(html: str) -> list[dict]:
    """The page embeds the store's price objects ("basePrice", "discountedPrice", ...): pull each one out."""
    out = []
    for m in re.finditer(r'"basePrice":', html):
        start = html.rfind("{", 0, m.start())
        depth, i = 0, start
        while i < len(html):
            if html[i] == "{":
                depth += 1
            elif html[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        try:
            out.append(json.loads(html[start:i + 1]))
        except ValueError:
            continue
    return out


def end_date(v) -> str | None:
    """Sale end: epoch milliseconds or an ISO time, depending on the page."""
    if not v:
        return None
    if str(v).isdigit():
        return datetime.fromtimestamp(int(v) / 1000, timezone.utc).date().isoformat()
    return str(v)[:10] if re.match(r"\d{4}-\d{2}-\d{2}", str(v)) else None


def price_of(concept: str) -> dict | None:
    r = get(f"https://store.playstation.com/{LOCALE}/concept/{concept}")
    if r is None or r.status_code != 200:
        return None
    blocks = price_blocks(r.text)
    if not blocks:
        return None
    included = any(not money(b.get("discountedPrice")) and b.get("discountedPrice") and not b.get("isFree") for b in blocks) or \
        any(b.get("isTiedToSubscription") for b in blocks)
    paid = [b for b in blocks if money(b.get("discountedPrice")) is not None and not b.get("isTiedToSubscription")]
    if not paid:
        free = any(b.get("isFree") for b in blocks)
        return {"price": 0.0 if free else None, "plus": included, "free": free}
    b = paid[0]                  # the main edition comes first
    price, base = money(b.get("discountedPrice")), money(b.get("basePrice"))
    return {"price": price, "base": base if base and base != price else None, "discount": b.get("discountText") or None,
            "until": end_date(b.get("endTime")),
            "plus": included}


def prices(today: date) -> dict:
    wl = load("wishlist.json", {})
    ids = load("store_ids.json", {})
    old = load("prices.json", {})
    out, found, missing = {}, 0, []
    for slug, w in wl.items():
        c = ids.get(slug) or {}
        stale = c.get("concept") is None and (not c.get("checked") or c["checked"] < (today - timedelta(days=14)).isoformat())
        if not c or stale:
            concept, page = concept_for(w["name"])
            c = {"concept": concept, "page": page, "checked": today.isoformat()}
            ids[slug] = c
        if not c.get("concept"):
            missing.append(w["name"])
            continue
        p = price_of(c["concept"])
        time.sleep(0.5)
        if p is None:
            if slug in old:
                out[slug] = old[slug]       # keep last week's price if the page didn't load
            continue
        prev = old.get(slug) or {}
        low = prev.get("low")
        if p.get("price") is not None and (low is None or p["price"] < low):
            low, low_at = p["price"], today.isoformat()
        else:
            low_at = prev.get("low_at")
        plus_since = (prev.get("plus_since") or today.isoformat()) if p.get("plus") else None
        first = prev.get("first_checked") or today.isoformat()     # so games already in PS Plus on day one aren't "new"
        out[slug] = {**{k: v for k, v in p.items() if v not in (None, False)}, "concept": c["concept"], "checked": today.isoformat(),
                     **({"plus_since": plus_since} if plus_since else {}), "first_checked": first,
                     **({"low": low, "low_at": low_at} if low is not None else {}),
                     **({"prev": prev.get("price")} if prev.get("price") is not None and prev.get("price") != p.get("price") else {})}
        found += 1
    for slug in [s for s in ids if s not in wl]:
        ids.pop(slug)
    save("store_ids.json", ids)
    save("prices.json", out)
    print(f"::notice::PS Store prices: {found} of {len(wl)} wishlist games" + (f" · not found in the Swiss store: {', '.join(missing)}" if missing else ""))
    return out


def main() -> None:
    today = datetime.now(timezone.utc).date()
    if "--prices-only" not in sys.argv:
        p = psplus(today)
        if p:
            save("psplus.json", p)
    if "--plus-only" not in sys.argv:
        prices(today)


if __name__ == "__main__":
    main()
