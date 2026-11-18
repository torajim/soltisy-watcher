"""임시 진단: 프라다 페이지 원본을 로그로 내보낸다 (gzip+base64)."""
import base64, gzip, requests

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1 soltisy-watcher")
r = requests.get("https://www.prada.com/kr/ko/mens/new-in/c/10182KR.html",
                 headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}, timeout=30)
data = base64.b64encode(gzip.compress(r.content, 9)).decode()
print("PRADA_DUMP_BEGIN", len(r.content), len(data))
for i in range(0, len(data), 4000):
    print("PD:" + data[i:i + 4000])
print("PRADA_DUMP_END")
