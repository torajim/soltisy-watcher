from __future__ import annotations

from .base import Http, Source
from .cafe24 import Cafe24Source
from .thehandsome import TheHandsomeSource

SOURCE_TYPES: dict[str, type[Source]] = {
    "cafe24": Cafe24Source,
    "thehandsome": TheHandsomeSource,
}


def create_source(conf: dict, http: Http) -> Source:
    conf = dict(conf)
    kind = conf.pop("source")
    if kind not in SOURCE_TYPES:
        raise ValueError(f"알 수 없는 source: {kind} (가능: {', '.join(SOURCE_TYPES)})")
    return SOURCE_TYPES[kind](brand_id=conf.pop("id"), brand_name=conf.pop("name"), http=http, **conf)
