import io
import zipfile
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
  .log-box {
    background: #1e1e1e; color: #d4d4d4;
    font-family: monospace; font-size: 12px;
    padding: 12px 16px; border-radius: 8px;
    max-height: 200px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-all;
  }
  .result-header {
    background: #f0f7ff; border-left: 4px solid #2563eb;
    padding: 10px 16px; border-radius: 0 8px 8px 0;
    font-weight: 600; font-size: 15px; margin: 1rem 0 0.5rem;
  }
</style>
""", unsafe_allow_html=True)

col_title, col_reset = st.columns([5, 1])
with col_title:
    st.title("📸 Samsung 상품 캡처")
    st.caption("URL을 최대 3개까지 입력하면 대표이미지 + 상품상세를 자동으로 캡처합니다.")
with col_reset:
    st.write("")
    st.write("")
    if st.session_state.get("results") and st.button("🔄 초기화", use_container_width=True):
        st.session_state.results = {}
        st.session_state.running = False
        st.session_state.urls_to_process = []
        st.rerun()
st.divider()

# ── session_state 초기화 ──────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = {}   # {url: result_dict}
if "running" not in st.session_state:
    st.session_state.running = False

# ── 입력 폼 ──────────────────────────────────────────────────
with st.form("capture_form"):
    url1 = st.text_input("상품 URL 1", placeholder="https://www.samsung.com/sec/...")
    url2 = st.text_input("상품 URL 2 (선택)", placeholder="https://www.samsung.com/sec/...")
    url3 = st.text_input("상품 URL 3 (선택)", placeholder="https://www.samsung.com/sec/...")
    col1, col2 = st.columns(2)
    with col1:
        width = st.selectbox("캡처 너비", [768, 1000, 1280], index=0,
                             format_func=lambda x: f"{x}px")
    with col2:
        wait_sec = st.selectbox("페이지 대기 시간", [3, 4, 5, 6, 8, 10], index=0,
                                format_func=lambda x: f"{x}초")
    submitted = st.form_submit_button("🚀 캡처 시작", type="primary", use_container_width=True)

# ── 캡처 실행 ─────────────────────────────────────────────────
if submitted and not st.session_state.running:
    urls = [u.strip() for u in [url1, url2, url3] if u.strip() and u.strip().startswith("http")]
    invalid = [u.strip() for u in [url1, url2, url3] if u.strip() and not u.strip().startswith("http")]
    if invalid:
        st.warning(f"⚠️  올바르지 않은 URL 제외: {', '.join(invalid)}")
    if not urls:
        st.error("유효한 URL을 1개 이상 입력해주세요.")
    else:
        # 새 실행 시 결과 초기화
        st.session_state.results = {}
        st.session_state.running = True
        st.session_state.urls_to_process = urls
        st.session_state.width = width
        st.session_state.wait_sec = wait_sec
        st.rerun()

# ── URL 순차 처리 (running 상태일 때) ────────────────────────
if st.session_state.running:
    urls     = st.session_state.get("urls_to_process", [])
    done     = list(st.session_state.results.keys())
    pending  = [u for u in urls if u not in done]

    import capture_core
    capture_core.WIDTH    = st.session_state.get("width", 1000)
    capture_core.WAIT_SEC = st.session_state.get("wait_sec", 3)

    if pending:
        url = pending[0]
        idx = urls.index(url) + 1
        st.markdown(
            f'<div class="result-header">🔄 [{idx}/{len(urls)}] 캡처 중... {url[:70]}</div>',
            unsafe_allow_html=True,
        )
        log_box  = st.empty()
        logs     = []

        def log(msg):
            logs.append(msg)
            log_box.markdown(
                '<div class="log-box">' + "\n".join(logs[-25:]) + '</div>',
                unsafe_allow_html=True,
            )

        with st.spinner(f"캡처 중 ({idx}/{len(urls)})..."):
            result = run_capture(url, log=log)

        # 결과 저장 후 rerun → 다음 URL 처리 or 완료
        st.session_state.results[url] = result
        if len(st.session_state.results) >= len(urls):
            st.session_state.running = False
        st.rerun()
    else:
        st.session_state.running = False

# ── 결과 표시 (session_state에서 읽기) ───────────────────────
if st.session_state.results:
    urls = st.session_state.get("urls_to_process", list(st.session_state.results.keys()))

    for idx, url in enumerate(urls, 1):
        if url not in st.session_state.results:
            continue

        result       = st.session_state.results[url]
        product_name = result.get("product_name", "")
        detail_png   = result.get("detail_png")
        images       = result.get("images", [])
        error        = result.get("error")

        st.markdown(
            f'<div class="result-header">✅ [{idx}] {product_name or url[:60]}</div>',
            unsafe_allow_html=True,
        )

        if error:
            st.error(f"❌ 캡처 실패: {error}")
            continue

        st.success(f"대표이미지 {len(images)}장 · 상품상세 캡처 완료")

        # 상품상세 미리보기
        if detail_png:
            with st.expander("🖼️ 상품상세 미리보기", expanded=(idx == 1)):
                st.image(detail_png, use_column_width=True)

        # 대표이미지 선택 + 미리보기
        sel_key   = f"sel_{idx}_{url[-20:]}"
        force_key = f"force_{idx}_{url[-20:]}"

        # 초기화
        if sel_key not in st.session_state:
            st.session_state[sel_key] = {i: False for i in range(len(images))}

        # 전체 선택/해제 버튼 — force 플래그로 처리 (rerun 불필요)
        if st.session_state.get(force_key) == "all":
            for i in range(len(images)):
                st.session_state[sel_key][i] = True
            del st.session_state[force_key]
        elif st.session_state.get(force_key) == "none":
            for i in range(len(images)):
                st.session_state[sel_key][i] = False
            del st.session_state[force_key]

        if images:
            with st.expander(f"📷 대표이미지 선택 ({len(images)}장)", expanded=True):
                bc1, bc2, _ = st.columns([1, 1, 4])
                with bc1:
                    if st.button("전체 선택", key=f"all_{idx}_{url[-20:]}", use_container_width=True):
                        st.session_state[force_key] = "all"
                        st.rerun()
                with bc2:
                    if st.button("전체 해제", key=f"none_{idx}_{url[-20:]}", use_container_width=True):
                        st.session_state[force_key] = "none"
                        st.rerun()

                st.markdown("---")
                cols = st.columns(min(len(images), 4))
                for i, img in enumerate(images):
                    with cols[i % 4]:
                        st.image(img["data"], use_column_width=True)
                        st.session_state[sel_key][i] = st.checkbox(
                            img["filename"],
                            value=st.session_state[sel_key].get(i, False),
                            key=f"chk_{idx}_{url[-20:]}_{i}",
                        )

        # 선택된 이미지만 ZIP
        sel_images = [img for i, img in enumerate(images) if st.session_state.get(sel_key, {}).get(i, False)] if images else []
        zip_data = make_zip(product_name, detail_png, sel_images)
        st.download_button(
            label=f"📦 {product_name}.zip — 상품상세 + 대표이미지 {len(sel_images)}장 ({len(zip_data)//1024} KB)",
            data=zip_data,
            file_name=f"{product_name}.zip",
            mime="application/zip",
            key=f"dl_{idx}_{url[-20:]}",
            use_container_width=True,
        )
        st.divider()

    # 전체 합치기 ZIP
    success = [r for r in st.session_state.results.values() if not r.get("error") and r.get("detail_png")]
    if len(success) >= 2:
        st.subheader("📦 전체 ZIP (모든 상품 합치기)")
        all_buf = io.BytesIO()
        with zipfile.ZipFile(all_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in success:
                pname = r["product_name"]
                if r["detail_png"]:
                    zf.writestr(f"{pname}/{pname}_상품상세.png", r["detail_png"])
                for img in r["images"]:
                    zf.writestr(f"{pname}/대표이미지/{img['filename']}", img["data"])
        all_zip = all_buf.getvalue()
        st.download_button(
            label=f"⬇️ 전체 합치기 ZIP ({len(all_zip)//1024} KB)",
            data=all_zip,
            file_name="samsung_상품_전체.zip",
            mime="application/zip",
            type="primary",
            key="dl_all",
            use_container_width=True,
        )
