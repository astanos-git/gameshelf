"""Temporary probe (deleted after use): PS Store search via its own persisted query (public data)."""
import json, re, hashlib, itertools
import requests
from graphql import parse, print_ast
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "fr-CH,fr;q=0.9"}
t = requests.get("https://store.playstation.com/fr-ch/search/cairn", headers=UA, timeout=30).text
app = [s for s in re.findall(r'<script[^>]+src="([^"]+\.js)"', t) if "_app-" in s][0]
js = requests.get("https://store.playstation.com" + app, headers=UA, timeout=30).text
def tmpl(start):
    i = js.find(start); j = js.find('"]', i)
    return json.loads('"' + js[i:j] + '"').replace('","', "")
def piece(marker):
    i = js.find(marker); i = js.rfind('["', 0, i) + 2; j = js.find('"]', i)
    return json.loads("[" + '"' + js[i:j] + '"]')
q = "".join(piece("query getSearchResults("))
frags = {}
for name in ["priceFragment", "personalizedMetaFragment"]:
    k = js.find(f"fragment {name} on")
    i = js.rfind('["', 0, k) + 2; j = js.find('"]', i)
    frags[name] = "".join(json.loads('["' + js[i:j] + '"]'))
    print(name, frags[name][:300].replace("\n", " "))
H = {**UA, "x-psn-store-locale-override": "fr-CH", "content-type": "application/json"}
var = {"countryCode": "CH", "languageCode": "fr", "pageOffset": 0, "pageSize": 5, "searchTerm": "cairn", "searchDomains": "MobileUniversalSearchGame", "nextCursor": ""}
for order in itertools.permutations(frags):
    doc = q + "".join("\n" + frags[n] for n in order)
    for printed in [print_ast(parse(doc)), doc]:
        h = hashlib.sha256(printed.encode()).hexdigest()
        r = requests.get("https://web.np.playstation.com/api/graphql/v1/op", params={"operationName": "getSearchResults", "variables": json.dumps(var), "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": h}})}, headers=H, timeout=30)
        print(order, "printed" if printed != doc else "raw", h[:12], r.status_code, r.text[:700].replace("\n", " "))
        if r.status_code == 200: break
