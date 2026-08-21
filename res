import sys
import httpx

URL = "https://auth.zelle.cat.earlywarning.io/token"

for proxy in sys.argv[1:]:
    try:
        r = httpx.get(URL, proxy=proxy, timeout=10)
        print(f"{proxy}  ->  WORKS (HTTP {r.status_code})")
    except Exception as e:
        print(f"{proxy}  ->  FAILED ({type(e).__name__}: {e})")
