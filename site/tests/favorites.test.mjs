import { test } from "node:test";
import assert from "node:assert/strict";
import { favoriteProducts, isFavorite, normalizeFavorites, refreshFavorites, toggleFavorite } from "../js/favorites.js";

const A = { id: "solid:1", brand: "solid", name: "코트", price: 900000 };
const B = { id: "beaker:2", brand: "beaker", name: "셔츠", price: 150000 };

test("찜하면 맨 앞에 추가되고, 다시 누르면 빠진다", () => {
  let favs = toggleFavorite([], A, 1);
  favs = toggleFavorite(favs, B, 2);
  assert.deepEqual(favs.map((f) => f.id), ["beaker:2", "solid:1"]);
  assert.ok(isFavorite(favs, "solid:1"));
  favs = toggleFavorite(favs, A, 3);
  assert.deepEqual(favs.map((f) => f.id), ["beaker:2"]);
  assert.ok(!isFavorite(favs, "solid:1"));
});

test("저장값이 깨져 있거나 중복이면 정리한다", () => {
  assert.deepEqual(normalizeFavorites(null), []);
  assert.deepEqual(normalizeFavorites({}), []);
  const favs = normalizeFavorites([{ id: "a", product: A }, { id: "a", product: A }, { id: 3 }, null, { id: "b" }]);
  assert.deepEqual(favs.map((f) => f.id), ["a"]);
});

test("모아보기는 지금 데이터를 쓰고, 데이터에서 빠진 상품은 사본으로 보여준다", () => {
  const favs = toggleFavorite(toggleFavorite([], A, 1), B, 2);
  const cheaper = { ...A, price: 700000 };
  const list = favoriteProducts(favs, [cheaper]);
  assert.equal(list.length, 2);
  assert.deepEqual(list[0], { ...B, gone: true });
  assert.equal(list[1], cheaper);
});

test("사본은 최신 정보로 갱신하고, 바뀐 게 없으면 같은 배열을 돌려준다", () => {
  const favs = toggleFavorite([], A, 1);
  assert.equal(refreshFavorites(favs, [A, B]), favs);
  const next = refreshFavorites(favs, [{ ...A, price: 1 }]);
  assert.notEqual(next, favs);
  assert.equal(next[0].product.price, 1);
  assert.equal(next[0].savedAt, 1);
});
