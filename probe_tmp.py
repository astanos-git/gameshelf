"""Temporary probe (deleted after use): PS Store data access. Public store data only."""
import json, re
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "en-CH,en;q=0.9"}
def section(t): print(f"\n===== {t}")
G = "https://web.np.playstation.com/api/graphql/v1/op"
H = {**UA, "x-psn-store-locale-override": "en-CH", "content-type": "application/json"}
def op(name, h, var):
    r = requests.get(G, params={"operationName": name, "variables": json.dumps(var), "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": h}})}, headers=H, timeout=30)
    return r.status_code, r.text
tests = [
  ("metGetProductById", "a128042177bd93dd831164103d53b73ef790d56f51dae647064cb8f9d9fc9d1a", {"productId": "EP9000-PPSA08338_00-MARVELSPIDERMAN2"}),
  ("metGetConceptById", "cc90404ac049d935afbd9968aef523da2b6723abfb9d586e5f77ebf7c5289006", {"conceptId": "10002694", "productId": ""}),
  ("metGetPricingDataByConceptId", "abcb311ea830e679fe2b697a27f755764535d825b24510ab1239a4ca3092bd09", {"conceptId": "10002694"}),
  ("categoryGridRetrieve", "4ce7d410a4db2c8b635a48c1dcec375906ff63b19dadd87e073f8fd0c0481d35", {"id": "44d8bb20-653e-431e-8ad0-c0a365f68d2f", "pageArgs": {"size": 5, "offset": 0}, "sortBy": None, "filterBy": [], "facetOptions": []}),
  ("getSearchResults", "a2fbc15433b37ca7bfcd7112f741735e13268f5e9ebd5ae83bd0a8d8b27ec8b4", {"searchTerm": "cairn", "pageOffset": 0, "pageSize": 5}),
  ("metGetSearchResults", "9c3c69ebc7b1d0fb06dd7ba0e3d7e6b0a3f2d3b2e8a3c1f5b6c1d0e3f2a1b4c5", {"searchTerm": "cairn"}),
]
section("graphql persisted")
for n, h, v in tests:
    try:
        c, t = op(n, h, v); print(n, c, t[:600].replace("\n", " "))
    except Exception as e: print(n, repr(e)[:200])
section("chihiro")
for u in ["https://store.playstation.com/store/api/chihiro/00_09_000/tumbler/CH/en/999/cairn?suggested_size=5&mode=game",
          "https://store.playstation.com/valkyrie-api/en/CH/999/faceted-search/cairn?query=cairn&game_content_type=games&size=5"]:
    try:
        r = requests.get(u, headers=UA, timeout=30); print(u[:70], r.status_code, r.text[:500].replace("\n", " "))
    except Exception as e: print(u[:70], repr(e)[:200])
section("store html: product page + concept page")
for u in ["https://store.playstation.com/en-ch/concept/10002694", "https://store.playstation.com/en-ch/category/44d8bb20-653e-431e-8ad0-c0a365f68d2f/1"]:
    try:
        r = requests.get(u, headers=UA, timeout=30)
        t = r.text
        print(u, r.status_code, len(t), "CHF" in t, re.findall(r'.{60}(?:CHF|Fr\.).{40}', t)[:3], re.findall(r'"(?:basePrice|discountedPrice)":"[^"]+"', t)[:4])
        print(" scripts:", [m[:80] for m in re.findall(r'<script[^>]*id="([^"]+)"', t)][:12])
    except Exception as e: print(u, repr(e)[:200])
section("PS Plus guide (Push Square)")
r = requests.get("https://www.pushsquare.com/guides/all-ps-plus-games-available-now", headers=UA, timeout=30)
t = r.text
print(len(t), [h for h in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", t)][:30])
print([x for x in re.findall(r'href="(https://www\.pushsquare\.com/(?:guides|news)/[^"]*(?:leav|extra|essential|catalog)[^"]*)"', t)][:15])
