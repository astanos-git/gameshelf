"""Temporary probe (deleted after use): public store data only."""
import json, re
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "fr-CH,fr;q=0.9,en;q=0.8"}
def section(t): print(f"\n===== {t}")
section("fr-ch search page")
for u in ["https://store.playstation.com/fr-ch/search/cairn", "https://store.playstation.com/de-ch/search/death%20stranding%202"]:
    r = requests.get(u, headers=UA, timeout=30); t = r.text
    print(u, r.status_code, len(t), "CHF" in t)
    print(" concept/product links:", list(dict.fromkeys(re.findall(r'/(?:concept|product)/([A-Za-z0-9_-]+)', t)))[:8])
    print(" prices:", re.findall(r'"(?:basePrice|discountedPrice)":"[^"]+"', t)[:6], re.findall(r'.{40}CHF.{20}', t)[:3])
    print(" names:", re.findall(r'"name":"([^"]{3,60})"', t)[:10])
section("fr-ch concept page")
r = requests.get("https://store.playstation.com/fr-ch/search/cairn", headers=UA, timeout=30)
cid = (re.findall(r'/concept/(\d+)', r.text) or [None])[0]
pid = (re.findall(r'/product/([A-Z]{2}\d{4}-[A-Z0-9_-]+)', r.text) or [None])[0]
print("first concept", cid, "product", pid)
for u in [f"https://store.playstation.com/fr-ch/concept/{cid}" if cid else None, f"https://store.playstation.com/fr-ch/product/{pid}" if pid else None]:
    if not u: continue
    t = requests.get(u, headers=UA, timeout=30).text
    print(u, len(t), re.findall(r'"(?:basePrice|discountedPrice|discountText|endTime|serviceBranding|upsellText)":(?:"[^"]*"|\[[^\]]*\]|null)', t)[:14])
    print(" jsonld:", re.findall(r'<script id="mfe-jsonld-tags" type="application/ld\+json">(.*?)</script>', t, re.S)[:1][0][:500] if 'mfe-jsonld-tags' in t else "")
section("Push Square leaving")
for q in ["status=leaving&tier=ps-plus-extra", "status=leaving", "status=leaving-soon"]:
    r = requests.get("https://www.pushsquare.com/guides/all-ps-plus-games-available-now?" + q, headers=UA, timeout=30); t = r.text
    print(q, r.status_code, len(t))
    print(" options:", sorted(set(re.findall(r'status=([a-z-]+)', t)))[:10], sorted(set(re.findall(r'tier=([a-z-]+)', t)))[:6])
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.S)
    print(" rows", len(rows), [re.sub(r"<[^>]+>", " | ", x).strip()[:160] for x in rows[:6]])
    print(" items", [re.sub(r"<[^>]+>", "", x).strip()[:80] for x in re.findall(r'<(?:li|div) class="[^"]*(?:game|item|title)[^"]*"[^>]*>(.*?)</(?:li|div)>', t, re.S)[:8]])
