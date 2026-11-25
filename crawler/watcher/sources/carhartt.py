"""칼하트WIP 코리아(carhartt-wip.co.kr) — 웍스아웃이 운영하는 Next.js 몰의 공개 JSON API 를 읽는다.

  - 목록: https://msa.carhartt-wip.co.kr/v2/products?mainCategoryId={분류}&sourceSite=CARHARTT&sort=id,desc
          (id,desc = 사이트의 기본 정렬, 최근 등록순). MEN 15 / WOMEN 19
  - 상세: /v2/products/{productId}?sourceSite=CARHARTT  → 이미지 전체와 사이즈별 실측(actualMeasures)
성별은 목록 분류(MEN/WOMEN)를 따르고, 두 목록에 모두 있으면 공용으로 합쳐진다.
색상마다 상품 번호가 따로 있어 한 상품이 색상별로 여러 개 나온다. 판매 예정(isComingSoon) 상품은 건너뛴다.
"""
from __future__ import annotations

import logging

from ..classify import classify
from ..measurements import normalize_all, parse_number
from ..models import Product, SizeOption
from .base import Http, Source

log = logging.getLogger(__name__)

SITE = "https://www.carhartt-wip.co.kr"
API = "https://msa.carhartt-wip.co.kr"
SOURCE_SITE = "CARHARTT"
PAGE_SIZE = 40
MAX_IMAGES = 8


def _payload(data: dict):
    if data.get("code") != "SUCCESS":
        raise RuntimeError(f"칼하트WIP API 오류: {data.get('code')} {data.get('message')}")
    return data.get("payload")


def images(item: dict, detail: dict | None) -> list[str]:
    urls: list[str] = []
    if detail:
        for img in sorted(detail.get("images") or [], key=lambda i: i.get("sort") or 0):
            if (img.get("mediaType") or "") not in ("", "IMAGE"):
                continue
            url = img.get("originalUrl") or img.get("thumbnailUrl")
            if url and url not in urls:
                urls.append(url)
    # 목록의 대표 이미지(-1)를 맨 앞에 둔다. 상세의 첫 장(-0)은 마우스오버용 착용컷이다
    thumb = item.get("thumbnailUrl")
    if thumb:
        urls = [thumb] + [u for u in urls if u != thumb]
    return urls[:MAX_IMAGES]


def parse_sizes(item: dict, detail: dict | None) -> list[SizeOption]:
    rows = (detail or {}).get("sizes") or item.get("sizes") or []
    sizes: list[SizeOption] = []
    seen: set[str] = set()
    for s in sorted(rows, key=lambda r: r.get("sort") or 0):
        label = (s.get("sizeName") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        pairs = [(k, parse_number(str(v))) for k, v in (s.get("actualMeasures") or {}).items()]
        sizes.append(SizeOption(label=label, in_stock=not s.get("isSoldOut"), measurements=normalize_all(pairs)))
    return sizes


def build_product(brand_id: str, brand_name: str, item: dict, detail: dict | None, rank: int) -> Product:
    pid = item["productId"]
    name = (item.get("productName") or "").strip()
    ko_name = (item.get("productKoreanName") or "").strip()
    sizes = parse_sizes(item, detail)
    keys = {k for s in sizes for k in s.measurements}
    initial = int(item.get("initialPrice") or 0)
    current = int(item.get("currentPrice") or initial)
    return Product(
        id=f"{brand_id}:{pid}",
        brand=brand_id,
        brand_name=brand_name,
        name=name or ko_name,
        url=f"{SITE}/products/{pid}",
        images=images(item, detail),
        price=current,
        original_price=max(initial, current),
        type=classify(ko_name, name, measurement_keys=keys),
        color=(item.get("colorName") or "").strip(),
        sizes=sizes,
        size_note="실측 (cm)" if keys else "",
        rank=rank,
    )


class CarharttSource(Source):
    def __init__(self, brand_id: str, brand_name: str, http: Http, main_category_id: int, limit: int = 60):
        super().__init__(brand_id, brand_name, http, limit)
        self.main_category_id = main_category_id

    def list_items(self) -> list[dict]:
        items: list[dict] = []
        page = 0
        while len(items) < self.limit:
            data = _payload(
                self.http.get_json(
                    f"{API}/v2/products",
                    params={
                        "mainCategoryId": self.main_category_id,
                        "sourceSite": SOURCE_SITE,
                        "sort": "id,desc",
                        "size": PAGE_SIZE,
                        "page": page,
                    },
                )
            ) or {}
            batch = data.get("content") or []
            items.extend(i for i in batch if not i.get("isComingSoon"))
            if data.get("last", True) or not batch:
                break
            page += 1
        return items[: self.limit]

    def fetch(self) -> list[Product]:
        products: list[Product] = []
        for item in self.list_items():
            pid = item["productId"]
            try:
                detail = _payload(self.http.get_json(f"{API}/v2/products/{pid}", params={"sourceSite": SOURCE_SITE}))
                if isinstance(detail, list):
                    detail = detail[0] if detail else None
            except Exception as e:  # 상세 하나 실패로 전체를 버리지 않는다
                log.warning("carhartt %s 상세 실패: %s", pid, e)
                detail = None
            p = build_product(self.brand_id, self.brand_name, item, detail, rank=len(products))
            if p.images:
                products.append(p)
        return products
