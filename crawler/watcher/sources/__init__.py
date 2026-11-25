from __future__ import annotations

from .adererror import AderErrorSource
from .base import Http, Source
from .carhartt import CarharttSource
from .cafe24 import Cafe24Source
from .prada import PradaSource
from .ssf import SsfSource
from .thehandsome import TheHandsomeSource
from .thehyundai import TheHyundaiSource
from .uniqlo import UniqloSource
from .zara import ZaraSource

SOURCE_TYPES: dict[str, type[Source]] = {
    "cafe24": Cafe24Source,
    "thehandsome": TheHandsomeSource,
    "ssf": SsfSource,
    "prada": PradaSource,
    "zara": ZaraSource,
    "uniqlo": UniqloSource,
    "thehyundai": TheHyundaiSource,
    "carhartt": CarharttSource,
    "adererror": AderErrorSource,
}


def create_source(conf: dict, http: Http) -> Source:
    conf = dict(conf)
    kind = conf.pop("source")
    if kind not in SOURCE_TYPES:
        raise ValueError(f"알 수 없는 source: {kind} (가능: {', '.join(SOURCE_TYPES)})")
    return SOURCE_TYPES[kind](brand_id=conf.pop("id"), brand_name=conf.pop("name"), http=http, **conf)
