import { TYPE_FILTERS, discountRate, filterProducts, formatPrice, interleave, timeAgo } from "./feed.js";
import { MEASURE_FIELDS, MEASURE_LABELS, formatDiff, hasProfile, parseLabelList, recommend } from "./sizing.js";
import { loadPrefs, loadProfile, savePrefs, saveProfile } from "./store.js";
import * as tryon from "./tryon.js";

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) node.setAttribute(k, v === true ? "" : v);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
};

const state = {
  data: null,
  all: [],
  list: [],
  prefs: loadPrefs(),
  profile: loadProfile(),
  current: 0,
};

const feed = $("#feed");
const counter = $("#counter");

// ---------- 데이터 ----------

async function load() {
  try {
    const res = await fetch("data/products.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(res.status);
    state.data = await res.json();
  } catch (e) {
    showState("상품 데이터를 불러오지 못했어요.\n잠시 후 다시 시도해 주세요.");
    console.error(e);
    return;
  }
  const brandOrder = state.data.brands.map((b) => b.id);
  state.all = interleave(state.data.products, brandOrder);
  if (state.prefs.brand !== "all" && !brandOrder.includes(state.prefs.brand)) state.prefs.brand = "all";
  render();
}

function showState(msg) {
  feed.replaceChildren(el("div", { class: "state", text: msg }));
  counter.hidden = true;
}

// ---------- 필터 ----------

function renderChips() {
  const brands = $("#brandChips");
  const counts = {};
  for (const p of state.all) counts[p.brand] = (counts[p.brand] || 0) + 1;
  const items = [{ id: "all", name: "ALL", count: state.all.length }, ...state.data.brands.map((b) => ({ id: b.id, name: b.name, count: counts[b.id] || 0 }))];
  brands.replaceChildren(
    ...items.map((b) =>
      el(
        "button",
        { class: "chip", type: "button", "aria-pressed": String(state.prefs.brand === b.id), onclick: () => setPref("brand", b.id) },
        b.name,
        el("span", { class: "n", text: b.count }),
      ),
    ),
  );

  const inBrand = filterProducts(state.all, { brand: state.prefs.brand });
  const types = $("#typeChips");
  types.replaceChildren(
    ...TYPE_FILTERS.filter((t) => t.id === "all" || inBrand.some((p) => p.type === t.id)).map((t) =>
      el("button", { class: "chip", type: "button", "aria-pressed": String(state.prefs.type === t.id), onclick: () => setPref("type", t.id) }, t.label),
    ),
  );
}

function setPref(key, value) {
  if (state.prefs[key] === value) {
    feed.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  state.prefs[key] = value;
  if (key === "brand") state.prefs.type = "all";
  savePrefs(state.prefs);
  render();
  feed.scrollTo({ top: 0 });
}

// ---------- 피드 ----------

function render() {
  renderChips();
  state.list = filterProducts(state.all, state.prefs);
  if (!state.list.length) {
    showState("표시할 상품이 없어요.");
    return;
  }
  const tpl = $("#cardTpl");
  const cards = state.list.map((p, i) => buildCard(tpl, p, i));
  feed.replaceChildren(...cards);
  observeCards(cards);
  state.current = 0;
  updateCounter();
}

function buildCard(tpl, p, index) {
  const card = tpl.content.firstElementChild.cloneNode(true);
  card.dataset.index = index;

  const gallery = $(".gallery", card);
  const dots = $(".dots", card);
  p.images.forEach((src, i) => {
    const eager = index < 2 && i === 0;
    const img = el("img", { src, alt: "", loading: eager ? "eager" : "lazy", decoding: "async", draggable: "false" });
    const dot = el("i", { class: i === 0 ? "on" : "" });
    img.addEventListener("error", () => onImageError(img, dot, card));
    gallery.append(img);
    dots.append(dot);
  });
  if (p.images.length < 2) dots.hidden = true;
  gallery.addEventListener("scroll", () => {
    const i = Math.round(gallery.scrollLeft / gallery.clientWidth);
    [...dots.children].forEach((d, j) => d.classList.toggle("on", i === j));
  }, { passive: true });

  $(".brand", card).textContent = p.brandName;
  $(".name", card).textContent = p.name;
  const rate = discountRate(p);
  $(".price", card).replaceChildren(
    ...(rate ? [el("span", { class: "rate", text: `${rate}%` })] : []),
    formatPrice(p.price),
    ...(rate ? [el("s", { text: formatPrice(p.originalPrice) })] : []),
  );

  const go = $(".go", card);
  go.href = p.url;

  $(".size-btn", card).addEventListener("click", () => openSizeSheet(p));
  if (!p.sizes.length) $(".size-btn", card).hidden = true;
  const tryBtn = $(".tryon-btn", card);
  tryBtn.addEventListener("click", () => {
    if (!tryon.isAvailable()) toast("가상 피팅은 준비 중이에요 👕");
  });

  fillSizeInfo(card, p);
  return card;
}

// 이미지 로드 실패: 한 번 재시도 후 그 컷을 빼고, 전부 실패하면 안내 문구를 보여준다.
function onImageError(img, dot, card) {
  if (!img.dataset.retried) {
    img.dataset.retried = "1";
    const src = img.src;
    setTimeout(() => (img.src = src + (src.includes("?") ? "&" : "?") + "r=1"), 1200);
    return;
  }
  img.remove();
  dot.remove();
  const gallery = $(".gallery", card);
  const dots = $(".dots", card);
  if (dots.children.length < 2) dots.hidden = true;
  if (!gallery.querySelector("img")) gallery.append(el("div", { class: "state", text: "이미지를 불러오지 못했어요" }));
}

function fillSizeInfo(card, p) {
  const rec = recommend(p, state.profile);
  const recEl = $(".rec", card);
  recEl.className = "rec";
  recEl.replaceChildren();
  if (rec) {
    if (!rec.inStock) recEl.classList.add("soldout");
    const how = rec.method === "measure" ? `실측 기준 ${rec.verdict}` : "평소 사이즈 기준";
    recEl.append(`추천 ${rec.label} · ${rec.inStock ? how : "품절"}`);
    if (rec.labelAlt) recEl.append(el("span", { class: "muted", text: ` (평소 사이즈 ${rec.labelAlt})` }));
  } else if (p.sizes.length && p.type !== "etc" && !hasProfile(state.profile)) {
    recEl.append(el("span", { class: "muted", text: "내 사이즈를 등록하면 추천해 드려요 →", role: "button", onclick: openSettings }));
  }

  $(".sizes", card).replaceChildren(
    ...p.sizes.map((s) => el("span", { class: `sz${s.inStock ? "" : " out"}${rec && rec.label === s.label ? " pick" : ""}`, text: s.label })),
  );
}

function refreshSizeInfo() {
  for (const card of feed.querySelectorAll(".card")) fillSizeInfo(card, state.list[Number(card.dataset.index)]);
}

let observer;
function observeCards(cards) {
  observer?.disconnect();
  observer = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          state.current = Number(e.target.dataset.index);
          updateCounter();
        }
      }
    },
    { root: feed, threshold: 0.6 },
  );
  cards.forEach((c) => observer.observe(c));
}

function updateCounter() {
  counter.hidden = !state.list.length;
  counter.textContent = `${state.current + 1} / ${state.list.length}`;
}

function goTo(i) {
  const cards = feed.querySelectorAll(".card");
  const target = cards[Math.max(0, Math.min(cards.length - 1, i))];
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------- 사이즈 시트 ----------

function openSizeSheet(p) {
  const sheet = $("#sizeSheet");
  $("#sizeSheetTitle").textContent = `${p.brandName} · 사이즈`;
  const body = $("#sizeSheetBody");
  body.replaceChildren();

  const rec = recommend(p, state.profile);
  const box = el("div", { class: "rec-box" });
  if (rec) {
    box.append("추천 사이즈 ", el("b", { text: rec.label }), rec.inStock ? "" : " (품절)");
    if (rec.method === "measure") {
      box.append(el("br"), `내 옷 실측과 비교: ${rec.verdict} (평균 오차 ${rec.score}cm)`);
      if (rec.labelAlt) box.append(el("br"), `평소 사이즈로는 ${rec.labelAlt}`);
    } else {
      box.append(el("br"), "평소 입는 사이즈 표기 기준이에요. 실측을 등록하면 더 정확해져요.");
    }
  } else if (["top", "bottom", "shoes"].includes(p.type)) {
    box.append("내 사이즈를 등록하면 추천해 드려요. ", el("a", { href: "#", onclick: (e) => { e.preventDefault(); sheet.close(); openSettings(); }, text: "등록하기" }));
  } else {
    box.append("사이즈 추천 대상이 아닌 상품이에요.");
  }
  body.append(box);

  const keys = [...new Set(p.sizes.flatMap((s) => Object.keys(s.measurements || {})))];
  const order = [...MEASURE_FIELDS.top, ...MEASURE_FIELDS.bottom].map((f) => f.key);
  keys.sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const mine = state.profile.measurements[p.type] || {};

  const table = el("table", { class: "size-table" });
  table.append(el("thead", {}, el("tr", {}, el("th", { text: "사이즈" }), ...keys.map((k) => el("th", { text: MEASURE_LABELS[k] || k })), el("th", { text: "재고" }))));
  const tbody = el("tbody");
  for (const s of p.sizes) {
    const tr = el("tr", { class: `${rec && rec.label === s.label ? "pick" : ""} ${s.inStock ? "" : "out"}` });
    const name = [s.label, ...(s.aliases || [])].join(" / ");
    tr.append(el("td", { text: name }));
    for (const k of keys) {
      const v = s.measurements?.[k];
      const td = el("td", { text: v ?? "-" });
      const m = Number(mine[k]);
      if (v != null && m) {
        const d = Math.round((v - m) * 10) / 10;
        td.append(el("span", { class: `d ${d > 0 ? "plus" : d < 0 ? "minus" : ""}`, text: formatDiff(d) }));
      }
      tr.append(td);
    }
    tr.append(el("td", { text: s.inStock ? "○" : "품절" }));
    tbody.append(tr);
  }
  if (keys.some((k) => Number(mine[k]))) {
    tbody.append(el("tr", { class: "mine" }, el("td", { text: "내 옷" }), ...keys.map((k) => el("td", { text: Number(mine[k]) || "-" })), el("td")));
  }
  table.append(tbody);
  body.append(el("div", { class: "table-wrap" }, table));
  body.append(el("p", { class: "hint", text: keys.length ? `단위 cm, 단면 기준. ${p.sizeNote || ""} 사이트 실측과 측정 방법에 따라 1~3cm 오차가 있을 수 있어요.` : "이 상품은 실측 정보가 없어요." }));
  body.append(el("a", { class: "btn primary", href: p.url, target: "_blank", rel: "noopener", style: "width:100%", text: "상품 페이지에서 사이즈 선택하기 ↗" }));
  sheet.showModal();
}

// ---------- 설정 ----------

function buildMeasureInputs() {
  for (const [type, id, title] of [["top", "#measureTop", "상의"], ["bottom", "#measureBottom", "하의"]]) {
    const grid = $(id);
    grid.replaceChildren(
      el("h4", { text: title }),
      ...MEASURE_FIELDS[type].map((f) =>
        el("label", {}, f.label, el("input", { name: `m-${type}-${f.key}`, type: "number", inputmode: "decimal", step: "0.1", min: "0", max: "200", placeholder: "-" })),
      ),
    );
  }
}

function openSettings() {
  const form = $("#settingsForm");
  const p = state.profile;
  for (const t of ["top", "bottom", "shoes"]) form.elements[`label-${t}`].value = (p.labels[t] || []).join(", ");
  for (const t of ["top", "bottom"]) {
    for (const f of MEASURE_FIELDS[t]) form.elements[`m-${t}-${f.key}`].value = p.measurements[t]?.[f.key] ?? "";
  }
  $("#settingsSheet").showModal();
}

function readSettingsForm() {
  const form = $("#settingsForm");
  const profile = { labels: {}, measurements: { top: {}, bottom: {} } };
  for (const t of ["top", "bottom", "shoes"]) profile.labels[t] = parseLabelList(form.elements[`label-${t}`].value);
  for (const t of ["top", "bottom"]) {
    for (const f of MEASURE_FIELDS[t]) {
      const v = parseFloat(form.elements[`m-${t}-${f.key}`].value);
      if (v > 0) profile.measurements[t][f.key] = v;
    }
  }
  return profile;
}

function setupSettings() {
  buildMeasureInputs();
  $("#openSettings").addEventListener("click", openSettings);
  $("#settingsForm").addEventListener("submit", (e) => {
    e.preventDefault();
    state.profile = readSettingsForm();
    const saved = saveProfile(state.profile);
    $("#settingsSheet").close();
    refreshSizeInfo();
    toast(saved ? "저장했어요. 상품마다 추천 사이즈를 보여드릴게요." : "이 브라우저에서는 저장이 안 돼서 이번 방문에만 적용돼요.");
  });
  $("#resetProfile").addEventListener("click", () => {
    const form = $("#settingsForm");
    for (const input of form.querySelectorAll("input")) input.value = "";
  });
}

// ---------- 기타 ----------

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 2200);
}

// 시트 바깥(backdrop) 탭하면 닫기
for (const dlg of document.querySelectorAll("dialog.sheet")) {
  dlg.addEventListener("click", (e) => {
    if (e.target === dlg) dlg.close();
  });
}

document.addEventListener("keydown", (e) => {
  if (document.querySelector("dialog[open]") || e.target.closest?.("input, textarea, select")) return;
  // 버튼/링크에 포커스가 있을 때 Enter 는 그 요소의 기본 동작에 맡긴다
  if (e.key === "Enter" && e.target.closest?.("button, a")) return;
  if (e.key === "ArrowDown" || e.key === "j") { e.preventDefault(); goTo(state.current + 1); }
  else if (e.key === "ArrowUp" || e.key === "k") { e.preventDefault(); goTo(state.current - 1); }
  else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
    const g = feed.querySelectorAll(".card")[state.current]?.querySelector(".gallery");
    if (g) { e.preventDefault(); g.scrollBy({ left: (e.key === "ArrowRight" ? 1 : -1) * g.clientWidth, behavior: "smooth" }); }
  } else if (e.key === "Enter") {
    const p = state.list[state.current];
    if (p) window.open(p.url, "_blank", "noopener");
  }
});

setupSettings();
load().then(() => {
  if (state.data?.generatedAt) document.title = `Soltisy Watcher · ${timeAgo(state.data.generatedAt)} 업데이트`;
});
