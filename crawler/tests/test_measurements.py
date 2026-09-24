import pytest

from watcher.classify import classify
from watcher.measurements import normalize, normalize_all


@pytest.mark.parametrize(
    "name,value,expected",
    [
        ("가슴둘레", 135.0, ("chest", 67.5)),
        ("가슴단면", 57.0, ("chest", 57.0)),
        ("Chest", 57, ("chest", 57.0)),  # 솔리드옴므: 단면 값
        ("Waist", 77.5, ("waist", 38.8)),  # 솔리드옴므: 둘레 값 → 단면
        ("허리둘레", 80.4, ("waist", 40.2)),
        ("어깨너비", 44.5, ("shoulder", 44.5)),
        ("Shoulder", 46, ("shoulder", 46.0)),
        ("소매길이", 60.7, ("sleeve", 60.7)),
        ("Sleeve", 61, ("sleeve", 61.0)),
        ("총길이", 64.5, ("length", 64.5)),
        ("Outseam", 102.4, ("length", 102.4)),
        ("앞밑위길이", 29.6, ("rise", 29.6)),
        ("Rise", 27.86, ("rise", 27.9)),
        ("밑단단면(바지부리)", 23.9, ("hem", 23.9)),
        ("Hem", 22.5, ("hem", 22.5)),
        ("Thigh", 35.9, ("thigh", 35.9)),
        ("엉덩이둘레", 105.2, ("hip", 52.6)),
    ],
)
def test_normalize(name, value, expected):
    assert normalize(name, value) == expected


@pytest.mark.parametrize("name", ["소매부리", "화장길이", "소매통", "뒤밑위길이", "트임길이"])
def test_ignored_fields(name):
    assert normalize(name, 10.0) is None


def test_zero_value_ignored():
    assert normalize("가슴단면", 0.0) is None


def test_normalize_all_first_wins():
    # 가슴둘레(0 → 무시) 다음 가슴단면 값을 사용
    assert normalize_all([("가슴둘레", 0.0), ("가슴단면", 55.0), ("총길이", 70)]) == {"chest": 55.0, "length": 70.0}


@pytest.mark.parametrize(
    "texts,expected",
    [
        (("데님", "팬츠", "남성"), "bottom"),
        (("점퍼", "아우터", "남성"), "top"),
        (("남성슈즈", "잡화"), "shoes"),
        (("남성백", "잡화"), "etc"),
        (("블랙 스트라이프 카라넥 가디건",), "top"),
        (("라이트 블루 스트레이트 데님 팬츠",), "bottom"),
        (("배색 스웨이드 레이스업 스니커즈",), "shoes"),
        # 품목명은 맨 끝에 오므로 마지막 키워드를 따른다
        (("인디고 데님 재킷",), "top"),
        (("워시드 데님 셔츠",), "top"),
        (("카고 재킷",), "top"),
        (("부츠컷 데님 팬츠",), "bottom"),
        (("bootcut jeans",), "bottom"),
        (("첼시 부츠",), "shoes"),
        (("수트팬츠", "팬츠", "남성"), "bottom"),
        (("케이블 울 글러브",), "etc"),
    ],
)
def test_classify(texts, expected):
    assert classify(*texts) == expected


def test_classify_falls_back_to_measurements():
    assert classify("무제", measurement_keys={"waist", "rise"}) == "bottom"
    assert classify("무제", measurement_keys={"chest"}) == "top"
    assert classify("무제") == "etc"
