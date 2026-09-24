"""사이트마다 다른 실측 항목명을 공통 키로 정규화한다.

모든 폭 계열 값(가슴, 허리, 엉덩이, 허벅지, 밑단)은 '단면'(평평하게 놓고 잰 폭) 기준으로 맞춘다.
"""
from __future__ import annotations

import re

# 공통 키: 앱의 사이즈 추천 로직(site/sizing.js)과 동일해야 한다.
KEYS = ("shoulder", "chest", "sleeve", "length", "waist", "hip", "thigh", "rise", "hem")

# (패턴, 키) — 위에서부터 먼저 맞는 것을 사용한다.
_NAME_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"어깨|shoulder", re.I), "shoulder"),
    (re.compile(r"가슴|chest|bust|pit", re.I), "chest"),
    (re.compile(r"^소매\s*길이$|^sleeve(\s*length)?$", re.I), "sleeve"),
    (re.compile(r"허리|waist", re.I), "waist"),
    (re.compile(r"엉덩이|힙|hip", re.I), "hip"),
    (re.compile(r"허벅지|thigh", re.I), "thigh"),
    (re.compile(r"^앞\s*밑위|^밑위|^(front\s*)?rise$", re.I), "rise"),
    (re.compile(r"^(?!.*소매).*(밑단|부리)|^hem|leg\s*opening", re.I), "hem"),
    (re.compile(r"^총\s*(길이|장)$|^(total\s*)?length$|outseam|^총기장$|^기장$", re.I), "length"),
]

# 이름에 둘레/단면 표시가 없을 때, 이 값보다 크면 둘레로 보고 절반으로 환산한다.
_CIRCUMFERENCE_THRESHOLD = {"chest": 80.0, "waist": 58.0, "hip": 75.0, "thigh": 48.0, "hem": 36.0}
_WIDTH_KEYS = set(_CIRCUMFERENCE_THRESHOLD)


def key_for(name: str) -> str | None:
    name = name.strip()
    for pattern, key in _NAME_RULES:
        if pattern.search(name):
            return key
    return None


def normalize(name: str, value: float) -> tuple[str, float] | None:
    """(항목명, 값) → (공통 키, 단면 기준 cm). 모르는 항목이거나 값이 없으면 None."""
    if value is None or value <= 0:
        return None
    key = key_for(name)
    if key is None:
        return None
    if key in _WIDTH_KEYS:
        if re.search(r"둘레|circumference", name, re.I):
            value = value / 2
        elif re.search(r"단면|width", name, re.I):
            pass
        elif value > _CIRCUMFERENCE_THRESHOLD[key]:
            value = value / 2
    return key, round(float(value), 1)


def normalize_all(pairs) -> dict[str, float]:
    """[(항목명, 값), ...] → {공통 키: 값}. 같은 키가 여러 번 나오면 먼저 나온 값을 쓴다."""
    out: dict[str, float] = {}
    for name, value in pairs:
        r = normalize(name, value)
        if r and r[0] not in out:
            out[r[0]] = r[1]
    return out


def parse_number(text: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(m.group()) if m else None
