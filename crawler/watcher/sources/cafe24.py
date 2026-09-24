"""Cafe24 기반 자체몰 — 솔리드옴므 등.

'신상품' 카테고리 목록 HTML 과 상품 상세 HTML 을 파싱한다.
상세 페이지에는 옵션 재고(option_stock_data)와 Size Guide 표가 들어 있다
(Size Guide 표는 HTML 주석 안에 있어서 정규식으로 잘라낸 뒤 파싱한다).
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..classify import classify
from ..measurements import normalize_all, parse_number
from ..models import Product, SizeOption
from .base import Http, Source

log = logging.getLogger(__name__)

_PRODUCT_NO = re.compile(r"product_no=(\d+)")


def parse_list(html: str, base_url: str, cate_no: int) -> list[dict]:
    """목록 페이지 → [{product_no, name, url, thumb, price, original_price}] (페이지 표시 순서)."""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    seen: set[str] = set()
    for box in soup.select(".xans-product-listnormal li.xans-record-"):
        link = box.select_one(f'a[href*="product_no="][href*="cate_no={cate_no}"]') or box.select_one('a[href*="product_no="]')
        name_el = box.select_one(".name")
        if not link or not name_el:
            continue
        m = _PRODUCT_NO.search(link["href"])
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        prices = [parse_number(t) for t in (box.select_one(".price") or box).stripped_strings if "KRW" in t or "원" in t]
        prices = [int(p) for p in prices if p]
        img = box.select_one("img.first-img") or box.select_one("img")
        items.append(
            {
                "product_no": m.group(1),
                "name": name_el.get_text(" ", strip=True),
                "url": f"{base_url}/product/detail.html?product_no={m.group(1)}&cate_no={cate_no}",
                "thumb": urljoin(base_url, img["src"]) if img and img.get("src") else "",
                "price": min(prices) if prices else 0,
                "original_price": max(prices) if prices else 0,
                "soldout": bool(box.select_one(".thumbnail-soldout:not(.displaynone)")),
            }
        )
    return items


def _js_json_var(html: str, name: str) -> dict | None:
    m = re.search(rf"var {name}\s*=\s*'(.*?)';", html, re.S)
    if not m:
        return None
    raw = m.group(1)
    try:
        # JS 문자열 리터럴 안의 JSON: \" 와 \uXXXX 이스케이프를 풀어준다
        return json.loads(json.loads(f'"{raw}"'))
    except (json.JSONDecodeError, ValueError):
        log.warning("%s 파싱 실패", name)
        return None


def parse_options(html: str) -> list[tuple[str, bool]]:
    """[(사이즈, 재고있음)] — 옵션이 없으면 빈 리스트."""
    data = _js_json_var(html, "option_stock_data")
    if not data:
        return []
    out = []
    for v in data.values():
        if v.get("is_display") == "F":
            continue
        label = str(v.get("option_value") or "").strip()
        if not label:
            continue
        stock = v.get("stock_number")
        in_stock = v.get("is_selling") == "T" and (stock is None or not v.get("use_stock") or stock > 0)
        out.append((label, in_stock))
    return out


def parse_size_table(html: str) -> dict[str, dict[str, float]]:
    """Size Guide 표 → {사이즈: {공통 키: 값}}."""
    i = html.find("Size Guide")
    if i < 0:
        return {}
    j = html.find("<table", i)
    k = html.find("</table>", j)
    if j < 0 or k < 0 or j - i > 2000:
        return {}
    table = BeautifulSoup(html[j : k + 8], "html.parser")
    rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in table.find_all("tr")]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        return {}
    header = rows[0]
    out: dict[str, dict[str, float]] = {}
    for r in rows[1:]:
        if not r or not r[0]:
            continue
        pairs = [(h, parse_number(v)) for h, v in zip(header[1:], r[1:]) if parse_number(v) is not None]
        m = normalize_all(pairs)
        if m:
            out[r[0].strip()] = m
    return out


def parse_images(html: str) -> list[str]:
    """상세 이미지(추가 이미지 슬라이드) — 작은 썸네일 경로를 큰 이미지 경로로 바꾼다."""
    soup = BeautifulSoup(html, "html.parser")
    images: list[str] = []
    for meta in soup.select('meta[property="og:image"]'):
        if meta.get("content"):
            images.append(meta["content"])
            break
    block = soup.select_one(".xans-product-addimage")
    for img in (block.select("img") if block else []):
        src = img.get("src") or ""
        if "/extra/small/" in src:
            images.append(src.replace("/extra/small/", "/extra/big/"))
    out: list[str] = []
    for src in images:
        src = "https:" + src if src.startswith("//") else src
        if src not in out:
            out.append(src)
    return out


def parse_description(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.select_one('meta[property="og:description"]') or soup.select_one('meta[name="description"]')
    return meta.get("content", "") if meta else ""


def build_product(brand_id: str, brand_name: str, item: dict, detail_html: str | None, rank: int) -> Product:
    options = parse_options(detail_html) if detail_html else []
    table = parse_size_table(detail_html) if detail_html else {}
    images = parse_images(detail_html) if detail_html else []
    if not images and item.get("thumb"):
        images = [item["thumb"]]

    sizes = [SizeOption(label=label, in_stock=ok and not item.get("soldout"), measurements=table.get(label, {})) for label, ok in options]
    mkeys = {k for m in table.values() for k in m}
    return Product(
        id=f"{brand_id}:{item['product_no']}",
        brand=brand_id,
        brand_name=brand_name,
        name=item["name"],
        url=item["url"],
        images=images,
        price=item["price"],
        original_price=item["original_price"],
        type=classify(item["name"], measurement_keys=mkeys),
        category="",
        color="",
        sizes=sizes,
        size_note="실측 (cm)" if table else "",
        rank=rank,
    )


class Cafe24Source(Source):
    def __init__(self, brand_id: str, brand_name: str, http: Http, base_url: str, new_category_no: int, limit: int = 60):
        super().__init__(brand_id, brand_name, http, limit)
        self.base_url = base_url.rstrip("/")
        self.cate_no = new_category_no

    def list_items(self) -> list[dict]:
        items: list[dict] = []
        seen: set[str] = set()
        page = 1
        while len(items) < self.limit and page <= 10:
            html = self.http.get_text(f"{self.base_url}/product/list.html", params={"cate_no": self.cate_no, "page": page})
            batch = [it for it in parse_list(html, self.base_url, self.cate_no) if it["product_no"] not in seen]
            if not batch:
                break
            seen.update(it["product_no"] for it in batch)
            items.extend(batch)
            if f"page={page + 1}" not in html:
                break
            page += 1
        return items[: self.limit]

    def fetch(self) -> list[Product]:
        products = []
        for item in self.list_items():
            try:
                html = self.http.get_text(f"{self.base_url}/product/detail.html", params={"product_no": item["product_no"], "cate_no": self.cate_no})
            except Exception as e:
                log.warning("상세 실패 %s: %s", item["product_no"], e)
                html = None
            p = build_product(self.brand_id, self.brand_name, item, html, rank=len(products))
            if p.images:
                products.append(p)
        return products
