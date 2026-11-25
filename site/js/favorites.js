// 찜 목록 (순수 함수). 브라우저 저장은 store.js 가 맡는다.
//
// 저장 형태: [{ id, savedAt, product }, ...]  최근에 찜한 것이 앞.
// product 는 찜할 때의 상품 정보 사본이다. 크롤링 결과에서 상품이 빠져도
// 찜 목록에서는 계속 볼 수 있게 남겨 둔다.

/** 저장값을 정리한다: 형식이 이상한 항목과 중복 id 를 뺀다. */
export function normalizeFavorites(saved) {
  if (!Array.isArray(saved)) return [];
  const seen = new Set();
  const out = [];
  for (const f of saved) {
    if (!f || typeof f.id !== "string" || !f.product || seen.has(f.id)) continue;
    seen.add(f.id);
    out.push(f);
  }
  return out;
}

export function isFavorite(favs, id) {
  return favs.some((f) => f.id === id);
}

/** 찜 상태를 뒤집은 새 목록을 돌려준다. 새로 찜한 상품은 맨 앞에 온다. */
export function toggleFavorite(favs, product, now = Date.now()) {
  if (isFavorite(favs, product.id)) return favs.filter((f) => f.id !== product.id);
  return [{ id: product.id, savedAt: now, product }, ...favs];
}

/**
 * 찜 모아보기 목록. 지금 데이터에 있는 상품은 최신 정보(가격·재고)로, 빠진 상품은 찜할 때 사본으로 보여준다.
 * 빠진 상품에는 gone: true 를 붙인다.
 */
export function favoriteProducts(favs, products) {
  const byId = new Map(products.map((p) => [p.id, p]));
  return favs.map((f) => byId.get(f.id) || { ...f.product, gone: true });
}

/** 최신 정보로 사본을 갱신한다 (바뀐 게 없으면 같은 배열을 돌려준다). */
export function refreshFavorites(favs, products) {
  const byId = new Map(products.map((p) => [p.id, p]));
  let changed = false;
  const out = favs.map((f) => {
    const p = byId.get(f.id);
    if (!p || JSON.stringify(p) === JSON.stringify(f.product)) return f;
    changed = true;
    return { ...f, product: p };
  });
  return changed ? out : favs;
}
