"""아더에러(adererror.com/kr) — 자체몰 프론트엔드가 쓰는 /_api/ JSON 을 읽는다. 요청에 country 헤더가 필요하다.

  - 목록: /_api/goods/get?header_idx={메뉴 번호}&param_sort=NEW&last_idx={이미 받은 칸 수}
          메뉴 번호는 /_api/menu/get 의 상단 메뉴(남성·여성 > 의류 > 전체보기 등)에서 확인
          grid_info 에 상품(PRD) 외 배너 칸이 섞여 있고, 같은 상품이 큰 칸·작은 칸으로 여러 번 나올 수 있다.
  - 상세: /_api/goods/detail/get?product_idx=  → sizeguide[0].dimensions 에 사이즈별 실측
"""
from __future__ import annotations

import logging

from ..classify import classify
from ..measurements import normalize_all
from ..models import Product, SizeOption
from .base import Http, Source

log = logging.getLogger(__name__)

SITE = "https://www.adererror.com"
API = f"{SITE}/_api"
CDN = "https://d31flwjaqugbgy.cloudfront.net/s3-cloud-bucket-ader-user"
MAX_IMAGES = 8
MAX_PAGES = 15
HEADERS = {"country": "KR", "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
IN_STOCK = {"STIN", "STCL"}  # STIN 재고 있음 · STCL 품절 임박(수량 적음) · STSO 품절


def _price(text) -> int:
    digits = "".join(ch for ch in str(text or "") if ch.isdigit() or ch == ".")
    return int(float(digits)) if digits else 0


def _data(resp: dict):
    if resp.get("code") != 200:
        raise RuntimeError(f"아더에러 API 오류: {resp.get('code')} {resp.get('msg')}")
    return resp.get("data")


def list_products(data: dict) -> list[dict]:
    """grid_info → 상품 칸만, 처음 나온 순서대로 한 번씩."""
    out: list[dict] = []
    seen: set[int] = set()
    for g in (data or {}).get("grid_info") or []:
        idx = g.get("product_idx")
        if g.get("grid_type") != "PRD" or not idx or idx in seen:
            continue
        seen.add(idx)
        out.append(g)
    return out


def images(item: dict, detail: dict | None) -> list[str]:
    urls: list[str] = []
    for img in (detail or {}).get("img_main") or []:
        url = CDN + img["img_location"] if img.get("img_location") else img.get("img_url")  # 사이트도 CDN 주소를 쓴다
        if url:
            urls.append(url)
    if not urls:
        pimg = item.get("product_img") or {}
        for img in (pimg.get("product_p_img") or []) + (pimg.get("product_o_img") or []):
            if img.get("img_location"):
                urls.append(CDN + img["img_location"])
    return list(dict.fromkeys(urls))[:MAX_IMAGES]


def parse_sizes(item: dict, sizeguide: dict | None) -> list[SizeOption]:
    dims = (sizeguide or {}).get("dimensions") or {}
    sizes: list[SizeOption] = []
    seen: set[str] = set()
    for s in item.get("product_size") or []:
        label = str(s.get("option_name") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        rows = dims.get(label) if isinstance(dims, dict) else None
        pairs = [(r.get("title") or "", r.get("value")) for r in rows or [] if isinstance(r, dict)]
        sizes.append(
            SizeOption(
                label=label,
                in_stock=s.get("stock_status") in IN_STOCK,
                measurements=normalize_all((n, float(v)) for n, v in pairs if isinstance(v, (int, float))),
            )
        )
    return sizes


def build_product(brand_id: str, brand_name: str, item: dict, detail: dict | None, sizeguide: dict | None, rank: int) -> Product:
    idx = item["product_idx"]
    name = (item.get("product_name") or "").strip()
    src = detail or item  # 상세의 재고가 더 최신이다
    sizes = parse_sizes({"product_size": src.get("product_size") or item.get("product_size")}, sizeguide)
    keys = {k for s in sizes for k in s.measurements}
    price = _price(item.get("price"))
    sale = _price(item.get("sales_price")) or price
    return Product(
        id=f"{brand_id}:{idx}",
        brand=brand_id,
        brand_name=brand_name,
        name=name,
        url=f"{SITE}/kr/shop/{idx}",
        images=images(item, detail),
        price=sale,
        original_price=max(price, sale),
        type=classify(name, measurement_keys=keys),
        color=(item.get("color") or "").strip(),
        sizes=sizes,
        size_note="실측 (cm)" if keys else "",
        rank=rank,
    )


class AderErrorSource(Source):
    def __init__(self, brand_id: str, brand_name: str, http: Http, header_idx: int, limit: int = 60):
        super().__init__(brand_id, brand_name, http, limit)
        self.header_idx = header_idx

    def list_items(self) -> list[dict]:
        items: list[dict] = []
        seen: set[int] = set()
        last_idx = 0
        for _ in range(MAX_PAGES):
            if len(items) >= self.limit:
                break
            data = _data(
                self.http.get_json(
                    f"{API}/goods/get",
                    params={"header_idx": self.header_idx, "param_sort": "NEW", "last_idx": last_idx},
                    headers=HEADERS,
                )
            )
            grid = (data or {}).get("grid_info") or []
            if not grid:
                break
            new = [g for g in list_products(data) if g["product_idx"] not in seen]
            seen.update(g["product_idx"] for g in new)
            items.extend(new)
            last_idx += len(grid)
            if not new:
                break
        return items[: self.limit]

    def fetch(self) -> list[Product]:
        products: list[Product] = []
        for item in self.list_items():
            idx = item["product_idx"]
            detail = sizeguide = None
            try:
                resp = self.http.get_json(f"{API}/goods/detail/get", params={"product_idx": idx}, headers=HEADERS)
                detail = _data(resp)
                guides = resp.get("sizeguide") or []
                sizeguide = guides[0] if guides and isinstance(guides[0], dict) else None
            except Exception as e:  # 상세 하나 실패로 전체를 버리지 않는다
                log.warning("adererror %s 상세 실패: %s", idx, e)
            p = build_product(self.brand_id, self.brand_name, item, detail, sizeguide, rank=len(products))
            if p.images:
                products.append(p)
        return products
