"""Temporary probe (deleted after use): what PSN entitlements, the Swiss PS Store, the PlayStation Blog and Push Square expose.
Prints only field names and counts, no personal data."""
import collections, json, os, re
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "en-CH,en;q=0.9"}

def section(t): print(f"\n===== {t}")

section("PSN entitlements")
try:
    from psnawp_api import PSNAWP
    me = PSNAWP(os.environ["PSN_NPSSO"]).me()
    ents = list(me.game_entitlements(limit=None))
    keys = collections.Counter(k for e in ents for k in e)
    print(len(ents), "entitlements; keys:", dict(keys))
    for k in ["entitlementType", "feature", "isConsumable", "rewardId", "activeFlag", "membership", "isPlus", "skuId", "inactiveDate", "preorder", "isSubscription"]:
        if k in keys: print(k, collections.Counter(str(type(e.get(k)).__name__ + ":" + (str(e.get(k))[:20] if k not in ("rewardId", "skuId", "inactiveDate") else ("set" if e.get(k) else "none"))) for e in ents).most_common(8))
    for sub in ["gameMeta", "titleMeta", "conceptMeta", "entitlementAttributes", "feature"]:
        ks = collections.Counter(k for e in ents if isinstance(e.get(sub), dict) for k in e[sub])
        if ks: print(sub, dict(ks))
    fe = collections.Counter(json.dumps(e.get("feature"), sort_keys=True)[:120] for e in ents)
    print("feature values:", fe.most_common(6))
except Exception as e:
    print("PSN failed:", repr(e)[:300])

section("PS Store CH search")
for url in ["https://store.playstation.com/en-ch/search/cairn", "https://store.playstation.com/de-ch/search/cairn"]:
    try:
        r = requests.get(url, headers=UA, timeout=30)
        t = r.text
        print(url, r.status_code, len(t), "next_data" if "__NEXT_DATA__" in t else "", "apollo" if "apolloState" in t or "__APOLLO" in t else "")
        ids = re.findall(r'"id":"([A-Z]{2}\d{4}-[A-Z]{4}\d{5}_00-[A-Z0-9]+)"', t)[:5]
        print(" product ids:", ids)
        prices = re.findall(r'"(basePrice|discountedPrice)":"([^"]+)"', t)[:6]
        print(" prices:", prices)
    except Exception as e:
        print(url, "failed", repr(e)[:200])

section("PS Store product page")
try:
    r = requests.get("https://store.playstation.com/en-ch/search/cairn", headers=UA, timeout=30)
    pid = re.search(r'"id":"([A-Z]{2}\d{4}-[A-Z]{4}\d{5}_00-[A-Z0-9]+)"', r.text)
    if pid:
        u = f"https://store.playstation.com/en-ch/product/{pid.group(1)}"
        p = requests.get(u, headers=UA, timeout=30)
        print(u, p.status_code, re.findall(r'"(basePrice|discountedPrice|discountText|endTime)":"?([^",]+)', p.text)[:8])
except Exception as e:
    print("product failed", repr(e)[:200])

section("PS Store GraphQL search (persisted query)")
try:
    q = {"operationName": "getSearchResults", "variables": json.dumps({"searchTerm": "cairn", "pageOffset": 0, "pageSize": 5, "countryCode": "CH", "languageCode": "en"})}
    r = requests.get("https://web.np.playstation.com/api/graphql/v1/op", params=q, headers={**UA, "x-psn-store-locale-override": "en-CH"}, timeout=30)
    print(r.status_code, r.text[:300])
except Exception as e:
    print("graphql failed", repr(e)[:200])

section("PlayStation Blog feed")
try:
    r = requests.get("https://blog.playstation.com/feed/", headers=UA, timeout=30)
    titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", r.text)
    print(r.status_code, [a or b for a, b in titles][:25])
    r2 = requests.get("https://blog.playstation.com/tag/playstation-plus/feed/", headers=UA, timeout=30)
    print("tag feed", r2.status_code, [a or b for a, b in re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", r2.text)][:25])
except Exception as e:
    print("blog failed", repr(e)[:200])

section("Push Square PS Plus leaving")
for url in ["https://www.pushsquare.com/guides/ps-plus-extra-premium-games-leaving", "https://www.pushsquare.com/feeds/latest", "https://www.pushsquare.com/search?q=leaving+ps+plus"]:
    try:
        r = requests.get(url, headers=UA, timeout=30)
        print(url, r.status_code, len(r.text), [t for t in re.findall(r"<title>(.*?)</title>", r.text) if "Plus" in t][:10])
    except Exception as e:
        print(url, "failed", repr(e)[:200])
