# Samsung 상품 캡처 도구

Samsung 상품 페이지 URL을 입력하면 **대표이미지 원본 + 상품상세 캡처**를 자동으로 수행합니다.

## 📦 결과물
- `상품명_상품상세.png` — feature-benefit, textbox, FAQ, itm-notice, 스펙 합체 캡처
- `상품명/01_*.png` ~ — 대표이미지 원본 전체
- ZIP으로 일괄 다운로드 가능

## 🚀 로컬 실행

```bash
pip install -r requirements.txt
python -m playwright install chromium
streamlit run app.py
```

## ☁️ Streamlit Cloud 배포

1. GitHub 리포지토리 생성 후 Push
2. [share.streamlit.io](https://share.streamlit.io) 접속
3. New app → 리포지토리 선택 → Main file: `app.py`
4. Deploy!

> Streamlit Cloud는 `packages.txt` 를 읽어 시스템 패키지를 자동 설치합니다.  
> Playwright Chromium은 `setup.sh` 없이 `playwright install chromium` 으로 처리됩니다.

## 🖥️ VS Code 로컬 테스트 (터미널 방식)

```bash
python capture_test.py
# 실행 후 URL 입력
```
