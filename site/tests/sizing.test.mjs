import { test } from "node:test";
import assert from "node:assert/strict";
import {
  emptyProfile,
  fitVerdict,
  formatDiff,
  hasProfile,
  measureScore,
  normalizeLabel,
  parseLabelList,
  recommend,
} from "../js/sizing.js";

const jacket = {
  type: "top",
  sizes: [
    { label: "95", aliases: ["M"], inStock: true, measurements: { shoulder: 44.8, chest: 52.0, length: 71.5, sleeve: 64.6 } },
    { label: "100", aliases: ["L"], inStock: true, measurements: { shoulder: 46.0, chest: 53.5, length: 72.5, sleeve: 65.0 } },
    { label: "105", aliases: ["XL"], inStock: false, measurements: { shoulder: 47.4, chest: 55.5, length: 73.5, sleeve: 66.3 } },
  ],
};

const pants = {
  type: "bottom",
  sizes: [
    { label: "78", aliases: ["M", "30+"], inStock: true, measurements: { waist: 40.2, hip: 52.6, length: 104.4 } },
    { label: "82", aliases: ["L", "32+"], inStock: true, measurements: { waist: 42.2, hip: 54.5, length: 105.0 } },
  ],
};

const solid = {
  type: "top",
  sizes: [
    { label: "46", aliases: [], inStock: true, measurements: {} },
    { label: "48", aliases: [], inStock: true, measurements: {} },
  ],
};

function profile(patch) {
  const p = emptyProfile();
  return { labels: { ...p.labels, ...(patch.labels || {}) }, measurements: { ...p.measurements, ...(patch.measurements || {}) } };
}

test("라벨 표기 정규화", () => {
  assert.equal(normalizeLabel(" 32+ "), "32");
  assert.equal(normalizeLabel("xl"), "XL");
  assert.deepEqual(parseLabelList("100, 48 / L"), ["100", "48", "L"]);
});

test("라벨 추천: 우선순위대로, 별칭(M/L, 32+)도 인식", () => {
  assert.equal(recommend(jacket, profile({ labels: { top: ["48", "L"] } })).label, "100");
  assert.equal(recommend(solid, profile({ labels: { top: ["100", "48"] } })).label, "48");
  assert.equal(recommend(pants, profile({ labels: { bottom: ["32"] } })).label, "82");
  assert.equal(recommend(pants, profile({ labels: { bottom: ["36"] } })), null);
});

test("실측 추천: 가장 가까운 사이즈 + 차이값", () => {
  const r = recommend(jacket, profile({ measurements: { top: { shoulder: 46, chest: 54, length: 72 } } }));
  assert.equal(r.method, "measure");
  assert.equal(r.label, "100");
  assert.deepEqual(r.diffs, { chest: -0.5, shoulder: 0, length: 0.5 });
  assert.equal(r.verdict, "잘 맞음");
});

test("실측이 라벨보다 우선, 라벨 결과가 다르면 함께 알려줌", () => {
  const r = recommend(
    jacket,
    profile({ labels: { top: ["95"] }, measurements: { top: { chest: 55.5, shoulder: 47.5 } } }),
  );
  assert.equal(r.label, "105");
  assert.equal(r.inStock, false);
  assert.equal(r.labelAlt, "95");
});

test("주요 항목(가슴/어깨, 허리) 없이 총장만 있으면 실측 추천 안 함", () => {
  assert.equal(measureScore(jacket.sizes[0].measurements, { length: 71 }, "top"), null);
  const r = recommend(jacket, profile({ labels: { top: ["M"] }, measurements: { top: { length: 71 } } }));
  assert.equal(r.method, "label");
  assert.equal(r.label, "95");
});

test("하의 실측 추천", () => {
  const r = recommend(pants, profile({ measurements: { bottom: { waist: 42, length: 104 } } }));
  assert.equal(r.label, "82");
});

test("기타 잡화나 사이즈 없는 상품은 추천 없음", () => {
  assert.equal(recommend({ type: "etc", sizes: jacket.sizes }, profile({ labels: { top: ["95"] } })), null);
  assert.equal(recommend({ type: "top", sizes: [] }, profile({ labels: { top: ["95"] } })), null);
});

test("신발은 라벨만 사용", () => {
  const shoes = { type: "shoes", sizes: [{ label: "265", aliases: [], inStock: true, measurements: {} }, { label: "270", aliases: [], inStock: true, measurements: {} }] };
  assert.equal(recommend(shoes, profile({ labels: { shoes: ["270"] } })).label, "270");
});

test("유틸", () => {
  assert.equal(formatDiff(1.5), "+1.5");
  assert.equal(formatDiff(-2), "-2");
  assert.equal(formatDiff(0), "±0");
  assert.equal(fitVerdict(1), "잘 맞음");
  assert.equal(fitVerdict(2.5), "약간 차이");
  assert.equal(fitVerdict(5), "차이 큼");
  assert.equal(hasProfile(emptyProfile()), false);
  assert.equal(hasProfile(profile({ labels: { top: ["100"] } })), true);
  assert.equal(hasProfile(profile({ measurements: { top: { chest: "" } } })), false);
});
