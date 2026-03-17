import io
import streamlit as st
from capture_core import run_capture, make_zip

st.set_page_config(
    page_title="Samsung 상품 캡처",
    page_icon="📸",
    layout="centered",
)

st.markdown("""
<style>
  .block-container { max-width: 820px; padding-top: 2rem; }
  .stTextInput > div > div > input { font-size: 14px; }
  .log-box {
    background: #1e1e1e; color: #d4d4d4;
    font-family: monospace; font-size: 12px;
    padding: 12px 16px; border-radius: 8px;
    max-height: 220px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-all;
  }
  .result-header {
    background: #f0f7ff; border-left: 4px solid #2563eb;
    padding: 10px 16px; border-radius: 0 8px 8px 0;
    font-weight: 600; font-size: 15px; margin: 1rem 0 0.5rem;
  }
</style>
""", unsafe_allow_html=True)

st.title("📸 Samsung 상품 캡처")
st.caption("URL을 최대 3개까지 입력하면 대표이미지 + 상품상세를 자동으로 캡처합니다.")
st.divider()

# ── URL 입력 (최대 3개) ───────────────────────────────────────
url1 = st.text_input("상품 URL 1", placeholder="https://www.samsung.com/sec/...", key="url1")
url2 = st.text_input("상품 URL 2 (선택)", placeholder="https://www.samsung.com/sec/...", key="url2")
url3 = st.text_input("상품 URL 3 (선택)", placeholder="https://www.samsung.com/sec/...", key="url3")

urls = [u.strip() for u in [url1, url2, url3] if u.strip()]

# ── 옵션 ─────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    width = st.selectbox("캡처 너비", [1000, 1280, 768], index=0,
                         format_func=lambda x: f"{x}px")
with col2:
    wait_sec = st.selectbox("페이지 대기 시간", [4, 5, 6, 8, 10], index=1,
                            format_func=lambda x: f"{x}초")

valid_urls = [u for u in urls if u.startswith("http")]
invalid    = [u for u in urls if u and not u.startswith("http")]

if invalid:
    st.warning(f"⚠️  올바르지 않은 URL: {', '.join(invalid)}")

run_btn = st.button(
    f"🚀 캡처 시작 ({len(valid_urls)}개 URL)",
    type="primary",
    use_container_width=True,
    disabled=len(valid_urls) == 0,
)

# ── 실행 ─────────────────────────────────────────────────────
if run_btn and valid_urls:
    import capture_core
    capture_core.WIDTH    = width
    capture_core.WAIT_SEC = wait_sec

    all_results = []

    for idx, url in enumerate(valid_urls, 1):
        st.markdown(
            f'<div class="result-header">🔗 [{idx}/{len(valid_urls)}] {url[:70]}</div>',
            unsafe_allow_html=True,
        )

        log_box = st.empty()
        logs = []

        def make_log(box, log_list):
            def log(msg):
                log_list.append(msg)
                box.markdown(
                    '<div class="log-box">' + "\n".join(log_list[-30:]) + '</div>',
                    unsafe_allow_html=True,
                )
            return log

        logger = make_log(log_box, logs)

        with st.spinner(f"캡처 중... ({idx}/{len(valid_urls)})"):
            result = run_capture(url, log=logger)

        all_results.append(result)

        if result["error"]:
            st.error(f"❌ 캡처 실패: {result['error']}")
            continue

        product_name = result["product_name"]
        detail_png   = result["detail_png"]
        images       = result["images"]

        st.success(f"✅ **{product_name}** — 대표이미지 {len(images)}장")

        # 상품상세 미리보기
        if detail_png:
            with st.expander("🖼️ 상품상세 미리보기", expanded=True):
                st.image(detail_png, use_column_width=True)

        # 대표이미지 미리보기
        if images:
            with st.expander(f"📷 대표이미지 ({len(images)}장)", expanded=False):
                cols = st.columns(min(len(images), 4))
                for i, img in enumerate(images):
                    with cols[i % 4]:
                        st.image(img["data"], caption=img["filename"], use_column_width=True)

        # 개별 ZIP 다운로드
        zip_data = make_zip(product_name, detail_png, images)
        st.download_button(
            label=f"📦 {product_name}.zip 다운로드 ({len(zip_data)//1024} KB)",
            data=zip_data,
            file_name=f"{product_name}.zip",
            mime="application/zip",
            key=f"zip_{idx}",
            use_container_width=True,
        )

        st.divider()

    # ── 전체 결과 합치기 (2개 이상 성공 시) ──────────────────
    success_results = [r for r in all_results if not r["error"] and r["detail_png"]]
    if len(success_results) >= 2:
        st.subheader("📦 전체 ZIP (모든 상품 합치기)")
        buf = io.BytesIO()
        import zipfile
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in success_results:
                pname = r["product_name"]
                if r["detail_png"]:
                    zf.writestr(f"{pname}/{pname}_상품상세.png", r["detail_png"])
                for img in r["images"]:
                    zf.writestr(f"{pname}/대표이미지/{img['filename']}", img["data"])
        all_zip = buf.getvalue()
        st.download_button(
            label=f"⬇️ 전체 합치기 ZIP ({len(all_zip)//1024} KB)",
            data=all_zip,
            file_name="samsung_상품_전체.zip",
            mime="application/zip",
            type="primary",
            key="zip_all",
            use_container_width=True,
        )
