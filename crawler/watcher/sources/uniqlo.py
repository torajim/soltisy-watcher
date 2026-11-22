"""유니클로(uniqlo.com/kr) — 사이트 프론트엔드가 쓰는 commerce API(JSON)를 읽는다.

HTML 페이지는 봇 차단(Akamai)으로 막혀 있지만 API 는 열려 있다.
  - 목록: /kr/api/commerce/v5/ko/products?path={성별 id},,&sort=1 (sort=1 → 신상품순)
          성별 id: WOMEN 57892, MEN 57893 (응답의 aggregations.tree.genders)
  - 재고: /kr/api/commerce/v5/ko/products/{productId}/price-groups/{priceGroup}/l2s?withStocks=true
판매 예정(comingSoon) 상품은 건너뛴다. 실측표는 HTML 이라 가져오지 않는다.
"""
from __future__ import annotations

import logging

from ..classify import classify
from ..models import Product, SizeOption
from .base import Http, Source

log = logging.getLogger(__name__)

SITE = "https://www.uniqlo.com"
API = f"{SITE}/kr/api/commerce/v5/ko"
PAGE_SIZE = 50
MAX_IMAGES = 8


def _flags(item: dict) -> set[str]:
    flags = ((item.get("representative") or {}).get("flags") or {}).get("productFlags") or []
    return {f.get("code") for f in flags}


def images(item: dict, color_code: str) -> list[str]:
    imgs = item.get("images") or {}
    main = (imgs.get("main") or {}).get(color_code) or next(iter((imgs.get("main") or {}).values()), {})
    urls = [main.get("image")] if main.get("image") else []
    urls += [s.get("image") for s in imgs.get("sub") or [] if s.get("image")]
    return urls[:MAX_IMAGES]


def parse_sizes(item: dict, l2s: dict | None, color_code: str, pld_code: str) -> list[SizeOption]:
    names = {s.get("code"): s.get("name") for s in item.get("sizes") or []}
    if not l2s:
        return [SizeOption(label=n) for n in names.values() if n]
    stocks = l2s.get("stocks") or {}
    sizes: list[SizeOption] = []
    seen: set[str] = set()
    for l2 in l2s.get("l2s") or []:
        if (l2.get("color") or {}).get("code") != color_code:
            continue
        if pld_code and (l2.get("pld") or {}).get("code") != pld_code:
            continue
        code = (l2.get("size") or {}).get("code")
        label = names.get(code) or ""  # 목록에 없는 사이즈 코드는 판매하지 않는 조합이다
        if not label or label in seen:
            continue
        seen.add(label)
        stock = stocks.get(l2.get("l2Id")) or {}
        in_stock = l2.get("sales", True) and stock.get("statusCode") in ("IN_STOCK", "LOW_STOCK")
        sizes.append(SizeOption(label=label, in_stock=bool(in_stock)))
    return sizes


def build_product(brand_id: str, brand_name: str, item: dict, l2s: dict | None, rank: int) -> Product:
    rep = item.get("representative") or {}
    color = rep.get("color") or (item.get("colors") or [{}])[0]
    color_code = color.get("code") or ""
    display_code = color.get("displayCode") or ""
    pld_code = (rep.get("pld") or {}).get("code") or ""
    prices = item.get("prices") or {}
    base = int(((prices.get("base") or {}).get("value")) or 0)
    promo = int(((prices.get("promo") or {}).get("value")) or base)
    pid, group = item["productId"], item.get("priceGroup") or "00"
    name = item.get("name") or ""
    return Product(
        id=f"{brand_id}:{pid}",
        brand=brand_id,
        brand_name=brand_name,
        name=name,
        url=f"{SITE}/kr/ko/products/{pid}/{group}?colorDisplayCode={display_code}",
        images=images(item, display_code),
        price=min(promo, base) if base else promo,
        original_price=base,
        type=classify(name),
        color=color.get("name") or "",
        sizes=parse_sizes(item, l2s, color_code, pld_code),
        rank=rank,
    )


class UniqloSource(Source):
    def __init__(self, brand_id: str, brand_name: str, http: Http, gender_path: str, limit: int = 60):
        super().__init__(brand_id, brand_name, http, limit)
        self.gender_path = gender_path

    def list_items(self) -> list[dict]:
        items: list[dict] = []
        offset = 0
        while len(items) < self.limit:
            data = self.http.get_json(
                f"{API}/products",
                params={"path": f"{self.gender_path},,", "sort": 1, "limit": PAGE_SIZE, "offset": offset, "httpFailure": "true"},
            )
            result = data.get("result") or {}
            batch = result.get("items") or []
            items.extend(i for i in batch if "comingSoon" not in _flags(i))
            offset += len(batch)
            if len(batch) < PAGE_SIZE or offset >= (result.get("pagination") or {}).get("total", 0):
                break
        return items[: self.limit]

    def fetch(self) -> list[Product]:
        products: list[Product] = []
        for item in self.list_items():
            pid, group = item["productId"], item.get("priceGroup") or "00"
            try:
                l2s = self.http.get_json(
                    f"{API}/products/{pid}/price-groups/{group}/l2s", params={"withPrices": "true", "withStocks": "true", "httpFailure": "true"}
                ).get("result")
            except Exception as e:  # 재고 하나 실패로 전체를 버리지 않는다
                log.warning("uniqlo %s 재고 실패: %s", pid, e)
                l2s = None
            p = build_product(self.brand_id, self.brand_name, item, l2s, rank=len(products))
            if p.images:
                products.append(p)
        return products
