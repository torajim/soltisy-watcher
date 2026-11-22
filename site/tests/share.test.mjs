import { test } from "node:test";
import assert from "node:assert/strict";
import { clipboardText, itemFromSearch, itemLink, shareData, shareText } from "../js/share.js";

const P = { id: "solid:123", brandName: "솔리드옴므", name: "울 코트", price: 955000, url: "https://shop.example/p/123" };
const PAGE = "https://torajim.github.io/soltisy-watcher/?item=old:1#x";

test("공유 링크는 앱 주소에 ?item=<id> 만 붙인다", () => {
  assert.equal(itemLink(PAGE, "solid:123"), "https://torajim.github.io/soltisy-watcher/?item=solid%3A123");
});

test("공유 링크에서 상품 id 를 다시 꺼낸다", () => {
  const link = new URL(itemLink(PAGE, "prada:SPH 1/2&x"));
  assert.equal(itemFromSearch(link.search), "prada:SPH 1/2&x");
  assert.equal(itemFromSearch(""), null);
  assert.equal(itemFromSearch("?item="), null);
  assert.equal(itemFromSearch("?other=1"), null);
});

test("공유 본문에 브랜드·상품명·가격·공식 링크가 들어간다", () => {
  assert.equal(shareText(P), "[솔리드옴므] 울 코트\n₩955,000\n공식 상품 페이지: https://shop.example/p/123");
  const d = shareData(P, PAGE);
  assert.equal(d.title, "솔리드옴므 울 코트");
  assert.equal(d.url, "https://torajim.github.io/soltisy-watcher/?item=solid%3A123");
  assert.ok(clipboardText(P, PAGE).endsWith("\nhttps://torajim.github.io/soltisy-watcher/?item=solid%3A123"));
});
