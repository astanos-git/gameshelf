"""Temporary probe (deleted after use): RAWG store links -> Swiss PS Store page prices (public data)."""
import json, os, re
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "fr-CH,fr;q=0.9"}
key = os.environ.get("RAWG_API_KEY")
wl = json.load(open("docs/wishlist.json"))
for slug in list(wl)[:8] + ["cairn", "marvels-wolverine"]:
    try:
        r = requests.get(f"https://api.rawg.io/api/games/{slug}/stores", params={"key": key}, timeout=30)
        urls = [x["url"] for x in r.json().get("results", []) if "playstation" in x.get("url", "")]
    except Exception as e:
        print(slug, "rawg", repr(e)[:100]); continue
    print(slug, r.status_code, urls[:2])
    for u in urls[:1]:
        m = re.search(r'/(concept|product)/([A-Za-z0-9_-]+)', u)
        if not m: continue
        page = f"https://store.playstation.com/fr-ch/{m.group(1)}/{m.group(2)}"
        t = requests.get(page, headers=UA, timeout=30)
        print("  ", page, t.status_code, re.findall(r'"(?:basePrice|discountedPrice|discountText|serviceBranding)":(?:"[^"]*"|\[[^\]]*\])', t.text)[:8], re.findall(r'"name":"([^"]{3,60})"', t.text)[:2])
