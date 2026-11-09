"""Temporary probe (deleted after use): playstation.com game pages -> store ids (public data)."""
import re
import requests
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Accept-Language": "fr-CH,fr;q=0.9"}
for slug in ["cairn", "ratchet-and-clank-rift-apart", "sekiro-shadows-die-twice", "owlboy", "brothers-a-tale-of-two-sons-remake", "marvels-wolverine", "the-blood-of-dawnwalker", "007-first-light", "phantom-blade-zero"]:
    u = f"https://www.playstation.com/fr-ch/games/{slug}/"
    try:
        r = requests.get(u, headers=UA, timeout=30); t = r.text
        ids = list(dict.fromkeys(re.findall(r'\b([EU]P\d{4}-[A-Z]{4}\d{5}_00-[A-Z0-9]{16})\b', t)))
        cons = list(dict.fromkeys(re.findall(r'concept/(\d{5,9})', t) + re.findall(r'"conceptId"\s*:\s*"?(\d{5,9})', t)))
        print(slug, r.status_code, len(t), "EP ids", [i for i in ids if i.startswith("EP")][:3], "concepts", cons[:3], re.findall(r'CHF[\s\xa0]?\d+[.,]\d\d', t)[:2])
    except Exception as e:
        print(slug, repr(e)[:120])
