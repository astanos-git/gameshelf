"""Temporary probe (deleted after use). Prints only field names, counts and public store data."""
import collections, json, os, re
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "en-CH,en;q=0.9"}
def section(t): print(f"\n===== {t}")

section("PSN entitlements detail")
try:
    from psnawp_api import PSNAWP
    me = PSNAWP(os.environ["PSN_NPSSO"]).me()
    ents = [e for e in me.game_entitlements(limit=None) if not e.get("isBeta") and e.get("isGame") is not False]
    print(len(ents), "game entitlements")
    print("serviceType", collections.Counter(str(e.get("serviceType")) for e in ents))
    print("featureType", collections.Counter(str(e.get("featureType")) for e in ents))
    print("rewardMeta keys", collections.Counter(k for e in ents if isinstance(e.get("rewardMeta"), dict) for k in e["rewardMeta"]), collections.Counter(type(e.get("rewardMeta")).__name__ for e in ents))
    print("rewardMeta sample values", collections.Counter(json.dumps(e.get("rewardMeta"), sort_keys=True)[:100] for e in ents).most_common(5))
    print("entitlementAttributes sample", collections.Counter(json.dumps(e.get("entitlementAttributes"), sort_keys=True)[:140] for e in ents).most_common(5))
    by = collections.Counter((str(e.get("serviceType")), (e.get("inactiveDate") or "none")[:7]) for e in ents)
    print("serviceType x inactive month", sorted(by.items())[:60])
    now = "2026-11-09"
    soon = [(e["inactiveDate"][:10], e["serviceType"]) for e in ents if e.get("inactiveDate") and now <= e["inactiveDate"][:10] <= "2027-01-31"]
    print("inactive between now and Jan 2027:", sorted(soon)[:30])
except Exception as e:
    print("PSN failed:", repr(e)[:300])

section("PS Store search structure")
try:
    r = requests.get("https://store.playstation.com/en-ch/search/cairn", headers=UA, timeout=30)
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.S)
    nd = json.loads(m.group(1)) if m else {}
    s = json.dumps(nd)
    print("next_data size", len(s))
    for k in ["price", "basePrice", "discountedPrice", "Product:", "Concept:", "skus", "webctas"]:
        i = s.find(k); print(k, i, s[max(0, i - 150):i + 250] if i >= 0 else "")
    apollo = re.findall(r'<script[^>]*id="env:[^"]*"[^>]*>(.*?)</script>', r.text, re.S)
    print("env scripts", len(apollo), [a[:200] for a in apollo[:3]])
    for key in re.findall(r'"(Product:[^"]+|Concept:[^"]+)"', r.text)[:8]: print(" key", key)
    print("raw price snippets", re.findall(r'.{80}CHF.{80}', r.text)[:5])
except Exception as e:
    print("store failed", repr(e)[:300])

section("Push Square guides")
try:
    r = requests.get("https://www.pushsquare.com/feeds/latest", headers=UA, timeout=30)
    print(re.findall(r"<item>\s*<title>(.*?)</title>\s*<link>(.*?)</link>", r.text)[:40])
except Exception as e:
    print("ps failed", repr(e)[:200])
for u in ["https://www.pushsquare.com/guides/all-ps-plus-games-leaving-in-november-2026", "https://www.pushsquare.com/guides/all-ps-plus-extra-premium-games-leaving-in-november-2026", "https://www.pushsquare.com/guides/all-ps-plus-games-available-now"]:
    try:
        r = requests.get(u, headers=UA, timeout=30); print(u, r.status_code, re.findall(r"<title>(.*?)</title>", r.text)[:1])
    except Exception as e: print(u, repr(e)[:100])
