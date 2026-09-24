"""상품을 사이즈 추천용 유형(top / bottom / shoes / etc)으로 분류한다."""
from __future__ import annotations

import re

from .models import ProductType

_SHOES = re.compile(r"슈즈|신발|스니커즈|로퍼|부츠|더비|샌들|슬리퍼|뮬|옥스퍼드|shoe|sneaker|loafer|boot", re.I)
_BOTTOM = re.compile(r"팬츠|바지|슬랙스|데님|진$|청바지|쇼츠|반바지|트라우저|조거|카고|치노|스커트|pants|trouser|jeans|shorts|denim", re.I)
_ETC = re.compile(r"가방|백$|백팩|토트|크로스|지갑|벨트|모자|캡|비니|머플러|스카프|목도리|장갑|양말|주얼리|반지|목걸이|팔찌|키링|넥타이|타이$|선글라스|잡화|acc", re.I)
_TOP = re.compile(r"아우터|코트|재킷|자켓|점퍼|블레이저|패딩|다운|베스트|셔츠|티셔츠|니트|스웨터|가디건|카디건|맨투맨|스웨트|후드|탑|수트|정장|블루종|야상|파카|폴로|top|coat|jacket|shirt|knit|cardigan|hoodie|vest", re.I)


def classify(*texts: str, measurement_keys: set[str] | None = None) -> ProductType:
    """카테고리명, 상품명 등을 받아 유형을 판단한다. 앞쪽 인자가 더 신뢰도 높은 정보여야 한다."""
    for text in texts:
        if not text:
            continue
        if _SHOES.search(text):
            return "shoes"
        if _BOTTOM.search(text):
            return "bottom"
        if _ETC.search(text):
            return "etc"
        if _TOP.search(text):
            return "top"
    if measurement_keys:
        if measurement_keys & {"waist", "thigh", "rise", "hip"} and not measurement_keys & {"chest", "shoulder"}:
            return "bottom"
        if measurement_keys & {"chest", "shoulder"}:
            return "top"
    return "etc"
