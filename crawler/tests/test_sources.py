import json
from pathlib import Path

from watcher.__main__ import run
from watcher.sources import cafe24, thehandsome

FIX = Path(__file__).parent / "fixtures"


def load_json(name):
    return json.loads((FIX / name).read_text("utf-8"))


def read(name):
    return (FIX / name).read_text("utf-8")


# ---------- 더한섬 ----------


def test_handsome_build_product():
    goods = load_json("handsome_list.json")["payload"]["goodsList"][0]
    detail = load_json("handsome_detail.json")["payload"]
    actual = load_json("handsome_actual.json")["payload"]

    p = thehandsome.build_product("timehomme", "TIME HOMME", goods, detail, actual, rank=0)

    assert p.id == "timehomme:TH2G8WJM900M"
    assert p.name == "페이드 텍스처 투웨이 점퍼"
    assert p.type == "top"
    assert p.category == "점퍼"
    assert p.price == 955000
    assert p.url.startswith("https://www.thehandsome.com/ko/PM/productDetail/TH2G8WJM900M?itmNo=")
    assert p.images and all(u.startswith("https://cdn-img.thehandsome.com/studio/goods/") for u in p.images)
    assert "rs=684X1032" in p.images[0]

    labels = [s.label for s in p.sizes]
    assert labels == ["95", "100", "105", "110"]
    m95 = p.sizes[0]
    assert "M" in m95.aliases
    assert m95.measurements["chest"] == 67.5  # 가슴둘레 135 → 단면
    assert m95.measurements["length"] == 64.5
    assert m95.measurements["hem"] == 51.0  # 밑단둘레 102 → 단면 (소매부리 13 이 아님)
    assert p.size_note == "실측 사이즈 (105) 기준"


def test_handsome_build_product_without_detail():
    goods = load_json("handsome_list.json")["payload"]["goodsList"][0]
    p = thehandsome.build_product("timehomme", "TIME HOMME", goods, None, None, rank=3)
    assert p.sizes == [] and p.images and p.rank == 3


class FakeHttp:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def _match(self, url, params):
        self.calls.append((url, params))
        for key, value in self.routes.items():
            if key in url:
                return value(params) if callable(value) else value
        raise AssertionError(f"예상치 못한 요청: {url}")

    def get_json(self, url, params=None, **_):
        return self._match(url, params)

    def get_text(self, url, params=None, **_):
        return self._match(url, params)


def test_handsome_fetch_skips_women_and_pages():
    lst = load_json("handsome_list.json")
    detail = load_json("handsome_detail.json")
    women = json.loads(json.dumps(detail))
    women["payload"]["dispCtgList"] = [{"dispCtgNm": "여성"}, {"dispCtgNm": "팬츠"}]
    second = lst["payload"]["goodsList"][1]["goodsNo"]

    def goods_detail(_params):
        return detail

    http = FakeHttp(
        {
            "categoryGoodsList": lst,
            f"goods/{second}/actualSizes": {"code": "0000", "payload": None},
            f"goods/{second}": women,
            "actualSizes": load_json("handsome_actual.json"),
            "/goods/": goods_detail,
        }
    )
    src = thehandsome.TheHandsomeSource("timehomme", "TIME HOMME", http, brand_no="BR06", limit=10)
    products = src.fetch()

    assert [p.id for p in products] == ["timehomme:TH2G8WJM900M"]


def test_handsome_fetch_skips_goods_when_detail_fails():
    lst = load_json("handsome_list.json")
    http = FakeHttp({"categoryGoodsList": lst, "/goods/": {"code": "9999", "message": "error"}})
    src = thehandsome.TheHandsomeSource("timehomme", "TIME HOMME", http, brand_no="BR06", limit=10)
    assert src.fetch() == []
    list_call = http.calls[0]
    assert list_call[1]["sortGbn"] == "10" and list_call[1]["brandNo"] == "BR06"
    # 목록이 20개 미만이면 다음 페이지를 요청하지 않는다
    assert sum("categoryGoodsList" in u for u, _ in http.calls) == 1


# ---------- Cafe24 (솔리드옴므) ----------


def test_cafe24_parse_list():
    items = cafe24.parse_list(read("cafe24_list.html"), "https://www.solidhomme.com", 83)
    assert len(items) == 11
    first = items[0]
    assert first["product_no"] == "5804"
    assert first["name"] == "아이보리 스트라이프 카라넥 가디건"
    assert first["price"] == 478000
    assert first["url"] == "https://www.solidhomme.com/product/detail.html?product_no=5804&cate_no=83"


def test_cafe24_parse_detail():
    html = read("cafe24_detail.html")
    assert cafe24.parse_options(html) == [("46", True), ("48", True), ("50", True), ("52", True)]

    table = cafe24.parse_size_table(html)
    assert table["46"] == {"shoulder": 46.0, "chest": 57.0, "sleeve": 61.0, "length": 67.0}
    assert set(table) == {"46", "48", "50", "52"}

    images = cafe24.parse_images(html)
    assert images[0].endswith(".jpg") and "/product/big/" in images[0]
    assert len(images) == 6
    assert all("/extra/small/" not in u for u in images)


def test_cafe24_options_soldout():
    html = '<script>var option_stock_data = \'{\\"A\\":{\\"option_value\\":\\"46\\",\\"is_selling\\":\\"F\\",\\"is_display\\":\\"T\\"},\\"B\\":{\\"option_value\\":\\"48\\",\\"is_selling\\":\\"T\\",\\"is_display\\":\\"T\\",\\"use_stock\\":true,\\"stock_number\\":0}}\';</script>'
    assert cafe24.parse_options(html) == [("46", False), ("48", False)]


def test_cafe24_build_product():
    item = cafe24.parse_list(read("cafe24_list.html"), "https://www.solidhomme.com", 83)[0]
    p = cafe24.build_product("solidhomme", "SOLID HOMME", item, read("cafe24_detail.html"), rank=0)
    assert p.type == "top"
    assert [s.label for s in p.sizes] == ["46", "48", "50", "52"]
    assert p.sizes[2].measurements["chest"] == 63.0
    j = p.to_json()
    assert j["brandName"] == "SOLID HOMME" and j["sizes"][0]["inStock"] is True


# ---------- 전체 실행 ----------


def test_run_keeps_previous_data_when_brand_fails(tmp_path, monkeypatch):
    out = tmp_path / "products.json"
    out.write_text(json.dumps({"products": [{"id": "b:1", "brand": "b"}]}), "utf-8")

    from watcher import __main__ as main_mod
    from watcher.models import Product

    class Ok:
        def fetch(self):
            return [Product(id="a:1", brand="a", brand_name="A", name="n", url="u", images=["i"], price=1, original_price=1, type="top")]

    class Broken:
        def fetch(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(main_mod, "create_source", lambda conf, http: Ok() if conf["id"] == "a" else Broken())
    ok = run([{"id": "a", "name": "A", "source": "x"}, {"id": "b", "name": "B", "source": "x"}], out, http=object())

    data = json.loads(out.read_text("utf-8"))
    assert ok == 1
    assert [p["id"] for p in data["products"]] == ["a:1", "b:1"]
    assert data["brands"][1] == {"id": "b", "name": "B", "ok": False, "count": 1}


def test_brands_config_is_valid():
    from watcher.__main__ import ROOT, load_brands
    from watcher.sources import SOURCE_TYPES

    brands = load_brands(ROOT / "brands.toml")
    ids = [b["id"] for b in brands]
    assert len(ids) == len(set(ids))
    assert {"solidhomme", "timehomme", "systemhomme"} <= set(ids)
    assert all(b["source"] in SOURCE_TYPES for b in brands)
