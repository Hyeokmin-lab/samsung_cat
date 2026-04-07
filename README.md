# 📸 Samsung 상품 캡처 도구

Samsung 상품 페이지 URL을 입력하면 **대표이미지 + 상품상세**를 자동으로 캡처하는 웹앱입니다.

---

## 주요 기능

- URL 최대 3개 동시 처리 (Chrome 1회 시작으로 빠르게 처리)
- 상품상세 캡처 (특장점 · FAQ 전체 펼침 · 스펙 자동 로딩 · 구매 유의사항)
- 스펙 탭별 개별 캡처 — 탭이 여러 개인 상품은 탭마다 클릭 후 세로 합체 (옵션)
- 대표이미지 500×500 JPG 다운로드 (체크박스로 원하는 이미지만 선택)
- 모든 이미지 JPG 형식으로 저장 (상품상세 · 스펙 · 대표이미지 전부)
- 상품명으로 폴더/파일명 자동 생성
- 개별 ZIP · 전체 합치기 ZIP 다운로드
- 초기화 버튼으로 새 작업 즉시 시작

---

## 결과물 구조

```
상품명.zip
└── 상품명_상품상세.jpg
└── 상품명_스펙.jpg       ← 스펙 탭별 캡처 옵션 사용 시
└── 상품명/
    ├── 01_이미지명.jpg
    ├── 02_이미지명.jpg
    └── ...
```

---

## 로컬 실행

```bash
# 1. 패키지 설치
pip install selenium pillow

# 2. 실행 (터미널 입력 방식)
python capture_test.py

# 3. 웹앱 실행
pip install streamlit
streamlit run app.py
```

> Chrome 브라우저가 설치되어 있어야 합니다.  
> ChromeDriver는 selenium 4.x에서 자동 설치됩니다.

---

## Streamlit Cloud 배포

1. GitHub 리포지토리에 Push
2. [share.streamlit.io](https://share.streamlit.io) → New app
3. 리포지토리 선택 → Main file: `app.py` → Deploy

> `packages.txt`로 시스템 chromium을 자동 설치합니다.

---

## 파일 구성

| 파일 | 설명 |
|---|---|
| `app.py` | Streamlit 웹앱 |
| `capture_core.py` | 캡처 핵심 로직 (selenium) |
| `capture_test.py` | VS Code 로컬 실행용 |
| `requirements.txt` | Python 패키지 |
| `packages.txt` | 시스템 패키지 (chromium) |
| `runtime.txt` | Python 버전 지정 |

---

## 옵션

| 옵션 | 기본값 | 설명 |
|---|---|---|
| 캡처 너비 | 768px | 768 / 1000 / 1280px 선택 |
| 페이지 대기 시간 | 3초 | 느린 페이지는 5~8초 권장 |
| 스펙 탭별 개별 캡처 | 해제 | 탭이 여러 개인 상품에만 체크 |
