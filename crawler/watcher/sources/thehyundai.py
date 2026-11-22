"""더현대Hi(hi.thehyundai.com) 브랜드관 — 현대백화점 편집숍 PEER 등.

사이트 프론트엔드가 쓰는 공개 JSON API 를 사용한다. 같은 사이트에서 온 요청처럼 Referer 와
x-device-type 헤더를 붙여야 응답한다 (없으면 500 HTML).
  - 목록: /proxy/v1/dp/search/searchResult?target=brand&targetCode={브랜드 코드}&sort=dtm (최신상품순)
          flSex=1 남성 / 2 여성, flCate=400003 패션
  - 재고: /proxy/v1/pd/item/uitm/uitmStckList?slitmCd={상품 코드}   ("색상/사이즈" 와 판매 가능 수량)
실측 정보는 상세 HTML 이미지라 가져오지 않는다.
"""
from __future__ import annotations

import logging
import re

from ..classify import classify
from ..models import Product, SizeOption
from .base import Http, Source

log = logging.getLogger(__name__)

SITE = "https://hi.thehyundai.com"
IMG = "https://image.thehyundai.com"
FASHION_CATEGORY = "400003"
PAGE_SIZE = 40
SEX_CODES = {"men": "1", "women": "2"}


def image_url(path: str) -> str:
    return path if path.startswith("http") else IMG + path


_BRAND_PREFIX = re.compile(r"^\s*\[[^\]]+\]\s*")
_CODE_SUFFIX = re.compile(r"\s*/\s*[A-Z0-9-]{6,}\s*$")


def clean_name(name: str) -> str:
    """'[MAISON LABICHE] 메종 라비쉬 캡 블루 / MSD4HT0001BL' → '메종 라비쉬 캡 블루'."""
    return _CODE_SUFFIX.sub("", _BRAND_PREFIX.sub("", name)).strip() or name


def parse_sizes(stock_list: list[dict] | None) -> list[SizeOption]:
    """[{uitmTotNm: 'NAVY/L', sellPossQty: 7}] → 사이즈 목록. 단품(옵션 없음)은 빈 목록."""
    sizes: list[SizeOption] = []
    seen: set[str] = set()
    for s in stock_list or []:
        name = str(s.get("uitmTotNm") or "")
        label = name.rsplit("/", 1)[-1].strip()
        if not label or label in seen:
            continue
        seen.add(label)
        sizes.append(SizeOption(label=label, in_stock=(s.get("sellPossQty") or 0) > 0))
    return sizes


def build_product(brand_id: str, brand_name: str, item: dict, stock_list: list[dict] | None, rank: int) -> Product:
    code = item["slitmCd"]
    sub = item.get("expsEngBrndNm") or item.get("operEngBrndNm") or ""
    # 편집숍은 상품마다 실제 브랜드를 앞에 붙여 보여준다 (예: "SPORTY AND RICH · PEER")
    display = f"{sub} · {brand_name}" if sub and sub.upper() != brand_name.upper() else brand_name
    price = int(item.get("bnftPrc") or item.get("sellPrc") or 0)
    names = [item.get(k) or "" for k in ("itemScsfNm", "itemMcsfNm", "itemDcsfNm")]
    color = ""
    if stock_list:
        color = str(stock_list[0].get("uitmTotNm") or "").rsplit("/", 1)[0] if "/" in str(stock_list[0].get("uitmTotNm") or "") else ""
    return Product(
        id=f"{brand_id}:{code}",
        brand=brand_id,
        brand_name=display,
        name=clean_name(item.get("slitmNm") or ""),
        url=f"{SITE}/product/{code}",
        images=[image_url(item["itemImageUrl"])] if item.get("itemImageUrl") else [],
        price=price,
        original_price=max(int(item.get("sellPrc") or price), price),
        type=classify(*names, item.get("slitmNm") or ""),
        category=names[0],
        color=color,
        sizes=parse_sizes(stock_list),
        rank=rank,
    )


class TheHyundaiSource(Source):
    def __init__(self, brand_id: str, brand_name: str, http: Http, brand_code: str, sect_id: int, sex: str = "", limit: int = 60):
        super().__init__(brand_id, brand_name, http, limit)
        self.brand_code = brand_code
        self.sect_id = sect_id  # 브랜드관 페이지 번호 (hi.thehyundai.com/brand/{sect_id}), Referer 용
        self.sex = SEX_CODES.get(sex, sex)

    def _headers(self, referer: str) -> dict:
        return {"Accept": "application/json, text/plain, */*", "x-device-type": "pc", "x-domain-type": "search", "Referer": referer}

    def list_items(self) -> list[dict]:
        items: list[dict] = []
        page = 1
        while len(items) < self.limit:
            params = {
                "target": "brand",
                "targetCode": self.brand_code,
                "searchType": "NCP_PRODUCT",
                "flCate": FASHION_CATEGORY,
                "sort": "dtm",  # 최신상품순
                "page": page,
                "disPlaySize": PAGE_SIZE,
            }
            if self.sex:
                params["flSex"] = self.sex
            data = self.http.get_json(
                f"{SITE}/proxy/v1/dp/search/searchResult", params=params, headers=self._headers(f"{SITE}/brand/{self.sect_id}")
            )
            if data.get("result") != "SUCCESS":
                raise RuntimeError(f"더현대Hi 목록 API 오류: {data.get('messageCode')} {data.get('message')}")
            batch = (((data.get("data") or {}).get("productList") or {}).get("productInfoList")) or []
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            page += 1
        return items[: self.limit]

    def fetch(self) -> list[Product]:
        products: list[Product] = []
        for item in self.list_items():
            if item.get("ostkYn") == "1":
                continue  # 품절
            if "키즈" in (item.get("slitmNm") or "") or "아동" in (item.get("itemLcsfNm") or ""):
                continue  # 편집숍에 섞여 있는 아동 상품
            code = item["slitmCd"]
            try:
                data = self.http.get_json(
                    f"{SITE}/proxy/v1/pd/item/uitm/uitmStckList", params={"slitmCd": code}, headers=self._headers(f"{SITE}/product/{code}")
                )
                stock = data.get("data") if data.get("result") == "SUCCESS" else None
            except Exception as e:  # 재고 하나 실패로 전체를 버리지 않는다
                log.warning("thehyundai %s 재고 실패: %s", code, e)
                stock = None
            p = build_product(self.brand_id, self.brand_name, item, stock, rank=len(products))
            if p.images:
                products.append(p)
        return products
