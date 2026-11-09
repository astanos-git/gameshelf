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
from graphql.language import ast as A
def add_typename(doc):
    d = parse(doc)
    def walk(node, parent_is_op):
        ss = getattr(node, "selection_set", None)
        if ss is not None:
            if not parent_is_op and not any(isinstance(x, A.FieldNode) and x.name.value.startswith("__") for x in ss.selections):
                ss.selections = (*ss.selections, A.FieldNode(name=A.NameNode(value="__typename"), arguments=(), directives=()))
            for sel in ss.selections: walk(sel, False)
    for df in d.definitions: walk(df, isinstance(df, A.OperationDefinitionNode))
    return print_ast(d)
for order in itertools.permutations(frags):
    doc = q + "".join("\n" + frags[n] for n in order)
    for printed in [add_typename(doc), print_ast(parse(doc))]:
        h = hashlib.sha256(printed.encode()).hexdigest()
        r = requests.get("https://web.np.playstation.com/api/graphql/v1/op", params={"operationName": "getSearchResults", "variables": json.dumps(var), "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": h}})}, headers=H, timeout=30)
        print(order, "printed" if printed != doc else "raw", h[:12], r.status_code, r.text[:700].replace("\n", " "))
        if r.status_code == 200: break
