"""칼하트WIP · 아더에러 파서 테스트. 픽스처는 2026-11-25 실제 응답 (긴 HTML·SVG 필드는 비움)."""
import json
from pathlib import Path

from watcher.measurements import normalize_all
from watcher.sources import adererror, carhartt

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text("utf-8"))


# ---------- CARHARTT WIP ----------


def test_carhartt_build_product_with_measurements():
    item = load("carhartt_list.json")["payload"]["content"][0]
    detail = load("carhartt_detail.json")["payload"]
    p = carhartt.build_product("carhartt", "CARHARTT WIP", item, detail, rank=0)
    assert p.id == "carhartt:336449"
    assert p.url == "https://www.carhartt-wip.co.kr/products/336449"
    assert p.name == "OG SANTA FE JACKET"
    assert p.color == "BLACK/BLACK STONE CANVAS"
    assert p.type == "top"
    assert p.price == p.original_price == 468000
    assert p.images[0].endswith("-1.jpg") and len(p.images) == len(set(p.images))
    assert [s.label for s in p.sizes] == ["XS", "S", "M", "L", "XL"]
    assert p.sizes[0].measurements == {"chest": 57.0, "sleeve": 64.0, "length": 64.0, "shoulder": 47.0}
    assert p.size_note == "실측 (cm)"


def test_carhartt_sizes_without_detail():
    item = load("carhartt_list.json")["payload"]["content"][0]
    p = carhartt.build_product("carhartt", "CARHARTT WIP", item, None, rank=0)
    assert [s.label for s in p.sizes] == ["XS", "S", "M", "L", "XL"]
    assert p.images == [item["thumbnailUrl"]]


# ---------- ADER ERROR ----------


def test_adererror_list_dedupes_grid_cells():
    data = load("adererror_list.json")["data"]
    raw = [g["product_idx"] for g in data["grid_info"]]
    items = adererror.list_products(data)
    assert len(raw) > len(items)
    assert [g["product_idx"] for g in items] == list(dict.fromkeys(raw))


def test_adererror_build_product_with_sizeguide():
    item = adererror.list_products(load("adererror_list.json")["data"])[0]
    resp = load("adererror_detail.json")
    p = adererror.build_product("adererror", "ADER ERROR", item, resp["data"], resp["sizeguide"][0], rank=0)
    assert p.id == "adererror:6091"
    assert p.url == "https://www.adererror.com/kr/shop/6091"
    assert p.price == p.original_price == 520000
    assert p.type == "top"
    assert p.images[0].startswith(adererror.CDN)
    assert [s.label for s in p.sizes] == ["XS", "S", "M", "L", "XL"]
    assert p.sizes[0].measurements == {"length": 64.0, "chest": 54.0, "shoulder": 41.0, "sleeve": 60.0}
    assert all(s.in_stock for s in p.sizes)  # STCL(품절 임박)도 구매 가능


def test_adererror_price_text():
    assert adererror._price("1,280,000") == 1280000
    assert adererror._price("") == 0


# ---------- 실측 항목명 ----------


def test_measurement_names_with_english_note():
    got = normalize_all(
        [("총 기장 [TOTAL LENGTH]", 64), ("소매길이 [SLEEVE LENGTH]", 64), ("허리 [WAIST WIDTH]", 40), ("밑단 [HEM WIDTH]", 24), ("인심 [INSEAM]", 70)]
    )
    assert got == {"length": 64.0, "sleeve": 64.0, "waist": 40.0, "hem": 24.0}
    assert normalize_all([("소매장", 60), ("소매입구", 11), ("앞밑위", 29)]) == {"sleeve": 60.0, "rise": 29.0}
