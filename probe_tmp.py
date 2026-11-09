"""Temporary probe (deleted after use): Swiss PS Store page prices (public store data)."""
import os, re
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "fr-CH,fr;q=0.9"}
from psnawp_api import PSNAWP
me = PSNAWP(os.environ["PSN_NPSSO"]).me()
cids = []
for e in me.game_entitlements(limit=None):
    c = (e.get("conceptMeta") or {}).get("conceptId")
    if c and not (e.get("rewardMeta") or {}).get("rewardMembershipType") and c not in cids: cids.append(c)
    if len(cids) >= 4: break
for c in cids:
    for loc in ["fr-ch", "de-ch"]:
        u = f"https://store.playstation.com/{loc}/concept/{c}"
        t = requests.get(u, headers=UA, timeout=30).text
        print(loc, "concept", len(t), re.findall(r'"(?:basePrice|discountedPrice|discountText|endTime)":(?:"[^"]*"|null)', t)[:6], re.findall(r'"invariantName":"([^"]{3,60})"', t)[:1])
for pid in ["EP9000-PPSA01474_00-RATCHETCLANKRIFT", "UP9000-PPSA01473_00-RATCHETCLANKRIFT"]:
    t = requests.get(f"https://store.playstation.com/fr-ch/product/{pid}", headers=UA, timeout=30).text
    print(pid, len(t), re.findall(r'"(?:basePrice|discountedPrice|discountText|endTime)":(?:"[^"]*"|null)', t)[:6])
r = requests.get("https://api.rawg.io/api/games", params={"key": os.environ.get("RAWG_API_KEY"), "search": "cairn", "page_size": 1}, timeout=30); print("rawg", r.status_code)
