from pathlib import Path

from watcher.sources import cafe24, prada, ssf

FIX = Path(__file__).parent / "fixtures"


def read(name):
    return (FIX / name).read_text("utf-8")


# ---------- 스컬프스토어 (Cafe24 편집숍 스킨) ----------


def test_sculp_parse_list():
    items = cafe24.parse_list(read("sculp_list.html"), "https://www.sculpstore.com", 255)
    assert len(items) == 3
    first = items[0]
    assert first["product_no"] == "36058"
    assert first["sub_brand"] == "TIMBERLAND"
    assert first["name"] == "AUTHENTIC BOAT SHOE MD BROWN FG W MD BROWN"
    assert (first["price"], first["original_price"]) == (159600, 228000)  # 할인가 / 정가
    assert first["url"] == "https://www.sculpstore.com/product/detail.html?product_no=36058&cate_no=255"


def test_sculp_detail_images_from_every_slide():
    images = cafe24.parse_images(read("sculp_detail.html"))
    assert len(images) >= 3  # og:image + 슬라이드마다 1장
    assert all(u.startswith("https://") and "/extra/small/" not in u for u in images)


def test_sculp_build_product_shows_real_brand():
    item = cafe24.parse_list(read("sculp_list.html"), "https://www.sculpstore.com", 255)[0]
    p = cafe24.build_product("sculpstore", "SCULP STORE", item, read("sculp_detail.html"), rank=0)
    assert p.brand == "sculpstore"
    assert p.brand_name == "TIMBERLAND · SCULP STORE"
    assert p.type == "shoes"
    assert [s.label for s in p.sizes][:2] == ["260", "265"]


def test_solid_list_has_no_sub_brand():
    items = cafe24.parse_list(read("cafe24_list.html"), "https://www.solidhomme.com", 83)
    assert items[0]["sub_brand"] == ""
    p = cafe24.build_product("solidhomme", "SOLID HOMME", items[0], read("cafe24_detail.html"), rank=0)
    assert p.brand_name == "SOLID HOMME"


# ---------- SSF SHOP (비이커) ----------


def test_ssf_parse_list():
    items = ssf.parse_list(read("ssf_list.html"))
    assert len(items) == 2
    first = items[0]
    assert first["god_no"] == "GM0026091417942"
    assert first["sub_brand"] == "ANCELLM"
    assert first["name"] == "Geep Tuck Jacket - Black"
    assert (first["price"], first["original_price"]) == (2612500, 2750000)
    assert first["url"].startswith("https://m.ssfshop.com/ANCELLM/GM0026091417942/good?")


def test_ssf_detail():
    html = read("ssf_detail.html")
    images = ssf.parse_images(html, "GM0026091417942")
    assert len(images) == 7
    assert images[0].startswith(ssf.IMG_RESIZE) and "_0_THNAIL" in images[0] and "_6_THNAIL" in images[-1]
    sizes, kind = ssf.parse_sizes(html)
    assert kind == "top"  # MALE_TOP
    assert [(s.label, s.aliases, s.in_stock) for s in sizes] == [("002", ["2"], True), ("003", ["3"], True)]


def test_ssf_build_product():
    item = ssf.parse_list(read("ssf_list.html"))[0]
    p = ssf.build_product("beaker", "BEAKER", item, read("ssf_detail.html"), rank=0)
    assert p.id == "beaker:GM0026091417942"
    assert p.brand_name == "ANCELLM · BEAKER"
    assert p.type == "top"
    assert len(p.images) == 7


# ---------- 프라다 ----------


def test_prada_parse_and_build():
    hits = prada.parse_hits(read("prada_list.html"))
    assert len(hits) == 3
    p = prada.build_product("prada", "PRADA", hits[0], "/kr/ko", rank=0)
    assert p.name == "가죽 코트"
    assert p.type == "top"
    assert p.price == 19700000 and p.original_price == 19700000
    assert p.url.startswith("https://www.prada.com/kr/ko/p/%EA%B0%80%EC%A3%BD") and p.url.endswith("UPS719_1967_F077U_S_OOO")
    assert p.images and all(u.endswith(prada.RENDITION) for u in p.images)
    assert p.color == "에메랄드 그린"
    assert p.sizes == []


def test_prada_without_hits_raises():
    class Http:
        def get_text(self, url, **_):
            return "<html>no data</html>"

    src = prada.PradaSource("prada", "PRADA", Http(), category_path="/mens/new-in/c/10182KR.html")
    try:
        src.fetch()
    except RuntimeError as e:
        assert "hits" in str(e)
    else:
        raise AssertionError("구조가 바뀌면 실패로 알려야 함")


# ---------- 리뷰에서 나온 회귀 케이스 ----------


def test_cafe24_name_numbers_are_not_prices():
    html = """<div class="xans-product-listnormal"><ul>
      <li id="anchorBoxId_1"><a href="/product/m-1965/1/category/255/display/1/"><p class="nm">M-1965 FIELD JACKET</p></a></li>
    </ul></div>"""
    item = cafe24.parse_list(html, "https://x", 255)[0]
    assert (item["price"], item["original_price"]) == (0, 0)


def test_cafe24_ignores_items_outside_main_list():
    html = """<div class="xans-product-listmain"><ul>
      <li id="anchorBoxId_9"><a href="/product/best/9/"><p class="nm">BEST ITEM</p></a></li></ul></div>
    <div class="xans-product-listnormal"><ul>
      <li id="anchorBoxId_1"><a href="/product/new/1/"><p class="nm">NEW ITEM</p><div class="price">228,000원</div></a></li></ul></div>"""
    assert [i["product_no"] for i in cafe24.parse_list(html, "https://x", 255)] == ["1"]


def test_ssf_missing_regular_price_does_not_use_name():
    html = """<ul><li name="gooditem" data-prdno="GM1"><a class="godItem" href="/B/GM1/good">
      <span class="brndNm">B</span><span class="godNm">Graphic Tee 2 Pack</span>
      <span class="lastSalePrc"><em class="dcRt">10%</em> 59,000</span></a></li></ul>"""
    item = ssf.parse_list(html)[0]
    assert (item["price"], item["original_price"]) == (59000, 59000)
