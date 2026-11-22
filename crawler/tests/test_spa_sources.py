"""ZARA · UNIQLO · 더현대Hi(PEER) · COOR(Cafe24 텍스트 실측) 파서 테스트. 픽스처는 2026-11-22 실제 응답."""
import json
from pathlib import Path

from watcher.sources import cafe24, thehyundai, uniqlo, zara

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text("utf-8"))


# ---------- ZARA ----------


def test_zara_list_skips_marketing_bundles():
    data = load("zara_list.json")
    raw = [c for g in data["productGroups"] for e in g["elements"] for c in e.get("commercialComponents") or []]
    comps = zara.list_products(data)
    assert any(c["type"] == "Bundle" for c in raw)
    assert comps and all(c["type"] == "Product" for c in comps)
    assert len({c["id"] for c in comps}) == len(comps)


def test_zara_build_product_from_detail():
    comp = zara.list_products(load("zara_list.json"))[0]
    p = zara.build_product("zara", "ZARA", comp, load("zara_detail.json"), rank=0)
    assert p.id == f"zara:{comp['id']}"
    assert p.url.startswith("https://www.zara.com/kr/ko/") and f"-p{comp['seo']['seoProductId']}.html?v1=" in p.url
    assert p.price == 329900
    assert p.type == "top"
    assert p.images and all(u.startswith("https://static.zara.net/") and "{width}" not in u for u in p.images)
    assert not any(u.endswith(".m3u8") for u in p.images)
    s = p.sizes[0]
    assert (s.label, s.aliases, s.in_stock) == ("S", ["KR 90"], True)


def test_zara_parse_size():
    assert zara.parse_size("M (KR 95-100)") == ("M", ["KR 95-100"])
    assert zara.parse_size("M (M)") == ("M", [])
    assert zara.parse_size("42") == ("42", [])


# ---------- UNIQLO ----------


def test_uniqlo_skips_coming_soon():
    items = load("uniqlo_list.json")["result"]["items"]
    assert "comingSoon" in uniqlo._flags(items[0])
    assert "comingSoon" not in uniqlo._flags(items[2])


def test_uniqlo_build_product_with_stock():
    item = load("uniqlo_list.json")["result"]["items"][2]
    p = uniqlo.build_product("uniqlo", "UNIQLO", item, load("uniqlo_l2s.json")["result"], rank=0)
    assert p.id == "uniqlo:E491662-000"
    assert p.url.startswith("https://www.uniqlo.com/kr/ko/products/E491662-000/00?colorDisplayCode=")
    assert p.type == "top"  # 블루종
    labels = [s.label for s in p.sizes]
    assert labels[:3] == ["XS", "S", "M"]
    assert len(labels) == len(set(labels))
    assert p.images[0].startswith("https://image.uniqlo.com/")


def test_uniqlo_sizes_without_stock_api():
    item = load("uniqlo_list.json")["result"]["items"][2]
    sizes = uniqlo.parse_sizes(item, None, "", "")
    assert [s.label for s in sizes][:2] == ["XS", "S"]


# ---------- 더현대Hi (PEER) ----------


def test_thehyundai_build_product():
    items = load("thehyundai_list.json")["data"]["productList"]["productInfoList"]
    stock = load("thehyundai_stock.json")["data"]
    p = thehyundai.build_product("peer", "PEER", items[0], stock, rank=0)
    assert p.url == f"https://hi.thehyundai.com/product/{items[0]['slitmCd']}"
    assert p.images[0].startswith("https://image.thehyundai.com/")
    assert p.type == "top"  # 재킷/점퍼
    assert p.brand_name.endswith(" · PEER")
    assert [s.label for s in p.sizes] == ["M", "L", "XL"]
    assert p.color == "네이비"
    assert p.price <= p.original_price


def test_thehyundai_clean_name():
    assert thehyundai.clean_name("[WELTER EXPERIMENT] 웰터익스페리먼트 패커블 백오렌지 / W1D5HB0002OR") == "웰터익스페리먼트 패커블 백오렌지"
    assert thehyundai.clean_name("나일론 푸퍼 자켓 네이비") == "나일론 푸퍼 자켓 네이비"


# ---------- COOR (Cafe24) ----------


def test_coor_list_drops_hidden_name_label():
    items = cafe24.parse_list((FIX / "coor_list.html").read_text("utf-8"), "https://www.coor.kr", 94)
    assert items[0]["name"] == "코듀로이 트림 헤어리 체스터필드 코트 (블랙)"
    assert items[0]["price"] == 470000


def test_coor_text_measurements():
    item = cafe24.parse_list((FIX / "coor_list.html").read_text("utf-8"), "https://www.coor.kr", 94)[0]
    p = cafe24.build_product("coor", "COOR", item, (FIX / "coor_detail.html").read_text("utf-8"), rank=0)
    m = {s.label: s.measurements for s in p.sizes}
    assert m["S"] == {"length": 107.5, "chest": 56.5, "shoulder": 49.0, "sleeve": 62.4}
    assert p.size_note == "실측 (cm)"


def test_size_lines_one_size():
    html = "<table><tr><td>SIZE 'CM'<br>총장 79.5 가슴 60 어깨 52.5 소매 58.5</td></tr></table>"
    assert cafe24.parse_size_lines(html) == {cafe24.ONE_SIZE: {"length": 79.5, "chest": 60.0, "shoulder": 52.5, "sleeve": 58.5}}
