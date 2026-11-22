"""임시: GitHub 러너에서 신규 브랜드 실제 수집 확인 (머지 전 삭제)."""
import json, logging, tomllib
from pathlib import Path
from watcher.__main__ import run
logging.basicConfig(level=logging.INFO)
ids = {"tomgreyhound", "coor", "peer", "zara", "uniqlo"}
brands = [b for b in tomllib.load(open("brands.toml", "rb"))["brand"] if b["id"] in ids]
for b in brands:
    b["limit"] = 3
out = Path("/tmp/probe.json")
run(brands, out)
d = json.loads(out.read_text())
for b in d["brands"]:
    print("PROBE", b)
for p in d["products"]:
    print("PROBE", p["brand"], p["gender"], p["name"], p["price"], len(p["images"]), [s["label"] for s in p["sizes"]])
