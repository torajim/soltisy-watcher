"""Nuxt 3 페이지의 `__NUXT_DATA__` 페이로드 해석.

Nuxt 3 는 서버 상태를 devalue 형식(평탄화된 JSON 배열)으로 HTML 에 넣는다.
배열의 0번이 루트이고, 객체·배열의 값은 다른 원소를 가리키는 인덱스다.
`["Reactive", i]` 같은 태그 배열은 감싼 값을 그대로 꺼낸다.
"""
from __future__ import annotations

import json
import re
from typing import Any

_SCRIPT = re.compile(r'<script[^>]*\bid="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S)
# 값을 그대로 감싸기만 하는 태그
_WRAPPERS = {"Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef"}


def extract_payload(html: str) -> list | None:
    m = _SCRIPT.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) and data else None


def unflatten(arr: list) -> Any:
    """devalue 평탄화 배열을 일반 파이썬 값으로 되돌린다 (순환 참조 안전)."""
    cache: dict[int, Any] = {}

    def _unwrap(i: int) -> int:
        """래퍼 태그를 따라가 실제 값의 인덱스를 찾는다 (래퍼끼리 순환하면 -1)."""
        for _ in range(len(arr)):
            v = arr[i] if 0 <= i < len(arr) else None
            if not (isinstance(v, list) and len(v) > 1 and v[0] in _WRAPPERS and isinstance(v[1], int)):
                return i
            i = v[1]
        return -1

    def hydrate(i: int) -> Any:
        if not isinstance(i, int) or i < 0 or i >= len(arr):
            return None  # 음수는 undefined·NaN 등 특수값 — 여기서는 모두 None
        if i in cache:
            return cache[i]
        v = arr[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str):
                tag = v[0]
                if tag in _WRAPPERS:
                    return hydrate(_unwrap(i))
                if tag == "Set":
                    r = []
                    cache[i] = r
                    r.extend(hydrate(x) for x in v[1:])
                    return r
                if tag == "Map":
                    r = {}
                    cache[i] = r
                    for k in range(1, len(v) - 1, 2):
                        r[str(hydrate(v[k]))] = hydrate(v[k + 1])
                    return r
                if tag == "null":  # 프로토타입 없는 객체: ["null", key, idx, key, idx ...]
                    r = {}
                    cache[i] = r
                    for k in range(1, len(v) - 1, 2):
                        r[v[k]] = hydrate(v[k + 1])
                    return r
                if tag in ("Date", "BigInt", "RegExp"):
                    cache[i] = v[1] if len(v) > 1 else None
                    return cache[i]
            r = []
            cache[i] = r
            r.extend(hydrate(x) for x in v)
            return r
        if isinstance(v, dict):
            r = {}
            cache[i] = r
            for k, x in v.items():
                r[k] = hydrate(x)
            return r
        cache[i] = v
        return v

    return hydrate(0)


def find_lists(root: Any, key: str, predicate, max_depth: int = 60) -> list[list]:
    """`key` 아래에 있으면서 predicate(첫 원소) 를 만족하는 리스트들을 찾는다."""
    found: list[list] = []
    seen: set[int] = set()
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > max_depth or id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, dict):
            v = node.get(key)
            if isinstance(v, list) and v and predicate(v[0]):
                found.append(v)
            stack.extend((x, depth + 1) for x in node.values() if isinstance(x, (dict, list)))
        elif isinstance(node, list):
            stack.extend((x, depth + 1) for x in node if isinstance(x, (dict, list)))
    return found
