// 가상 피팅 (준비 중).
//
// 나중에 전신 사진 + 상품 이미지를 받아 합성 이미지를 돌려주는 백엔드(또는 외부 API)를 붙일 자리.
// 앱은 isAvailable() 로 버튼 활성화 여부를 정하고, tryOn() 결과 이미지를 카드 갤러리 맨 앞에 끼워 넣으면 된다.

export function isAvailable() {
  return false;
}

/**
 * @param {object} product  products.json 의 상품
 * @param {Blob} bodyPhoto  사용자 전신 사진
 * @returns {Promise<string>} 합성 이미지 URL
 */
export async function tryOn(product, bodyPhoto) {
  void product;
  void bodyPhoto;
  throw new Error("가상 피팅은 아직 준비 중이에요.");
}
