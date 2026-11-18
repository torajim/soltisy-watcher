"""임시 진단: GitHub Actions 러너에서 실패 중인 사이트가 무엇을 돌려주는지 출력한다."""
import re
import requests

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1 soltisy-watcher")
DESKTOP = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
URLS = [
    "https://www.thehandsome.com/api/display/1/ko/category/categoryGoodsList?brandNo=BR06&mainBrand=BR06&mainCategory=10000001&norOutletGbCd=J&sortGbn=10&soutYn=Y&pageNo=1",
    "https://www.thehandsome.com/ko/",
    "https://www.prada.com/kr/ko/mens/new-in/c/10182KR.html",
    "https://www.sculpstore.com/product/list.html?cate_no=255&sort_method=5",
]
MARKERS = ["\"hits\"", "ProductName", "__NEXT_DATA__", "algolia", "akamai", "captcha", "Access Denied",
           "_abck", "bm-verify", "cloudflare", "점검", "maintenance", "window.__STATE__", "application/ld+json"]

for url in URLS:
    for name, ua in (("app-UA", UA), ("desktop-UA", DESKTOP)):
        print(f"===== {url}  [{name}]")
        try:
            r = requests.get(url, headers={"User-Agent": ua, "Accept-Language": "ko-KR,ko;q=0.9"}, timeout=30)
        except Exception as e:
            print("ERROR", repr(e)); continue
        print("status", r.status_code, "final", r.url, "history", [h.status_code for h in r.history])
        for h in ("Content-Type", "Server", "Content-Length", "Set-Cookie", "Cache-Control", "X-Cache", "Akamai-GRN", "CF-Ray"):
            if h in r.headers:
                print(f"  {h}: {r.headers[h][:200]}")
        r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
        t = r.text
        title = re.search(r"<title[^>]*>(.*?)</title>", t, re.S | re.I)
        print("  len", len(t), "title", repr(title.group(1).strip()[:120]) if title else None)
        print("  markers", {m: t.count(m) for m in MARKERS if m in t})
        print("  head", repr(" ".join(t[:600].split())))
        i = t.find("hits")
        if i >= 0:
            print("  around 'hits'", repr(t[max(0, i - 200):i + 300]))
