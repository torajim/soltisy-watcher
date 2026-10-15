from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import requests

from ..models import Product

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1 soltisy-watcher"
)


def _retryable(error: requests.RequestException) -> bool:
    """연결 오류·타임아웃·5xx·429 만 재시도한다."""
    resp = getattr(error, "response", None)
    if resp is None:
        return True
    return resp.status_code >= 500 or resp.status_code == 429


class Http:
    """재시도와 요청 간 지연을 가진 얇은 requests 래퍼."""

    def __init__(self, delay: float = 0.2, retries: int = 3, timeout: float = 20.0):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"})
        self.delay = delay
        self.retries = retries
        self.timeout = timeout

    def get(self, url: str, **kwargs) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self.session.get(url, timeout=self.timeout, **kwargs)
                resp.raise_for_status()
                if self.delay:
                    time.sleep(self.delay)
                return resp
            except requests.RequestException as e:
                last_error = e
                log.warning("GET %s 실패 (%d/%d): %s", url, attempt + 1, self.retries, e)
                if not _retryable(e):
                    break  # 404 등은 다시 요청해도 같으므로 바로 포기한다
                if attempt + 1 < self.retries:
                    time.sleep(2**attempt)
        raise last_error  # type: ignore[misc]

    def get_json(self, url: str, **kwargs) -> dict:
        return self.get(url, **kwargs).json()

    def get_text(self, url: str, **kwargs) -> str:
        resp = self.get(url, **kwargs)
        resp.encoding = resp.encoding if resp.encoding and resp.encoding.lower() != "iso-8859-1" else "utf-8"
        return resp.text


class Source(ABC):
    """브랜드 한 곳의 신상품을 가져오는 어댑터. 새 사이트 유형은 이 클래스를 상속해 추가한다."""

    def __init__(self, brand_id: str, brand_name: str, http: Http, limit: int = 60):
        self.brand_id = brand_id
        self.brand_name = brand_name
        self.http = http
        self.limit = limit

    @abstractmethod
    def fetch(self) -> list[Product]:
        ...
