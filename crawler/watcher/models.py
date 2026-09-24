from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

ProductType = Literal["top", "bottom", "shoes", "etc"]


@dataclass
class SizeOption:
    label: str
    """사이트에 표시되는 대표 사이즈 표기 (예: '100', '48', '82')."""
    aliases: list[str] = field(default_factory=list)
    """같은 사이즈의 다른 표기 (예: 'L', '32+')."""
    in_stock: bool = True
    measurements: dict[str, float] = field(default_factory=dict)
    """정규화된 실측치 (cm, 둘레는 단면으로 환산). 키는 measurements.KEYS 참고."""


@dataclass
class Product:
    id: str
    brand: str
    brand_name: str
    name: str
    url: str
    images: list[str]
    price: int
    original_price: int
    type: ProductType
    category: str = ""
    color: str = ""
    sizes: list[SizeOption] = field(default_factory=list)
    size_note: str = ""
    rank: int = 0
    """브랜드 신상품 목록에서의 순서 (0 이 가장 최신)."""

    def to_json(self) -> dict:
        d = asdict(self)
        return {
            "id": d["id"],
            "brand": d["brand"],
            "brandName": d["brand_name"],
            "name": d["name"],
            "url": d["url"],
            "images": d["images"],
            "price": d["price"],
            "originalPrice": d["original_price"],
            "type": d["type"],
            "category": d["category"],
            "color": d["color"],
            "sizes": [
                {
                    "label": s["label"],
                    "aliases": s["aliases"],
                    "inStock": s["in_stock"],
                    "measurements": s["measurements"],
                }
                for s in d["sizes"]
            ],
            "sizeNote": d["size_note"],
            "rank": d["rank"],
        }
