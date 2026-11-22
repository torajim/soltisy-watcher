// 상품 공유 (순수 함수). 공유 링크는 앱 주소에 ?item=<상품 id> 를 붙인 딥링크다.
import { formatPrice } from "./feed.js";

export const ITEM_PARAM = "item";

/** 앱 주소(현재 페이지)에서 쿼리·해시를 떼고 ?item=<id> 를 붙인 공유 링크. */
export function itemLink(pageHref, id) {
  const url = new URL(pageHref);
  url.search = "";
  url.hash = "";
  url.searchParams.set(ITEM_PARAM, id);
  return url.toString();
}

/** 주소의 쿼리 문자열에서 공유된 상품 id 를 꺼낸다. 없으면 null. */
export function itemFromSearch(search) {
  const id = new URLSearchParams(search).get(ITEM_PARAM);
  return id ? id.trim() || null : null;
}

/** 공유 본문: 브랜드·상품명·가격과 공식 상품 링크. 앱에서 빠진 상품이어도 받은 사람이 볼 수 있게. */
export function shareText(p) {
  return [`[${p.brandName}] ${p.name}`, formatPrice(p.price), `공식 상품 페이지: ${p.url}`].join("\n");
}

/** navigator.share 에 넘길 데이터. */
export function shareData(p, pageHref) {
  return { title: `${p.brandName} ${p.name}`, text: shareText(p), url: itemLink(pageHref, p.id) };
}

/** 공유 시트를 못 쓰는 환경(PC 등)에서 클립보드에 복사할 글. */
export function clipboardText(p, pageHref) {
  return `${shareText(p)}\n${itemLink(pageHref, p.id)}`;
}
