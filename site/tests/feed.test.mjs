import { test } from "node:test";
import assert from "node:assert/strict";
import { discountRate, filterProducts, formatPrice, interleave, timeAgo } from "../js/feed.js";

const P = (brand, rank, type = "top") => ({ id: `${brand}:${rank}`, brand, rank, type, price: 100, originalPrice: 100 });

test("브랜드별 순서를 유지하며 번갈아 섞기", () => {
  const products = [P("a", 1), P("a", 0), P("a", 2), P("b", 0), P("c", 1), P("c", 0)];
  const ids = interleave(products, ["a", "b", "c"]).map((p) => p.id);
  assert.deepEqual(ids, ["a:0", "b:0", "c:0", "a:1", "c:1", "a:2"]);
});

test("설정에 없는 브랜드도 빠지지 않음", () => {
  assert.equal(interleave([P("x", 0)], ["a"]).length, 1);
});

test("브랜드/종류 필터", () => {
  const list = [P("a", 0, "top"), P("a", 1, "bottom"), P("b", 0, "top")];
  assert.equal(filterProducts(list, { brand: "a" }).length, 2);
  assert.equal(filterProducts(list, { type: "top" }).length, 2);
  assert.equal(filterProducts(list, { brand: "a", type: "bottom" }).length, 1);
  assert.equal(filterProducts(list).length, 3);
});

test("가격/할인/시간 표시", () => {
  assert.equal(formatPrice(955000), "₩955,000");
  assert.equal(discountRate({ price: 70, originalPrice: 100 }), 30);
  assert.equal(discountRate({ price: 100, originalPrice: 100 }), 0);
  const now = Date.parse("2026-09-24T12:00:00Z");
  assert.equal(timeAgo("2026-09-24T11:30:00Z", now), "30분 전");
  assert.equal(timeAgo("2026-09-24T06:00:00Z", now), "6시간 전");
  assert.equal(timeAgo("2026-09-21T12:00:00Z", now), "3일 전");
});
