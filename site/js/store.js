// 브라우저 저장소 (프로필, 필터 상태). 사생활 보호 모드 등에서 실패해도 앱은 동작해야 한다.
import { emptyProfile } from "./sizing.js";
import { normalizeBrands } from "./feed.js";

const PROFILE_KEY = "soltisy.profile.v1";
const PREFS_KEY = "soltisy.prefs.v1";
const POSITION_KEY = "soltisy.position.v1";

function read(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function loadProfile() {
  const base = emptyProfile();
  const saved = read(PROFILE_KEY);
  if (!saved) return base;
  return {
    labels: { ...base.labels, ...(saved.labels || {}) },
    measurements: {
      top: { ...(saved.measurements?.top || {}) },
      bottom: { ...(saved.measurements?.bottom || {}) },
    },
  };
}

export const saveProfile = (p) => write(PROFILE_KEY, p);
// gender: 보여줄 성별 (men / women / all). 처음에는 지금까지처럼 남성만.
// brands: 고른 브랜드 id 목록 (비어 있으면 전체). 예전에는 brand 하나만 저장했다.
export function loadPrefs() {
  const saved = read(PREFS_KEY) || {};
  const { brand, ...rest } = saved;
  return { type: "all", gender: "men", ...rest, brands: normalizeBrands(saved) };
}
export const savePrefs = (p) => write(PREFS_KEY, p);

// 필터 조합별 마지막으로 본 상품: { "all|all": { id, index }, ... }
export function loadPosition(key) {
  return (read(POSITION_KEY) || {})[key] || null;
}

export function savePosition(key, pos) {
  const all = read(POSITION_KEY) || {};
  all[key] = pos;
  return write(POSITION_KEY, all);
}
