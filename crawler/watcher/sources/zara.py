"""자라(zara.com/kr) — 카테고리 상품 목록과 상품 페이지의 ajax JSON 을 읽는다.

HTML 페이지는 봇 확인(Akamai bm-verify)이 걸려 있지만 사이트 프론트엔드가 쓰는 `?ajax=true` JSON 은 열려 있다.
  - 목록: /kr/ko/category/{category_id}/products?ajax=true   (productGroups → elements → commercialComponents)
  - 상세: /kr/ko/{seo.keyword}-p{seo.seoProductId}.html?v1={id}&ajax=true   (색상별 사이즈·재고)
카테고리 번호는 /kr/ko/categories?ajax=true 에서 찾는다 (예: 남성 THE NEW = 2544454, 여성 THE NEW = 2546081).
실측 정보는 공개 JSON 에 없어 사이즈 추천은 하지 않는다.
"""
from __future__ import annotations

import logging
import re

from ..classify import classify
from ..models import Product, SizeOption
from .base import Http, Source

log = logging.getLogger(__name__)

SITE = "https://www.zara.com"
IMAGE_WIDTH = 750
MAX_IMAGES = 8
IN_STOCK = {"in_stock", "low_on_stock"}
_SIZE_LABEL = re.compile(r"^(.*?)\s*\((.*)\)\s*$")


def list_products(data: dict) -> list[dict]:
    """목록 JSON → 상품(commercialComponents 중 type == Product) 을 화면 순서대로. 같은 상품은 한 번만."""
    out: list[dict] = []
    seen: set = set()
    for group in data.get("productGroups") or []:
        for element in group.get("elements") or []:
            for comp in element.get("commercialComponents") or []:
                if comp.get("type") != "Product" or not comp.get("seo") or comp.get("id") in seen:
                    continue
                seen.add(comp.get("id"))
                out.append(comp)
    return out


def product_path(comp: dict) -> str:
    seo = comp["seo"]
    return f"/kr/ko/{seo['keyword']}-p{seo['seoProductId']}.html?v1={seo.get('discernProductId') or comp['id']}"


def images_from_color(color: dict) -> list[str]:
    urls = []
    for media in color.get("xmedia") or []:
        url = media.get("url") or ""
        if media.get("type") != "image" or not url:
            continue
        url = url.replace("{width}", str(IMAGE_WIDTH))
        if url not in urls:
            urls.append(url)
    return urls[:MAX_IMAGES]


def parse_size(raw: str) -> tuple[str, list[str]]:
    """'M (KR 95-100)' → ('M', ['KR 95-100']), '42 (KR 270)' → ('42', ['KR 270'])."""
    m = _SIZE_LABEL.match(raw.strip())
    if m and m.group(1):
        alias = m.group(2).strip()
        return m.group(1), [alias] if alias and alias != m.group(1) else []
    return raw.strip(), []


def build_product(brand_id: str, brand_name: str, comp: dict, detail: dict | None, rank: int) -> Product | None:
    colors = ((detail or {}).get("product") or {}).get("detail", {}).get("colors") or comp.get("detail", {}).get("colors") or []
    if not colors:
        return None
    color = colors[0]
    list_color = (comp.get("detail", {}).get("colors") or [{}])[0]
    images = images_from_color(color) or images_from_color(list_color)
    sizes = []
    for s in color.get("sizes") or []:
        label, aliases = parse_size(s.get("name") or "")
        if label:
            sizes.append(SizeOption(label=label, aliases=aliases, in_stock=s.get("availability") in IN_STOCK))
    price = int(color.get("price") or comp.get("price") or 0)  # 원 단위
    original = int(color.get("oldPrice") or comp.get("oldPrice") or price)
    name = comp.get("name") or ""
    return Product(
        id=f"{brand_id}:{comp['id']}",
        brand=brand_id,
        brand_name=brand_name,
        name=name,
        url=SITE + product_path(comp),
        images=images,
        price=price,
        original_price=max(original, price),
        type=classify(comp.get("familyName") or "", name),
        category="",  # familyName 등은 'ATH Tops' 같은 내부 영문 분류라 보여주지 않는다
        color=color.get("name") or "",
        sizes=sizes,
        rank=rank,
    )


class ZaraSource(Source):
    def __init__(self, brand_id: str, brand_name: str, http: Http, category_id: int, limit: int = 60):
        super().__init__(brand_id, brand_name, http, limit)
        self.category_id = category_id

    def fetch(self) -> list[Product]:
        data = self.http.get_json(f"{SITE}/kr/ko/category/{self.category_id}/products", params={"ajax": "true"})
        products: list[Product] = []
        for comp in list_products(data):
            if len(products) >= self.limit:
                break
            try:
                detail = self.http.get_json(SITE + product_path(comp) + "&ajax=true")
            except Exception as e:  # 상세 하나 실패로 전체를 버리지 않는다 (목록 정보만으로 만든다)
                log.warning("zara %s 상세 실패: %s", comp.get("id"), e)
                detail = None
            p = build_product(self.brand_id, self.brand_name, comp, detail, rank=len(products))
            if p and p.images:
                products.append(p)
        return products
