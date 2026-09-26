// 피드 구성 (순수 함수).

export const TYPE_FILTERS = [
  { id: "all", label: "전체" },
  { id: "top", label: "상의·아우터" },
  { id: "bottom", label: "하의" },
  { id: "shoes", label: "신발" },
  { id: "etc", label: "잡화" },
];

/** 브랜드별 신상품 순서를 유지하면서 브랜드를 번갈아 섞는다 (한 브랜드만 계속 나오지 않도록). */
export function interleave(products, brandOrder) {
  const groups = new Map(brandOrder.map((id) => [id, []]));
  for (const p of products) {
    if (!groups.has(p.brand)) groups.set(p.brand, []);
    groups.get(p.brand).push(p);
  }
  for (const list of groups.values()) list.sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0));
  const lists = [...groups.values()];
  const out = [];
  for (let i = 0; lists.some((l) => i < l.length); i++) {
    for (const l of lists) if (i < l.length) out.push(l[i]);
  }
  return out;
}

export function filterProducts(products, { brand = "all", type = "all" } = {}) {
  return products.filter((p) => (brand === "all" || p.brand === brand) && (type === "all" || p.type === type));
}

export function formatPrice(n) {
  return "₩" + Number(n || 0).toLocaleString("ko-KR");
}

export function discountRate(p) {
  if (!p.originalPrice || p.originalPrice <= p.price) return 0;
  return Math.round((1 - p.price / p.originalPrice) * 100);
}

export function timeAgo(iso, now = Date.now()) {
  const t = Date.parse(iso);
  if (!t) return "";
  const m = Math.max(0, Math.round((now - t) / 60000));
  if (m < 1) return "방금";
  if (m < 60) return `${m}분 전`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}시간 전`;
  return `${Math.round(h / 24)}일 전`;
}

/**
 * 저장해 둔 위치를 현재 목록의 인덱스로 바꾼다.
 * 상품 id 로 찾고(새 상품이 앞에 추가돼도 같은 상품으로 돌아감), 없어졌으면 비슷한 순서로 간다.
 */
export function restoreIndex(list, saved) {
  if (!saved || !list.length) return 0;
  const i = list.findIndex((p) => p.id === saved.id);
  if (i >= 0) return i;
  const n = Number(saved.index);
  return Number.isInteger(n) && n > 0 ? Math.min(n, list.length - 1) : 0;
}
