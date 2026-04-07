import io
import zipfile
import streamlit as st
from capture_core import run_capture, run_capture_multi, make_zip, _to_jpg

st.set_page_config(page_title="Samsung 상품 캡처", page_icon="📸", layout="centered")

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

# ── session_state 초기화 ──────────────────────────────────────
if "results" not in st.session_state: st.session_state.results = {}
if "running" not in st.session_state: st.session_state.running = False

# ── 헤더 + 초기화 버튼 ───────────────────────────────────────
col_title, col_reset = st.columns([5, 1])
with col_title:
    st.title("📸 Samsung 상품 캡처")
    st.caption("URL을 최대 3개까지 입력하면 대표이미지 + 상품상세를 자동으로 캡처합니다.")
with col_reset:
    st.write(""); st.write("")
    if st.session_state.get("results") and st.button("🔄 초기화", use_container_width=True):
        # session_state 전체 초기화 (URL 입력값 포함)
        st.session_state.clear()
        st.rerun()
st.divider()

# ── 입력 폼 ──────────────────────────────────────────────────
with st.form("capture_form"):
    url1 = st.text_input("상품 URL 1", placeholder="https://www.samsung.com/sec/...", key="input_url1")
    url2 = st.text_input("상품 URL 2 (선택)", placeholder="https://www.samsung.com/sec/...", key="input_url2")
    url3 = st.text_input("상품 URL 3 (선택)", placeholder="https://www.samsung.com/sec/...", key="input_url3")
    col1, col2 = st.columns(2)
    with col1:
        width = st.selectbox("캡처 너비", [768, 1000, 1280], index=0,
                             format_func=lambda x: f"{x}px")
    with col2:
        wait_sec = st.selectbox("페이지 대기 시간", [3, 4, 5, 6, 8, 10], index=0,
                                format_func=lambda x: f"{x}초")
    multi_spec = st.checkbox("스펙 탭별 개별 캡처 (탭이 여러 개인 상품에 사용)", value=False)
    submitted = st.form_submit_button("🚀 캡처 시작", type="primary", use_container_width=True)

# ── 캡처 시작 ─────────────────────────────────────────────────
if submitted and not st.session_state.running:
    urls    = [u.strip() for u in [url1, url2, url3] if u.strip().startswith("http")]
    invalid = [u.strip() for u in [url1, url2, url3] if u.strip() and not u.strip().startswith("http")]
    if invalid:
        st.warning(f"⚠️  올바르지 않은 URL 제외: {', '.join(invalid)}")
    if not urls:
        st.error("유효한 URL을 1개 이상 입력해주세요.")
    else:
        st.session_state.results         = {}
        st.session_state.running         = True
        st.session_state.urls_to_process = urls
        st.session_state.width           = width
        st.session_state.wait_sec        = wait_sec
        st.session_state.multi_spec      = multi_spec
        st.rerun()

# ── 전체 URL 일괄 처리 (Chrome 1회 시작) ────────────────────
if st.session_state.running:
    import capture_core
    capture_core.WIDTH      = st.session_state.get("width", 768)
    capture_core.WAIT_SEC   = st.session_state.get("wait_sec", 3)
    capture_core.MULTI_SPEC = st.session_state.get("multi_spec", False)

    urls = st.session_state.get("urls_to_process", [])

    st.markdown('<div class="result-header">🔄 캡처 진행 중...</div>',
                unsafe_allow_html=True)
    log_box = st.empty()
    logs    = []

    def log(msg):
        logs.append(msg)
        log_box.markdown('<div class="log-box">' + "\n".join(logs[-30:]) + '</div>',
                         unsafe_allow_html=True)

    with st.spinner(f"전체 {len(urls)}개 URL 캡처 중... (Chrome 1회 시작)"):
        results_list = run_capture_multi(urls, log=log)

    for url, result in zip(urls, results_list):
        st.session_state.results[url] = result

    st.session_state.running = False
    st.rerun()

# ── 결과 표시 (fragment 로 URL별 독립 렌더링) ───────────────
@st.fragment
def show_result(idx, url, result):
    product_name = result.get("product_name", "")
    detail_png   = result.get("detail_png")
    images       = result.get("images", [])
    error        = result.get("error")
    spec_png     = result.get("spec_png")

    st.markdown(f'<div class="result-header">✅ [{idx}] {product_name or url[:60]}</div>',
                unsafe_allow_html=True)

    if error:
        st.error(f"❌ 캡처 실패: {error}")
        return

    st.success(f"대표이미지 {len(images)}장 · 상품상세 캡처 완료")

    # 상품상세 미리보기
    if detail_png:
        with st.expander("🖼️ 상품상세 미리보기", expanded=(idx == 1)):
            st.image(detail_png, use_column_width=True)

    # 스펙 탭 합체 미리보기
    if spec_png:
        with st.expander("📋 스펙 (탭 전체 합체)", expanded=True):
            st.image(spec_png, use_column_width=True)
            st.download_button(
                label=f"⬇️ {product_name}_스펙.jpg 다운로드",
                data=_to_jpg(spec_png),
                file_name=f"{product_name}_스펙.jpg",
                mime="image/jpeg",
                key=f"spec_{idx}_{url[-20:]}",
            )

    def chk_key(i): return f"chk_{idx}_{url[-20:]}_{i}"

    if images:
        init_key = f"init_{idx}_{url[-20:]}"
        if init_key not in st.session_state:
            for i in range(len(images)):
                st.session_state[chk_key(i)] = False
            st.session_state[init_key] = True

        with st.expander(f"📷 대표이미지 선택 ({len(images)}장)", expanded=True):
            bc1, bc2, _ = st.columns([1, 1, 4])
            with bc1:
                if st.button("전체 선택", key=f"all_{idx}_{url[-20:]}", use_container_width=True):
                    for i in range(len(images)):
                        st.session_state[chk_key(i)] = True
            with bc2:
                if st.button("전체 해제", key=f"none_{idx}_{url[-20:]}", use_container_width=True):
                    for i in range(len(images)):
                        st.session_state[chk_key(i)] = False

            st.markdown("---")
            cols = st.columns(min(len(images), 4))
            for i, img in enumerate(images):
                with cols[i % 4]:
                    st.image(img["data"], use_column_width=True)
                    st.checkbox(img["filename"], key=chk_key(i))

    # 선택된 대표이미지
    sel_images = [img for i, img in enumerate(images)
                  if st.session_state.get(chk_key(i), False)]

    # ── 다운로드 버튼 ─────────────────────────────────────────
    # 대표이미지 미선택 + 스펙 없음 → 상품상세 JPG 단독 다운로드
    # 대표이미지 선택 or 스펙 있음  → ZIP 다운로드
    if not sel_images and not spec_png:
        # 상품상세 JPG 단독 다운로드
        detail_jpg = _to_jpg(detail_png) if detail_png else b""
        st.download_button(
            label=f"⬇️ {product_name}_상품상세.jpg 다운로드 ({len(detail_jpg)//1024} KB)",
            data=detail_jpg,
            file_name=f"{product_name}_상품상세.jpg",
            mime="image/jpeg",
            key=f"dl_{idx}_{url[-20:]}",
            use_container_width=True,
        )
    else:
        zip_data = make_zip(product_name, detail_png, sel_images, spec_png)
        st.download_button(
            label=f"📦 {product_name}.zip — 상품상세 + 대표이미지 {len(sel_images)}장 ({len(zip_data)//1024} KB)",
            data=zip_data,
            file_name=f"{product_name}.zip",
            mime="application/zip",
            key=f"dl_{idx}_{url[-20:]}",
            use_container_width=True,
        )
    st.divider()


if st.session_state.results:
    urls = st.session_state.get("urls_to_process", list(st.session_state.results.keys()))

    for idx, url in enumerate(urls, 1):
        if url not in st.session_state.results:
            continue
        show_result(idx, url, st.session_state.results[url])

    # 전체 합치기 ZIP (2개 이상 성공 시)
    success = [r for r in st.session_state.results.values()
               if not r.get("error") and r.get("detail_png")]
    if len(success) >= 2:
        st.subheader("📦 전체 ZIP (모든 상품 합치기)")
        all_buf = io.BytesIO()
        with zipfile.ZipFile(all_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for j, r in enumerate(success):
                pname = r["product_name"]
                r_url = next((u for u, v in st.session_state.results.items() if v is r), "")
                r_idx = list(st.session_state.results.keys()).index(r_url) + 1 if r_url else j + 1
                if r["detail_png"]:
                    zf.writestr(f"{pname}/{pname}_상품상세.jpg", _to_jpg(r["detail_png"]))
                if r.get("spec_png"):
                    zf.writestr(f"{pname}/{pname}_스펙.jpg", _to_jpg(r["spec_png"]))
                for i, img in enumerate(r["images"]):
                    k = f"chk_{r_idx}_{r_url[-20:]}_{i}"
                    if st.session_state.get(k, False):
                        zf.writestr(f"{pname}/{img['filename']}", img["data"])
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
