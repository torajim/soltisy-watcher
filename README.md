# Soltisy Watcher

솔리드옴므 · 타임옴므 · 시스템옴므의 신상품을 모아 **큰 이미지로 스와이프하며 보고**, 마음에 들면 바로 상품 페이지로 이동하는 모바일 웹 앱.

- 세로 스와이프 → 다음 상품, 가로 스와이프 → 같은 상품의 다른 이미지
- 브랜드 / 종류(상의·하의·신발·잡화) 필터
- **내 사이즈 추천**: 평소 사이즈 표기(예: `100, 48, L`)와 잘 맞는 옷의 실측(단면 cm)을 등록하면 상품마다 추천 사이즈, 품절 여부, 실측 차이를 보여줌
- 가상 피팅(체형 사진에 입혀보기)은 자리만 마련 (`site/js/tryon.js`)

## 구조

```
crawler/            Python 수집기 → site/data/products.json 생성
  brands.toml       수집 대상 브랜드 목록 (여기에 추가)
  watcher/sources/  사이트 유형별 어댑터 (thehandsome, cafe24)
site/               정적 모바일 웹 앱 (빌드 없음, 바닐라 JS)
  js/sizing.js      사이즈 추천 로직
.github/workflows/deploy.yml   3시간마다 수집 → GitHub Pages 배포
```

| 브랜드 | 출처 | 신상품 기준 |
|---|---|---|
| SOLID HOMME | solidhomme.com (Cafe24) | `신상품` 카테고리 (cate_no=83) |
| TIME HOMME | 더한섬닷컴 (BR06) | 신상품순 상위 60개, 품절·여성 라인 제외 |
| SYSTEM HOMME | 더한섬닷컴 (BR07) | 신상품순 상위 60개, 품절·여성 라인 제외 |

사이즈 프로필은 **브라우저(localStorage)에만** 저장되고 서버로 보내지 않습니다.

## 브랜드 추가

더한섬닷컴 입점 브랜드나 Cafe24 자체몰이면 `crawler/brands.toml` 에 블록만 추가하면 됩니다.

```toml
[[brand]]
id = "lanvin"            # 앱 내부 id
name = "LANVIN COLLECTION"
source = "thehandsome"
brand_no = "BR??"        # getDispCtgBrandList API 에서 확인
limit = 60
```

다른 종류의 사이트는 `crawler/watcher/sources/base.py` 의 `Source` 를 상속한 어댑터를 만들고 `sources/__init__.py` 의 `SOURCE_TYPES` 에 등록합니다.

## 로컬 실행

```bash
cd crawler
pip install -r requirements.txt
python -m watcher              # 전체 수집 (약 2~3분)
python -m watcher --limit 5    # 빠르게 확인
python -m pytest -q            # 크롤러 테스트

cd ../site
npm test                       # 사이즈 추천/피드 로직 테스트
python3 -m http.server 8000    # http://localhost:8000
```

## 배포 (GitHub Pages)

1. 저장소 **Settings → Pages → Build and deployment → Source** 를 **GitHub Actions** 로 설정
2. `main` 브랜치에 푸시하면 테스트 → 수집 → 배포. 이후 3시간마다 자동 갱신 (Actions 탭에서 수동 실행도 가능)
3. 주소: `https://<계정>.github.io/soltisy-watcher/` — 모바일 브라우저에서 "홈 화면에 추가"하면 앱처럼 쓸 수 있음

한 브랜드 수집이 실패하면 직전 배포본의 그 브랜드 데이터를 유지합니다.
