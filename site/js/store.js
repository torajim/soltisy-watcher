// 브라우저 저장소 (프로필, 필터 상태). 사생활 보호 모드 등에서 실패해도 앱은 동작해야 한다.
import { emptyProfile } from "./sizing.js";

const PROFILE_KEY = "soltisy.profile.v1";
const PREFS_KEY = "soltisy.prefs.v1";

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
export const loadPrefs = () => ({ brand: "all", type: "all", ...(read(PREFS_KEY) || {}) });
export const savePrefs = (p) => write(PREFS_KEY, p);
