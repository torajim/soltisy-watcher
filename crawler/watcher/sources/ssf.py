"""SSF SHOP(삼성물산) 브랜드관 — 비이커 등.

브랜드관의 신상품 목록 HTML 과 상품 상세 HTML 을 파싱한다.
  - 목록: https://m.ssfshop.com/{shop_path}/list?dspCtgryNo=...&brandShopNo=...&brndShopId=...
          li[name=gooditem] 에 브랜드·상품명·정가·판매가·썸네일
  - 상세: https://m.ssfshop.com/{brand}/{godNo}/good
          추가 이미지({godNo}_{n}_THNAIL_ORGINL_*.jpg), 사이즈별 재고(input[name=sizeItmNo])
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..classify import classify
from ..measurements import parse_number
from ..models import Product, SizeOption
from .base import Http, Source

log = logging.getLogger(__name__)

SITE = "https://m.ssfshop.com"
IMG_RESIZE = "https://img.ssfshop.com/cmd/LB_750x1000/src/"  # 원본은 크기가 커서 CDN 리사이즈본을 쓴다

# 사이트의 표준 사이즈 구분 코드 → 사이즈 추천 유형
_STD_SIZE_TYPE = {"TOP": "top", "BOTTOM": "bottom", "SHOES": "shoes"}


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items, seen = [], set()
    for box in soup.select('li[name="gooditem"]'):
        god_no = box.get("data-prdno")
        link = box.select_one("a.godItem[href]")
        name = box.select_one(".godNm")
        if not god_no or not link or not name or god_no in seen:
            continue
        seen.add(god_no)
        brand = box.select_one(".brndNm")
        regular_el = box.select_one(".rtlPrc")
        regular = parse_number(regular_el.get_text(" ", strip=True)) if regular_el else None
        sale_el = box.select_one(".lastSalePrc")
        if sale_el:
            for em in sale_el.select("em"):  # 할인율(%) 표기는 빼고 금액만
                em.decompose()
        sale = parse_number(sale_el.get_text(" ", strip=True)) if sale_el else None
        img = box.select_one(".img img")
        prices = [int(p) for p in (regular, sale) if p and p >= 100]
        items.append(
            {
                "god_no": god_no,
                "name": name.get_text(" ", strip=True),
                "sub_brand": brand.get_text(" ", strip=True) if brand else "",
                "url": SITE + link["href"],
                "thumb": img["src"] if img and img.get("src") else "",
                "price": min(prices) if prices else 0,
                "original_price": max(prices) if prices else 0,
            }
        )
    return items


def parse_images(html: str, god_no: str) -> list[str]:
    """상세의 원본 이미지들을 순번대로, CDN 리사이즈 주소로."""
    found: dict[int, str] = {}
    for m in re.finditer(rf"https://img\.ssfshop\.com/goods/[^\"'\s)]+?/{god_no}_(\d+)_[A-Z_]+_\d+\.jpg", html):
        found.setdefault(int(m.group(1)), m.group(0))
    return [IMG_RESIZE + found[k] for k in sorted(found)]


def parse_sizes(html: str) -> tuple[list[SizeOption], str | None]:
    """[(사이즈, 재고)] 와 사이트의 표준 사이즈 구분(MALE_TOP 등)으로 정한 유형."""
    soup = BeautifulSoup(html, "html.parser")
    sizes = []
    for el in soup.select('input[name="sizeItmNo"]'):
        label = (el.get("sizeitmnm") or "").strip()
        if not label:
            continue
        stock = int(parse_number(el.get("onlineusefulinvqty") or "0") or 0)
        aliases = []
        if label.isdigit() and label.lstrip("0") and label.lstrip("0") != label:
            aliases.append(label.lstrip("0"))  # "002" → "2"
        sizes.append(SizeOption(label=label, aliases=aliases, in_stock=stock > 0 and el.get("itmstatcd") == "SALE_PROGRS"))
    sect = soup.select_one('input[name="sizeStdSizeSectCd"]')
    kind = None
    if sect and sect.get("value"):
        kind = next((t for key, t in _STD_SIZE_TYPE.items() if key in sect["value"].upper()), None)
    return sizes, kind


def build_product(brand_id: str, brand_name: str, item: dict, detail_html: str | None, rank: int) -> Product:
    images = parse_images(detail_html, item["god_no"]) if detail_html else []
    if not images and item.get("thumb"):
        images = [item["thumb"]]
    sizes, kind = parse_sizes(detail_html) if detail_html else ([], None)
    sub = item.get("sub_brand") or ""
    return Product(
        id=f"{brand_id}:{item['god_no']}",
        brand=brand_id,
        brand_name=f"{sub} · {brand_name}" if sub and sub.upper() != brand_name.upper() else brand_name,
        name=item["name"],
        url=item["url"],
        images=images,
        price=item["price"],
        original_price=item["original_price"],
        type=kind or classify(item["name"]),
        sizes=sizes,
        rank=rank,
    )


class SsfSource(Source):
    def __init__(
        self, brand_id: str, brand_name: str, http: Http, shop_path: str, category_no: str, brand_shop_no: str, brand_shop_id: str, limit: int = 60
    ):
        super().__init__(brand_id, brand_name, http, limit)
        self.list_url = f"{SITE}/{shop_path.strip('/')}/list"
        self.params = {"dspCtgryNo": category_no, "brandShopNo": brand_shop_no, "brndShopId": brand_shop_id}

    def fetch(self) -> list[Product]:
        items = parse_list(self.http.get_text(self.list_url, params=self.params))[: self.limit]  # 한 페이지 60개, 신상품순
        products = []
        for item in items:
            try:
                html = self.http.get_text(item["url"])
            except Exception as e:
                log.warning("상세 실패 %s: %s", item["god_no"], e)
                html = None
            p = build_product(self.brand_id, self.brand_name, item, html, rank=len(products))
            if p.images:
                products.append(p)
        return products
