"""더한섬닷컴(thehandsome.com) 입점 브랜드 — 타임옴므, 시스템옴므 등.

사이트 프론트엔드가 쓰는 공개 JSON API 를 사용한다.
  - 목록: /api/display/1/ko/category/categoryGoodsList (sortGbn=10 → 신상품순)
  - 상세: /api/goods/1/ko/goods/{goodsNo}           (색상별 사이즈/재고)
  - 실측: /api/goods/1/ko/goods/{goodsNo}/actualSizes
"""
from __future__ import annotations

import logging

from ..classify import classify
from ..measurements import normalize_all
from ..models import Product, SizeOption
from .base import Http, Source

log = logging.getLogger(__name__)

SITE = "https://www.thehandsome.com"
API = f"{SITE}/api"
IMG = "https://cdn-img.thehandsome.com/studio/goods"
PAGE_SIZE = 20  # API 가 고정으로 20개씩 준다
WOMEN_CATEGORY = "여성"


def image_url(path: str) -> str:
    return path if path.startswith("http") else IMG + path


def pick_color(goods: dict) -> dict | None:
    colors = goods.get("colorInfo") or []
    for c in colors:
        if c.get("repYn") == "Y":
            return c
    return colors[0] if colors else None


def images_from_color(color: dict) -> list[str]:
    """P01.. (모바일용 리사이즈 컷) 순서대로, 없으면 W01.., 그것도 없으면 대표컷."""
    conts = sorted(color.get("colorContInfo") or color.get("contentList") or [], key=lambda c: c.get("imgGbCd", ""))

    def path_of(c):
        return c.get("dispGoodsContUrl") or c.get("contFilePathNm")

    for prefix in ("P", "W", "T"):
        paths = [path_of(c) for c in conts if (c.get("imgGbCd") or "").startswith(prefix) and path_of(c)]
        if paths:
            if prefix == "W":
                paths = [p if "?" in p else p + "?rs=684X1032" for p in paths]
            return [image_url(p) for p in paths]
    return []


def parse_sizes(detail: dict, actual: dict | None, color_code: str) -> tuple[list[SizeOption], str]:
    colors = detail.get("colorList") or []
    color = next((c for c in colors if c.get("erpColorCd") == color_code), colors[0] if colors else None)
    if color is None:
        return [], ""

    measured: dict[str, tuple[dict, str]] = {}
    note = ""
    if actual:
        note = actual.get("acmantSzAddDesc") or ""
        for s in actual.get("sizeList") or []:
            pairs = [(a["acmantSzNm"], a["acmantSzVal"]) for a in s.get("acmantSzList") or []]
            measured[str(s.get("erpSzCd"))] = (normalize_all(pairs), str(s.get("onlSzCd") or ""))

    sizes = []
    for s in color.get("sizeList") or []:
        label = str(s.get("erpSzCd") or s.get("onlSzCd") or "")
        m, alpha = measured.get(label, ({}, ""))
        aliases = []
        for a in (alpha, s.get("onlSzCd"), s.get("koreaSz")):
            a = str(a or "").strip()
            if a and a != label and a not in aliases:
                aliases.append(a)
        in_stock = (s.get("stkQty") or 0) > 0 and s.get("statCd", "10") == "10"
        sizes.append(SizeOption(label=label, aliases=aliases, in_stock=in_stock, measurements=m))
    return sizes, note


def build_product(brand_id: str, brand_name: str, goods: dict, detail: dict | None, actual: dict | None, rank: int) -> Product | None:
    color = pick_color(goods)
    if color is None:
        return None
    goods_no = goods["goodsNo"]
    itm_no = color.get("repItmNo") or "001"
    if detail:
        for c in detail.get("colorList") or []:
            if c.get("erpColorCd") == color.get("optnNo"):
                itm_no = c.get("itmNo") or itm_no

    categories = [c.get("dispCtgNm") or "" for c in (detail or {}).get("dispCtgList") or []]
    sizes, note = parse_sizes(detail, actual, color.get("optnNo")) if detail else ([], "")
    item_kind = (actual or {}).get("itemGbNm") or ""
    mkeys = {k for s in sizes for k in s.measurements}
    ptype = classify(*reversed(categories), item_kind, goods.get("goodsNm", ""), measurement_keys=mkeys)

    return Product(
        id=f"{brand_id}:{goods_no}",
        brand=brand_id,
        brand_name=brand_name,
        name=goods.get("goodsNm", ""),
        url=f"{SITE}/ko/PM/productDetail/{goods_no}?itmNo={itm_no}",
        images=images_from_color(color),
        price=int(goods.get("salePrc") or 0),
        original_price=int(goods.get("norPrc") or goods.get("salePrc") or 0),
        type=ptype,
        category=categories[-1] if categories else item_kind,
        color=color.get("optnNm") or color.get("onlColorCd") or "",
        sizes=sizes,
        size_note=note,
        rank=rank,
    )


class TheHandsomeSource(Source):
    def __init__(self, brand_id: str, brand_name: str, http: Http, brand_no: str, limit: int = 60):
        super().__init__(brand_id, brand_name, http, limit)
        self.brand_no = brand_no

    def list_goods(self) -> list[dict]:
        goods: list[dict] = []
        page = 1
        while len(goods) < self.limit:
            data = self.http.get_json(
                f"{API}/display/1/ko/category/categoryGoodsList",
                params={
                    "brandNo": self.brand_no,
                    "mainBrand": self.brand_no,
                    "mainCategory": "10000001",
                    "norOutletGbCd": "J",  # 정상 상품 (아울렛 제외)
                    "sortGbn": "10",  # 신상품순
                    "soutYn": "Y",  # 품절 상품 제외
                    "pageNo": page,
                },
            )
            if data.get("code") != "0000":
                raise RuntimeError(f"더한섬 목록 API 오류: {data.get('code')} {data.get('message')}")
            batch = (data.get("payload") or {}).get("goodsList") or []
            goods.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            page += 1
        return goods

    def _payload(self, url: str) -> dict | None:
        try:
            data = self.http.get_json(url)
        except Exception as e:  # 상세 하나 실패로 전체를 버리지 않는다
            log.warning("%s: %s", url, e)
            return None
        return data.get("payload") if data.get("code") == "0000" else None

    def fetch(self) -> list[Product]:
        products: list[Product] = []
        for goods in self.list_goods():
            if len(products) >= self.limit:
                break
            goods_no = goods["goodsNo"]
            detail = self._payload(f"{API}/goods/1/ko/goods/{goods_no}")
            categories = [c.get("dispCtgNm") for c in (detail or {}).get("dispCtgList") or []]
            if categories and categories[0] == WOMEN_CATEGORY:
                continue  # 옴므 브랜드에 섞여 있는 여성 라인은 제외
            actual = self._payload(f"{API}/goods/1/ko/goods/{goods_no}/actualSizes")
            p = build_product(self.brand_id, self.brand_name, goods, detail, actual, rank=len(products))
            if p and p.images:
                products.append(p)
        return products
