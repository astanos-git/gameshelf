"""Temporary probe (deleted after use): public store data only."""
import json, re
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "fr-CH,fr;q=0.9"}
def section(t): print(f"\n===== {t}")
section("bundle hashes")
t = requests.get("https://store.playstation.com/fr-ch/search/cairn", headers=UA, timeout=30).text
srcs = list(dict.fromkeys(re.findall(r'<script[^>]+src="([^"]+\.js)"', t)))
ops = {}
for s in srcs:
    u = s if s.startswith("http") else "https://store.playstation.com" + s
    try: js = requests.get(u, headers=UA, timeout=30).text
    except Exception: continue
    for m in re.finditer(r'[0-9a-f]{64}', js):
        ctx = js[max(0, m.start() - 200): m.end() + 200]
        names = re.findall(r'\b((?:met|get|wca)\w{3,40})\b', ctx)
        ops.setdefault(m.group(0), set()).update(n for n in names if "earch" in n or "rice" in n or "oncept" in n or "roduct" in n)
    if "searchTerm" in js:
        i = js.find("searchTerm"); print("searchTerm in", u.split("/")[-1], js[max(0, i - 400): i + 200].replace("\n", " ")[:600])
print({h: sorted(v)[:4] for h, v in ops.items() if v})
section("psprices")
for u in ["https://psprices.com/region-ch/search/?q=cairn&platform=PS5", "https://psprices.com/region-ch/games/?q=cairn"]:
    try:
        r = requests.get(u, headers=UA, timeout=30); x = r.text
        print(u, r.status_code, len(x), "cloudflare" in x.lower(), re.findall(r'.{60}CHF.{30}', x)[:3], re.findall(r'href="(/region-ch/game/[^"]+)"', x)[:4])
    except Exception as e: print(u, repr(e)[:200])
section("wikidata PS store ids")
q = 'SELECT ?item ?itemLabel ?id WHERE { VALUES ?name { "Cairn"@en "Death Stranding 2: On the Beach"@en "Ratchet & Clank: Rift Apart"@en } ?item rdfs:label ?name; wdt:P5944 ?id. SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }'
r = requests.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"}, headers={"User-Agent": "gameshelf-probe/1.0"}, timeout=60)
print(r.status_code, [(b["itemLabel"]["value"], b["id"]["value"]) for b in r.json()["results"]["bindings"]][:12])
