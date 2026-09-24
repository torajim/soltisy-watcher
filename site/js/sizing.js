// 사이즈 추천 로직 (브라우저/Node 공용, 순수 함수).
//
// 프로필 구조:
// {
//   labels: { top: ["100", "48", "L"], bottom: ["32", "82"], shoes: ["270"] },  // 우선순위 순
//   measurements: {                                                            // 잘 맞는 옷의 실측(단면, cm)
//     top:    { shoulder, chest, sleeve, length },
//     bottom: { waist, hip, thigh, rise, length, hem }
//   }
// }
// 상품 사이즈의 measurements 는 크롤러가 단면(cm) 기준으로 정규화해 둔 값이다.

export const MEASURE_FIELDS = {
  top: [
    { key: "shoulder", label: "어깨너비" },
    { key: "chest", label: "가슴단면" },
    { key: "length", label: "총장" },
    { key: "sleeve", label: "소매길이" },
  ],
  bottom: [
    { key: "waist", label: "허리단면" },
    { key: "hip", label: "엉덩이단면" },
    { key: "thigh", label: "허벅지단면" },
    { key: "rise", label: "밑위" },
    { key: "length", label: "총장" },
    { key: "hem", label: "밑단단면" },
  ],
};

export const MEASURE_LABELS = Object.fromEntries(
  [...MEASURE_FIELDS.top, ...MEASURE_FIELDS.bottom].map((f) => [f.key, f.label]),
);

const WEIGHTS = {
  top: { chest: 3, shoulder: 2, length: 1, sleeve: 1 },
  bottom: { waist: 3, hip: 1.5, thigh: 1.5, rise: 1, length: 1, hem: 0.5 },
};
// 이 중 하나는 비교 가능해야 실측 추천을 한다 (총장만 맞는 건 의미가 없으므로).
const PRIMARY = { top: ["chest", "shoulder"], bottom: ["waist"] };

export function emptyProfile() {
  return { labels: { top: [], bottom: [], shoes: [] }, measurements: { top: {}, bottom: {} } };
}

export function normalizeLabel(s) {
  return String(s ?? "").toUpperCase().replace(/\s+/g, "").replace(/\+$/, "");
}

export function parseLabelList(text) {
  return String(text ?? "")
    .split(/[,/\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function sizeNames(size) {
  return [size.label, ...(size.aliases || [])].map(normalizeLabel);
}

/** 라벨 기준 추천: 프로필 라벨 목록 우선순위대로 상품 옵션과 맞춰본다. */
export function recommendByLabel(product, profile) {
  const wanted = (profile?.labels?.[product.type] || []).map(normalizeLabel).filter(Boolean);
  for (const w of wanted) {
    const size = product.sizes.find((s) => sizeNames(s).includes(w));
    if (size) return { size, matched: w };
  }
  return null;
}

/** 한 사이즈와 내 실측의 차이. 비교할 주요 항목이 없으면 null. */
export function measureScore(sizeMeasurements, mine, type) {
  const weights = WEIGHTS[type];
  if (!weights || !sizeMeasurements || !mine) return null;
  let total = 0;
  let wsum = 0;
  const diffs = {};
  for (const [key, w] of Object.entries(weights)) {
    const a = Number(sizeMeasurements[key]);
    const b = Number(mine[key]);
    if (!a || !b) continue;
    const d = Math.round((a - b) * 10) / 10;
    diffs[key] = d;
    total += w * Math.abs(d);
    wsum += w;
  }
  if (!PRIMARY[type].some((k) => k in diffs)) return null;
  return { score: Math.round((total / wsum) * 100) / 100, diffs };
}

/** 실측 기준 추천: 가중 평균 오차가 가장 작은 사이즈. 동점이면 재고 있는 쪽. */
export function recommendByMeasure(product, profile) {
  const mine = profile?.measurements?.[product.type];
  let best = null;
  for (const size of product.sizes) {
    const r = measureScore(size.measurements, mine, product.type);
    if (!r) continue;
    const better =
      !best || r.score < best.score || (r.score === best.score && size.inStock && !best.size.inStock);
    if (better) best = { size, ...r };
  }
  return best;
}

export function fitVerdict(score) {
  if (score == null) return "";
  if (score <= 1.5) return "잘 맞음";
  if (score <= 3) return "약간 차이";
  return "차이 큼";
}

/**
 * 최종 추천. 실측 비교가 가능하면 실측을, 아니면 라벨을 쓴다.
 * @returns {null | {label, inStock, method: "measure"|"label", score?, diffs?, verdict?, labelAlt?}}
 */
export function recommend(product, profile) {
  if (!product?.sizes?.length || !["top", "bottom", "shoes"].includes(product.type)) return null;
  const byLabel = recommendByLabel(product, profile);
  const byMeasure = product.type === "shoes" ? null : recommendByMeasure(product, profile);

  if (byMeasure) {
    const out = {
      label: byMeasure.size.label,
      inStock: byMeasure.size.inStock,
      method: "measure",
      score: byMeasure.score,
      diffs: byMeasure.diffs,
      verdict: fitVerdict(byMeasure.score),
    };
    if (byLabel && byLabel.size.label !== byMeasure.size.label) out.labelAlt = byLabel.size.label;
    return out;
  }
  if (byLabel) {
    return { label: byLabel.size.label, inStock: byLabel.size.inStock, method: "label" };
  }
  return null;
}

export function formatDiff(d) {
  if (d == null) return "";
  if (d === 0) return "±0";
  return (d > 0 ? "+" : "") + d.toFixed(1).replace(/\.0$/, "");
}

export function hasProfile(profile) {
  if (!profile) return false;
  const labels = Object.values(profile.labels || {}).some((l) => l && l.length);
  const meas = Object.values(profile.measurements || {}).some((m) => m && Object.values(m).some((v) => Number(v) > 0));
  return labels || meas;
}
