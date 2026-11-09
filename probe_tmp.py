"""Temporary probe (deleted after use): public store data only."""
import json, re, hashlib
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "fr-CH,fr;q=0.9"}
def section(t): print(f"\n===== {t}")
section("shared nav search endpoints")
js = requests.get("https://web-commerce-anywhere.playstation.com/static/shared-nav/shared-nav.js", headers=UA, timeout=30).text
for m in set(re.findall(r'https?://[a-z0-9.-]+playstation[a-z0-9.-]*\.(?:com|net)[^"\'` ]{0,120}', js)): print(" url", m)
i = js.find("tumbler"); print(js[i - 600:i + 900].replace("\n", " ") if i > 0 else "no tumbler")
section("app bundle: full search query + fragments")
t = requests.get("https://store.playstation.com/fr-ch/search/cairn", headers=UA, timeout=30).text
app = [s for s in re.findall(r'<script[^>]+src="([^"]+\.js)"', t) if "_app-" in s][0]
js = requests.get("https://store.playstation.com" + app, headers=UA, timeout=30).text
i = js.find("query getSearchResults"); print(js[i - 1500:i + 2500])
