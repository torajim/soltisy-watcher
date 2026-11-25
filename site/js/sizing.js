// 상품 실측표에 쓰는 항목 이름과 순서 (브라우저/Node 공용).
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
