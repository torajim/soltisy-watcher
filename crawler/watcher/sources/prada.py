"""프라다 공식몰(prada.com) — 카테고리 페이지에 들어 있는 상품 검색 결과(Algolia hits)를 읽는다.

페이지 HTML 안에 `"hits":[{...ProductName...}]` 형태의 JSON 이 그대로 있다.
`?page=` 는 서버에서 무시되어 첫 페이지(최신 24개)만 가져온다.
사이즈 정보는 목록에 없어 사이즈 추천은 하지 않는다.
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote

from ..classify import classify
from ..models import Product
from .base import Http, Source

log = logging.getLogger(__name__)

SITE = "https://www.prada.com"
# 원본(1800px, ~600KB) 대신 1000px 렌디션 (~200KB)
RENDITION = "/_jcr_content/renditions/cq5dam.web.hebebed.1000.1000.jpg"


def parse_hits(html: str) -> list[dict]:
    dec = json.JSONDecoder()
    for m in re.finditer(r'"hits":\[', html):
        try:
            arr, _ = dec.raw_decode(html, m.end() - 1)
        except json.JSONDecodeError:
            continue
        if arr and isinstance(arr[0], dict) and "ProductName" in arr[0]:
            return arr
    return []


def _ko(field, default=""):
    if isinstance(field, dict):
        return field.get("ko_KR") or field.get("en_GB") or default
    return field or default


def build_product(brand_id: str, brand_name: str, hit: dict, locale_path: str, rank: int) -> Product | None:
    name = _ko(hit.get("ProductName"))
    path = _ko(hit.get("UrlReconstructed"))
    if not name or not path:
        return None
    imgs = hit.get("Images") or {}
    images = []
    for key in ("PLPBKG", "HoverBKG", "PLPBKG_MDD"):
        src = imgs.get(key)
        if src and src + RENDITION not in images:
            images.append(src + RENDITION)
    price = hit.get("Price") or {}
    value = int(price.get("Value") or 0)
    sale = int(price.get("DiscountedPrice") or value)
    color = _ko(hit.get("Color")).split("|||")[0]
    return Product(
        id=f"{brand_id}:{hit.get('objectID') or path}",
        brand=brand_id,
        brand_name=brand_name,
        name=name,
        url=SITE + locale_path + quote(path),
        images=images,
        price=sale,
        original_price=max(value, sale),
        type=classify(name),
        color=color,
        rank=rank,
    )


class PradaSource(Source):
    def __init__(self, brand_id: str, brand_name: str, http: Http, category_path: str, locale_path: str = "/kr/ko", limit: int = 60):
        super().__init__(brand_id, brand_name, http, limit)
        self.url = SITE + locale_path + category_path
        self.locale_path = locale_path

    def fetch(self) -> list[Product]:
        hits = parse_hits(self.http.get_text(self.url))
        if not hits:
            raise RuntimeError("상품 데이터(hits)를 찾지 못함 — 페이지 구조가 바뀌었을 수 있음")
        products = []
        for hit in hits[: self.limit]:
            p = build_product(self.brand_id, self.brand_name, hit, self.locale_path, rank=len(products))
            if p and p.images:
                products.append(p)
        return products
