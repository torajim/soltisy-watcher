"""임시: GitHub 러너에서 신규 브랜드 엔드포인트 접근 확인 (머지 전 삭제)."""
import requests
UAS = {
    "iphone": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1 soltisy-watcher",
    "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
}
URLS = [
    "https://www.coor.kr/product/list.html?cate_no=94",
    "https://www.zara.com/kr/ko/category/2544454/products?ajax=true",
    "https://www.zara.com/kr/ko/x-p03286417.html?v1=605310896&ajax=true",
    "https://www.uniqlo.com/kr/api/commerce/v5/ko/products?path=%2C%2C&limit=5",
    "https://www.uniqlo.com/kr/ko/men",
    "https://www.cos.com/ko-kr/men/new-arrivals.html",
    "https://www.cos.com/en-kr/men/new-arrivals.html",
    "https://www.massimodutti.com/kr/",
    "https://www.massimodutti.com/itxrest/2/catalog/store/35009516/30359499/category?languageId=-9&typeCatalog=1&appId=1",
    "https://hi.thehyundai.com/proxy/v1/dp/search/searchResult?targetCode=M00021&page=1&disPlaySize=10&flCate=400003&target=brand&searchType=NCP_PRODUCT",
]
for name, ua in UAS.items():
    s = requests.Session(); s.headers.update({"User-Agent": ua, "Accept-Language": "ko-KR,ko;q=0.9"})
    for u in URLS:
        try:
            r = s.get(u, timeout=25, allow_redirects=True)
            body = " ".join(r.text[:160].split())
            print(f"PROBE {name} {r.status_code} {len(r.content)}B {r.headers.get('Server','?')} {u[:110]} :: {body}")
        except Exception as e:
            print(f"PROBE {name} ERR {u[:110]} :: {e}")
