# 📸 Samsung 상품 캡처 도구

Samsung 상품 페이지 URL을 입력하면 **대표이미지 + 상품상세 이미지**를 자동으로 캡처합니다.

---

## 주요 기능

- URL 최대 3개 동시 처리
- 대표이미지 원본 수집 (500×500 JPG 리사이즈)
- 대표이미지 개별 선택 후 다운로드
- 상품상세 전체 캡처 (특장점 · 텍스트 · FAQ · 유의사항 · 스펙 포함)
- 상품별 ZIP 개별 다운로드 / 전체 합치기 ZIP 다운로드
- 초기화 버튼으로 빠른 재사용

## 캡처 영역

| 영역 | 설명 |
|---|---|
| feature-benefit | 특징 / 혜택 |
| textbox-simple | 텍스트 설명 |
| FAQ | 전체 펼침 |
| itm-notice | 구매 유의사항 |
| spec-all | 스펙 (AJAX 로드 후 펼침) |

---

## 로컬 실행 (VS Code)

```bash
# 패키지 설치 (최초 1회)
pip install selenium pillow

# 실행
python capture_test.py
```

Chrome 브라우저가 설치되어 있어야 합니다.  
ChromeDriver는 selenium 4.x에서 자동 설치됩니다.

---

## 웹앱 로컬 실행 (Streamlit)

```bash
pip install streamlit selenium pillow
streamlit run app.py
```

---

## Streamlit Cloud 배포

1. GitHub 리포지토리에 Push
2. [share.streamlit.io](https://share.streamlit.io) → New app
3. 리포지토리 선택 → Main file: `app.py` → Deploy

---

## 파일 구조

```
app.py              ← Streamlit 웹앱
capture_core.py     ← 핵심 캡처 로직 (selenium 기반)
capture_test.py     ← VS Code 로컬 실행용
requirements.txt    ← streamlit / selenium / pillow
packages.txt        ← Streamlit Cloud 시스템 패키지 (chromium)
runtime.txt         ← Python 버전 지정
.streamlit/
└── config.toml
```

## 결과물 구조

```
상품명_상품상세.png          ← 상품상세 캡처
상품명/
├── 01_이미지명.jpg          ← 대표이미지 (500×500 JPG)
├── 02_이미지명.jpg
└── ...
samsung_capture_all.zip    ← 전체 합치기 (2개 이상 시)
```
