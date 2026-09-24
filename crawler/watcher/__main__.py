"""사용법: python -m watcher [--config brands.toml] [--out ../site/data/products.json] [--only timehomme]"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from .sources import Http, create_source

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("watcher")


def load_brands(path: Path) -> list[dict]:
    with path.open("rb") as f:
        return tomllib.load(f)["brand"]


def run(brands: list[dict], out: Path, only: set[str] | None = None, http: Http | None = None) -> int:
    """수집 후 JSON 을 쓴다. 성공한 브랜드 수를 반환한다.

    한 브랜드가 실패하면 기존 파일에 있던 그 브랜드의 상품을 유지한다.
    """
    http = http or Http()
    previous: dict[str, list[dict]] = {}
    if out.exists():
        try:
            for p in json.loads(out.read_text("utf-8")).get("products", []):
                previous.setdefault(p["brand"], []).append(p)
        except (json.JSONDecodeError, KeyError):
            pass

    products: list[dict] = []
    brand_info = []
    ok = 0
    for conf in brands:
        info = {"id": conf["id"], "name": conf["name"], "ok": False, "count": 0}
        brand_info.append(info)
        if only and conf["id"] not in only:
            kept = previous.get(conf["id"], [])
            products.extend(kept)
            info["count"] = len(kept)
            continue
        try:
            fetched = [p.to_json() for p in create_source(conf, http).fetch()]
            if not fetched:
                raise RuntimeError("상품이 0개")
            products.extend(fetched)
            info.update(ok=True, count=len(fetched))
            ok += 1
            log.info("%s: %d개", conf["id"], len(fetched))
        except Exception:
            log.exception("%s 수집 실패 — 이전 데이터 유지", conf["id"])
            kept = previous.get(conf["id"], [])
            products.extend(kept)
            info["count"] = len(kept)

    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "brands": brand_info,
        "products": products,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="브랜드 신상품 수집기")
    ap.add_argument("--config", type=Path, default=ROOT / "brands.toml")
    ap.add_argument("--out", type=Path, default=ROOT.parent / "site" / "data" / "products.json")
    ap.add_argument("--only", action="append", help="이 브랜드 id 만 수집 (여러 번 지정 가능)")
    ap.add_argument("--limit", type=int, help="브랜드별 최대 상품 수 덮어쓰기 (테스트용)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    brands = load_brands(args.config)
    if args.limit:
        for b in brands:
            b["limit"] = args.limit
    targets = [b for b in brands if not args.only or b["id"] in args.only]
    ok = run(brands, args.out, set(args.only) if args.only else None)
    log.info("완료: %d/%d 브랜드 성공 → %s", ok, len(targets), args.out)
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
