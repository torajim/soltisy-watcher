import { GENDER_FILTERS, TYPE_FILTERS, brandsKey, discountRate, filterProducts, formatPrice, imageWindow, interleave, matchesGender, normalizeBrands, restoreIndex, staleNotice, tabBrands, timeAgo } from "./feed.js";
import { MEASURE_FIELDS, MEASURE_LABELS } from "./sizing.js";
import { favoriteProducts, isFavorite, refreshFavorites, toggleFavorite } from "./favorites.js";
import { clipboardText, itemFromSearch, shareData } from "./share.js";
import { clearLegacyProfile, loadFavorites, loadPosition, loadPrefs, saveFavorites, savePosition, savePrefs } from "./store.js";

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
  favorites: loadFavorites(),
  // "feed" 또는 "favorites" (찜 모아보기)
  view: "feed",
  current: 0,
  // 공유 링크(?item=<id>)로 들어왔을 때 처음에 보여줄 상품
  sharedId: null,
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
  const missingShared = takeSharedItem();
  // 찜해 둔 상품의 가격·재고를 최신 데이터로 맞춘다
  const fresh = refreshFavorites(state.favorites, state.data.products);
  if (fresh !== state.favorites) {
    state.favorites = fresh;
    saveFavorites(fresh);
  }
  buildAll();
  render();
  if (missingShared) toast("공유받은 상품이 지금 피드에는 없어요. 함께 받은 공식 상품 링크로 확인해 주세요.", null, 5000);
}

// 설정한 성별의 상품만 모아 피드를 만든다. 고른 브랜드에 그 성별 상품이 없으면 ALL 로 돌린다.
function buildAll() {
  const brandOrder = state.data.brands.map((b) => b.id);
  // 공유받은 상품은 성별 설정과 달라도 보여준다
  const shown = state.data.products.filter((p) => matchesGender(p, state.prefs.gender) || p.id === state.sharedId);
  state.all = interleave(shown, brandOrder);
  const feedBrandIds = tabBrands(state.data.brands, state.all).map((b) => b.id);
  state.prefs.brands = normalizeBrands(state.prefs, feedBrandIds);
}

function setGender(gender) {
  if (state.prefs.gender === gender) return;
  state.prefs.gender = gender;
  savePrefs(state.prefs);
  buildAll();
  render();
}

// 공유 링크로 들어오면 전체 피드에서 그 상품부터 보여준다. 상품이 데이터에서 빠졌으면 true.
function takeSharedItem() {
  const id = itemFromSearch(location.search);
  if (!id) return false;
  // 새로고침하거나 홈 화면 앱으로 다시 열 때 또 그 상품으로 튀지 않도록 주소에서 지운다
  try {
    history.replaceState(null, "", location.pathname);
  } catch {}
  if (!state.data.products.some((p) => p.id === id)) return true;
  state.prefs.brands = [];
  state.prefs.type = "all";
  state.sharedId = id;
  return false;
}

function showState(msg) {
  feed.replaceChildren(el("div", { class: "state", text: msg }));
  counter.hidden = true;
}

// ---------- 필터 ----------

function renderChips() {
  const counts = {};
  for (const p of state.all) counts[p.brand] = (counts[p.brand] || 0) + 1;
  // 상품을 직접 가져오지 못하는 브랜드(바로가기 전용·수집된 상품 없음)는 목록에서 뺀다
  const feedBrands = tabBrands(state.data.brands, state.all);
  const items = [
    { id: "all", name: "ALL", count: state.all.length },
    ...feedBrands.map((b) => ({ id: b.id, name: b.name, count: counts[b.id] || 0, notice: staleNotice(b) })),
  ];
  const countText = (b) => (b.notice ? `${b.count} !` : String(b.count));

  state.brandItems = items;

  // 상단에는 지금 고른 브랜드만 짧게 보여주고, 누르면 전체 브랜드를 한 화면에 펼친다
  const picked = items.filter((b) => state.prefs.brands.includes(b.id));
  const inBrand = filterProducts(state.all, { brands: state.prefs.brands });
  const stale = picked.filter((b) => b.notice);
  const label = !picked.length ? "ALL" : picked.length === 1 ? picked[0].name : `${picked[0].name} 외 ${picked.length - 1}`;
  const trigger = $("#openBrands");
  trigger.replaceChildren(
    el("span", { class: "label", text: label }),
    el("span", { class: "n", text: stale.length ? `${inBrand.length} !` : String(inBrand.length) }),
    el("span", { class: "caret", "aria-hidden": "true", text: "▾" }),
  );
  trigger.classList.toggle("stale", stale.length > 0);
  trigger.title = picked.map((b) => b.name).join(", ");

  // 수집에 실패한 브랜드를 고르면 오래된 데이터라는 걸 알려준다
  const notice = $("#brandNotice");
  notice.replaceChildren(...stale.map((b) => el("div", { text: b.notice })));
  notice.hidden = !stale.length;

  const types = $("#typeChips");
  types.replaceChildren(
    ...TYPE_FILTERS.filter((t) => t.id === "all" || inBrand.some((p) => p.type === t.id)).map((t) =>
      el("button", { class: "chip", type: "button", "aria-pressed": String(state.prefs.type === t.id), onclick: () => setPref("type", t.id) }, t.label),
    ),
  );
}

// ---------- 브랜드 고르기 (여러 개) ----------

// 시트 안에서 고르는 중인 목록. 시트를 닫을 때 한 번에 적용한다.
let draftBrands = [];

function openBrandSheet() {
  draftBrands = [...state.prefs.brands];
  renderBrandSheet();
  const sheet = $("#brandSheet");
  sheet.showModal();
  // 브랜드가 많아 목록이 길어져도 지금 고른 브랜드가 보이게
  sheet.querySelector('.brand-tile[aria-pressed="true"]')?.scrollIntoView({ block: "nearest" });
}

function toggleDraft(id) {
  if (id === "all") draftBrands = [];
  else if (draftBrands.includes(id)) draftBrands = draftBrands.filter((b) => b !== id);
  else draftBrands = [...draftBrands, id];
  renderBrandSheet();
}

function renderBrandSheet() {
  const items = state.brandItems || [];
  const countText = (b) => (b.notice ? `${b.count} !` : String(b.count));
  $("#brandGrid").replaceChildren(
    ...items.map((b) =>
      el(
        "button",
        {
          class: ["brand-tile", b.id === "all" && "all", b.notice && "stale"].filter(Boolean).join(" "),
          type: "button",
          title: b.notice,
          "aria-pressed": String(b.id === "all" ? !draftBrands.length : draftBrands.includes(b.id)),
          onclick: () => toggleDraft(b.id),
        },
        el("span", { class: "check", "aria-hidden": "true" }),
        el("span", { class: "label", text: b.name }),
        el("span", { class: "n", text: countText(b) }),
      ),
    ),
  );
  const n = filterProducts(state.all, { brands: draftBrands }).length;
  $("#applyBrands").textContent = draftBrands.length ? `${draftBrands.length}개 브랜드 · ${n}개 보기` : `전체 브랜드 · ${n}개 보기`;
}

function applyDraftBrands() {
  const next = normalizeBrands({ brands: draftBrands }, state.brandItems.map((b) => b.id));
  if (brandsKey(next) === brandsKey(state.prefs.brands)) return;
  state.prefs.brands = next;
  state.prefs.type = "all";
  savePrefs(state.prefs);
  render();
}

function setPref(key, value) {
  if (state.prefs[key] === value) {
    feed.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  state.prefs[key] = value;
  savePrefs(state.prefs);
  render();
}

// ---------- 피드 ----------

function render() {
  renderTopbar();
  if (state.view === "favorites") {
    state.list = favoriteProducts(state.favorites, state.data.products);
  } else {
    renderChips();
    state.list = filterProducts(state.all, state.prefs);
  }
  if (!state.list.length) {
    showState(state.view === "favorites" ? "아직 찜한 상품이 없어요.\n상품 아래 ♡ 를 눌러 모아 보세요." : "표시할 상품이 없어요.");
    return;
  }
  const tpl = $("#cardTpl");
  const cards = state.list.map((p, i) => buildCard(tpl, p, i));
  feed.replaceChildren(...cards);

  // 필터(브랜드·종류)마다 마지막으로 보던 상품에서 이어서 보여준다
  const shared = state.sharedId ? state.list.findIndex((p) => p.id === state.sharedId) : -1;
  state.sharedId = null;
  const start = shared >= 0 ? shared : restoreIndex(state.list, loadPosition(positionKey()));
  state.current = start;
  if (shared >= 0) {
    feed.scrollTop = cards[start].offsetTop;
  } else if (start > 0) {
    feed.scrollTop = cards[start].offsetTop;
    toast(`${start + 1}번째부터 이어서 봐요`, { label: "처음부터", onClick: () => goTo(0) }, 4000);
  } else {
    feed.scrollTop = 0;
  }
  updateImageWindow();
  observeCards(cards);
  updateCounter();
}

function positionKey() {
  if (state.view === "favorites") return "favorites";
  return `${state.prefs.gender}|${brandsKey(state.prefs.brands)}|${state.prefs.type}`;
}

function buildCard(tpl, p, index) {
  const card = tpl.content.firstElementChild.cloneNode(true);
  card.dataset.index = index;

  // 이미지는 여기서 만들지 않는다. 현재 카드 주변만 updateImageWindow() 가 채운다.
  const gallery = $(".gallery", card);
  const dots = $(".dots", card);
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
  $(".share-btn", card).addEventListener("click", () => shareProduct(p));
  const fav = $(".fav-btn", card);
  syncFavButton(fav, p.id);
  fav.addEventListener("click", () => onToggleFavorite(p, fav));
  $(".gone", card).hidden = !p.gone;
  if (!p.sizes.length) $(".size-btn", card).hidden = true;

  $(".sizes", card).replaceChildren(...p.sizes.map((s) => el("span", { class: `sz${s.inStock ? "" : " out"}`, text: s.label })));
  return card;
}

// ---------- 찜 ----------

function syncFavButton(btn, id) {
  const on = isFavorite(state.favorites, id);
  btn.setAttribute("aria-pressed", String(on));
  btn.setAttribute("aria-label", on ? "찜 해제" : "찜하기");
  btn.title = on ? "찜 해제" : "찜하기";
}

function onToggleFavorite(p, btn) {
  const { gone, ...product } = p;
  state.favorites = toggleFavorite(state.favorites, product);
  const saved = saveFavorites(state.favorites);
  syncFavButton(btn, p.id);
  updateFavCount();
  // 찜 모아보기 안에서 해제해도 카드는 그대로 두어 화면이 튀지 않게 한다. 다시 열면 빠져 있다.
  if (!isFavorite(state.favorites, p.id)) {
    toast("찜을 해제했어요");
  } else if (!saved) {
    toast("이 브라우저에서는 저장이 안 돼서 이번 방문에만 남아요.");
  } else if (state.view !== "favorites") {
    toast("찜했어요", { label: "모아보기", onClick: () => setView("favorites") });
  } else {
    toast("다시 찜했어요");
  }
}

function updateFavCount() {
  const n = state.favorites.length;
  const badge = $("#favCount");
  badge.textContent = n > 99 ? "99+" : String(n);
  badge.hidden = !n;
  if (state.view === "favorites") $("#closeFavorites").replaceChildren(el("span", { "aria-hidden": "true", text: "←" }), `찜한 상품 ${n}`);
}

function renderTopbar() {
  const fav = state.view === "favorites";
  $("#openFavorites").setAttribute("aria-pressed", String(fav));
  $("#openFavorites").setAttribute("aria-label", fav ? "찜 모아보기 닫기" : "찜 모아보기");
  $("#openBrands").hidden = fav;
  $("#typeChips").hidden = fav;
  $("#closeFavorites").hidden = !fav;
  if (fav) $("#brandNotice").hidden = true;
  updateFavCount();
}

function setView(view) {
  if (state.view === view) return;
  state.view = view;
  $("#toast").hidden = true;
  render();
}

// ---------- 이미지 메모리 관리 ----------
// 사진을 한 번 올리면 계속 들고 있으면 수십 장 넘기는 사이 디코딩된 이미지가 1GB 를 넘어
// iOS(특히 홈 화면 앱)가 페이지를 강제로 다시 로드한다. 현재 카드 주변만 이미지를 붙이고
// 멀어진 카드는 이미지를 떼어 메모리를 돌려준다.

function hydrateCard(card) {
  if (card.dataset.hydrated) return;
  card.dataset.hydrated = "1";
  const p = state.list[Number(card.dataset.index)];
  const gallery = $(".gallery", card);
  const dots = $(".dots", card);
  const isCurrent = Number(card.dataset.index) === state.current;
  p.images.forEach((src, i) => {
    const img = el("img", { src, alt: "", loading: isCurrent && i === 0 ? "eager" : "lazy", decoding: "async", draggable: "false" });
    const dot = el("i", { class: i === 0 ? "on" : "" });
    img.addEventListener("error", () => onImageError(img, dot, card));
    gallery.append(img);
    dots.append(dot);
  });
  dots.hidden = p.images.length < 2;
}

function dehydrateCard(card) {
  if (!card.dataset.hydrated) return;
  delete card.dataset.hydrated;
  const gallery = $(".gallery", card);
  // src 를 비워야 WebKit 이 디코딩된 비트맵을 바로 놓아준다
  for (const img of gallery.querySelectorAll("img")) img.src = "data:,";
  gallery.replaceChildren();
  gallery.scrollLeft = 0;
  $(".dots", card).replaceChildren();
}

function updateImageWindow() {
  const cards = feed.querySelectorAll(".card");
  const { from, to } = imageWindow(state.current, cards.length);
  cards.forEach((card, i) => (i >= from && i <= to ? hydrateCard(card) : dehydrateCard(card)));
}

// 이미지 로드 실패: 한 번 재시도 후 그 컷을 빼고, 전부 실패하면 안내 문구를 보여준다.
function onImageError(img, dot, card) {
  if (!img.isConnected) return; // 이미 화면에서 떼어낸 이미지
  if (!img.dataset.retried) {
    img.dataset.retried = "1";
    const src = img.src;
    setTimeout(() => {
      if (img.isConnected) img.src = src + (src.includes("?") ? "&" : "?") + "r=1";
    }, 1200);
    return;
  }
  img.remove();
  dot.remove();
  const gallery = $(".gallery", card);
  const dots = $(".dots", card);
  if (dots.children.length < 2) dots.hidden = true;
  if (!gallery.querySelector("img")) gallery.append(el("div", { class: "state", text: "이미지를 불러오지 못했어요" }));
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
          updateImageWindow();
          savePosition(positionKey(), { id: state.list[state.current].id, index: state.current });
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

// ---------- 공유 ----------
// 휴대폰에서는 기본 공유 창(카카오톡·메시지·인스타 DM 등)을 띄우고, 안 되면 링크를 복사한다.

async function shareProduct(p) {
  const data = shareData(p, location.href);
  if (navigator.share && (!navigator.canShare || navigator.canShare(data))) {
    try {
      await navigator.share(data);
      return;
    } catch (e) {
      if (e?.name === "AbortError") return; // 사용자가 공유 창을 닫음
      console.warn(e);
    }
  }
  try {
    await navigator.clipboard.writeText(clipboardText(p, location.href));
    toast("링크를 복사했어요. 원하는 곳에 붙여 넣어 보내세요.");
  } catch {
    toast("이 브라우저에서는 공유할 수 없어요.");
  }
}

// ---------- 사이즈 시트 ----------

function openSizeSheet(p) {
  const sheet = $("#sizeSheet");
  $("#sizeSheetTitle").textContent = `${p.brandName} · 사이즈`;
  const body = $("#sizeSheetBody");
  body.replaceChildren();

  const keys = [...new Set(p.sizes.flatMap((s) => Object.keys(s.measurements || {})))];
  const order = [...MEASURE_FIELDS.top, ...MEASURE_FIELDS.bottom].map((f) => f.key);
  keys.sort((a, b) => order.indexOf(a) - order.indexOf(b));

  const table = el("table", { class: "size-table" });
  table.append(el("thead", {}, el("tr", {}, el("th", { text: "사이즈" }), ...keys.map((k) => el("th", { text: MEASURE_LABELS[k] || k })), el("th", { text: "재고" }))));
  const tbody = el("tbody");
  for (const s of p.sizes) {
    const tr = el("tr", { class: s.inStock ? "" : "out" });
    const name = [s.label, ...(s.aliases || [])].join(" / ");
    tr.append(el("td", { text: name }));
    for (const k of keys) tr.append(el("td", { text: s.measurements?.[k] ?? "-" }));
    tr.append(el("td", { text: s.inStock ? "○" : "품절" }));
    tbody.append(tr);
  }
  table.append(tbody);
  body.append(el("div", { class: "table-wrap" }, table));
  body.append(el("p", { class: "hint", text: keys.length ? `단위 cm, 단면 기준. ${p.sizeNote || ""} 사이트 실측과 측정 방법에 따라 1~3cm 오차가 있을 수 있어요.` : "이 상품은 실측 정보가 없어요." }));
  body.append(el("a", { class: "btn primary", href: p.url, target: "_blank", rel: "noopener", style: "width:100%", text: "상품 페이지에서 사이즈 선택하기 ↗" }));
  sheet.showModal();
}

// ---------- 설정 ----------

function buildGenderPicker() {
  $("#genderPicker").replaceChildren(
    ...GENDER_FILTERS.map((g) =>
      el("button", { class: "chip", type: "button", "data-gender": g.id, onclick: () => { setGender(g.id); syncGenderPicker(); } }, g.label),
    ),
  );
}

function syncGenderPicker() {
  for (const b of $("#genderPicker").children) b.setAttribute("aria-pressed", String(b.dataset.gender === state.prefs.gender));
}

function openSettings() {
  syncGenderPicker();
  $("#settingsSheet").showModal();
}

function setupSettings() {
  buildGenderPicker();
  $("#openSettings").addEventListener("click", openSettings);
  $("#openBrands").addEventListener("click", openBrandSheet);
  $("#openFavorites").addEventListener("click", () => setView(state.view === "favorites" ? "feed" : "favorites"));
  $("#closeFavorites").addEventListener("click", () => setView("feed"));
  // 적용 버튼·닫기·바깥 탭 어느 쪽으로 닫아도 고른 대로 적용한다
  $("#brandSheet").addEventListener("close", applyDraftBrands);
}

// ---------- 기타 ----------

let toastTimer;
function toast(msg, action, duration = 2200) {
  const t = $("#toast");
  t.replaceChildren(msg);
  if (action) {
    t.append(
      el("button", {
        type: "button",
        text: action.label,
        onclick: () => {
          t.hidden = true;
          action.onClick();
        },
      }),
    );
  }
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), duration);
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

clearLegacyProfile();
setupSettings();
load().then(() => {
  if (state.data?.generatedAt) document.title = `Soltisy Watcher · ${timeAgo(state.data.generatedAt)} 업데이트`;
});
