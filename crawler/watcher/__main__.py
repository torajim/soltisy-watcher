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


GENDERS = ("men", "women")


def gender_feeds(conf: dict) -> list[tuple[str, dict]]:
    """브랜드 설정을 성별 피드 목록으로 나눈다.

    - `[brand.men]` / `[brand.women]` 하위 표가 있으면 각각을 공통 설정에 덮어써 따로 수집한다.
    - 없으면 `gender`(기본 "men") 하나로 수집한다.
    """
    base = {k: v for k, v in conf.items() if k not in GENDERS and k != "gender"}
    split = [(g, {**base, **conf[g]}) for g in GENDERS if isinstance(conf.get(g), dict)]
    return split or [(conf.get("gender", "men"), base)]


def merge_genders(products: list[dict]) -> list[dict]:
    """남성·여성 목록에 모두 나온 상품은 하나만 남기고 'unisex' 로 표시한다."""
    seen: dict[str, dict] = {}
    for p in products:
        first = seen.get(p["id"])
        if first is None:
            seen[p["id"]] = p
        elif first.get("gender") != p.get("gender"):
            first["gender"] = "unisex"
    return list(seen.values())


def run(brands: list[dict], out: Path, only: set[str] | None = None, http: Http | None = None) -> int:
    """수집 후 JSON 을 쓴다. 성공한 브랜드 수를 반환한다.

    한 브랜드가 실패하면 기존 파일에 있던 그 브랜드의 상품을 유지한다.
    """
    http = http or Http()
    previous: dict[str, list[dict]] = {}
    previous_updated: dict[str, str] = {}
    previous_ok: dict[str, bool] = {}
    if out.exists():
        try:
            old = json.loads(out.read_text("utf-8"))
            for p in old.get("products", []):
                previous.setdefault(p["brand"], []).append(p)
            for b in old.get("brands", []):
                previous_ok[b["id"]] = bool(b.get("ok"))
                # 예전 파일에는 updatedAt 이 없다. 그때 성공한 브랜드는 그 파일의 생성 시각을 쓴다.
                updated = b.get("updatedAt") or (old.get("generatedAt") if b.get("ok") else None)
                if updated:
                    previous_updated[b["id"]] = updated
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            pass

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    products: list[dict] = []
    brand_info = []
    ok = 0
    for conf in brands:
        info = {"id": conf["id"], "name": conf["name"], "ok": False, "count": 0}
        brand_info.append(info)
        if conf["source"] == "link":
            # 수집하지 않고 앱에 공식 페이지 바로가기 칩만 보여주는 브랜드
            info.update(ok=True, link=conf["url"])
            continue
        if only and conf["id"] not in only:
            # 이번에 수집 대상이 아닌 브랜드는 실패가 아니다. 이전 상태를 그대로 옮긴다.
            kept = previous.get(conf["id"], [])
            products.extend(kept)
            info.update(ok=previous_ok.get(conf["id"], False), count=len(kept), updatedAt=previous_updated.get(conf["id"]))
            continue
        feeds = gender_feeds(conf)
        fetched: list[dict] = []
        failed: list[str] = []
        for gender, feed_conf in feeds:
            try:
                got = create_source(feed_conf, http).fetch()
                if not got:
                    raise RuntimeError("상품이 0개")
                for p in got:
                    p.gender = p.gender or gender
                fetched.extend(p.to_json() for p in got)
                log.info("%s/%s: %d개", conf["id"], gender, len(got))
            except Exception:
                log.exception("%s/%s 수집 실패 — 이전 데이터 유지", conf["id"], gender)
                failed.append(gender)
        if failed:
            # 실패한 성별 피드만 이전 데이터로 채운다. 피드가 하나뿐이면(성별 구분 없는 브랜드) 전부 유지.
            # 예전 파일의 상품은 성별이 없으면 남성으로 본다.
            kept = previous.get(conf["id"], [])
            if len(failed) < len(feeds):
                kept = [p for p in kept if p.get("gender", "men") in (*failed, "unisex")]
            fetched.extend(kept)
        fetched = merge_genders(fetched)
        products.extend(fetched)
        info["count"] = len(fetched)
        if failed:
            # 앱이 "N시간 전 데이터" 를 보여줄 수 있도록 마지막 성공 시각을 남긴다
            info["updatedAt"] = previous_updated.get(conf["id"])
        else:
            info.update(ok=True, updatedAt=now)
            ok += 1

    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": now,
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
    targets = [b for b in brands if b["source"] != "link" and (not args.only or b["id"] in args.only)]
    ok = run(brands, args.out, set(args.only) if args.only else None)
    log.info("완료: %d/%d 브랜드 성공 → %s", ok, len(targets), args.out)
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
