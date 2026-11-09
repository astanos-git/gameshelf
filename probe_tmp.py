"""Temporary probe (deleted after use): public store data only."""
import json, re
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "fr-CH,fr;q=0.9"}
def section(t): print(f"\n===== {t}")
section("bundles")
t = requests.get("https://store.playstation.com/fr-ch/search/cairn", headers=UA, timeout=30).text
srcs = list(dict.fromkeys(re.findall(r'<script[^>]+src="([^"]+\.js)"', t)))
print(len(srcs), srcs[:40])
found = {}
for s in srcs:
    u = s if s.startswith("http") else "https://store.playstation.com" + s
    try: js = requests.get(u, headers=UA, timeout=30).text
    except Exception: continue
    for m in re.finditer(r'(getSearchResults|metGetSearch\w*|searchResults\w*|\w*[Ss]earch\w*Query)', js):
        ctx = js[max(0, m.start() - 300): m.end() + 300]
        hs = re.findall(r'[0-9a-f]{64}', ctx)
        if hs: found.setdefault(m.group(1), set()).update(hs)
    for m in re.finditer(r'operationName:"(\w*[Ss]earch\w*)"', js): found.setdefault("op:" + m.group(1), set())
    # lazy chunks
    for c in re.findall(r'"(static/chunks/[^"]+\.js)"', js)[:0]: pass
print({k: list(v)[:3] for k, v in found.items()})
section("next data buildId and chunks")
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', t, re.S)
nd = json.loads(m.group(1)) if m else {}
print({k: (v if not isinstance(v, (dict, list)) else type(v).__name__) for k, v in nd.items()})
print(json.dumps(nd.get("props", {}))[:600])
section("Push Square all")
r = requests.get("https://www.pushsquare.com/guides/all-ps-plus-games-available-now?status=all", headers=UA, timeout=30); tx = r.text
rows = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", x)).strip() for x in re.findall(r'<tr[^>]*>(.*?)</tr>', tx, re.S)]
print("rows", len(rows)); import collections
avail = collections.Counter((x.split("|")[-2].strip() if x.count("|") > 2 else "?")[:14] for x in rows)
print(avail.most_common(15)); print([x[:150] for x in rows if "Until" in x or "From" in x][:12])
