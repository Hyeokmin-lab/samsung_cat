"""
VS Code 테스트용 Samsung 상품 페이지 캡처 스크립트
====================================================
필요 패키지:
    pip install playwright
    python -m playwright install chromium

실행: VS Code에서 F5 또는 ▶ 버튼
결과 이미지는 이 파일과 같은 폴더에 저장됩니다
"""

import time
import os
from playwright.sync_api import sync_playwright
try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False
    print("⚠️  Pillow 미설치. 설치 명령: pip install pillow")

# =============================================
# ★ 실행 시 URL을 입력하거나 아래에 직접 입력하세요
# =============================================
# URL을 직접 지정하려면 아래 주석을 해제하고 입력:
# URL = "https://www.samsung.com/sec/..."
URL = None   # None 이면 실행 시 입력 받음

# heightWrap     → 상품 특장점
# faqWrap        → FAQ 영역만
# faqFull        → feature-benefit + textbox-simple + FAQ 전체 합체 캡처
# itmNotice      → 구매 유의사항 (div.itm-notice)
# specAll        → 스펙 전체 펼침 (#compGoodsSpec, 탭 클릭 후 펼쳐서 캡처)
# featureBenefit → 특징/혜택 영역 (wrap-component.feature-benefit)
# textboxSimple  → 텍스트박스 영역 (wrap-component.textbox-simple)
# downloadImages → 대표이미지 원본 전체 다운로드
# all            → 대표이미지 다운로드 + faqFull 캡처 동시 실행
MODE     = "all"

WIDTH    = 1000
WAIT_SEC = 5
# =============================================

SELECTORS = {
    "heightWrap":    ".heightWrap",
    "faqWrap":       "section.faqWrap",
    "faqFull":       "MULTI",
    "itmNotice":     "div.itm-notice",
    "specAll":       "#compGoodsSpec",
    "featureBenefit":"div.wrap-component.feature-benefit",
    "textboxSimple": "div.wrap-component.textbox-simple",
    "downloadImages":"DOWNLOAD",
    "all":           "ALL",        # 대표이미지 다운로드 + faqFull 캡처 동시
}

# faqFull 모드에서 합칠 셀렉터 목록 (페이지 등장 순서대로)
FAQ_FULL_SELECTORS = [
    "div.wrap-component.feature-benefit",
    "div.wrap-component.textbox-simple",
    "section.faqWrap",
    "div.itm-notice",
    "#compGoodsSpec",
]

# ── FAQ 펼치기 ─────────────────────────────────────────────────
# 삼성 FAQ 구조 (캡처된 JS 코드 기반):
#   .faqTitle 클릭 → .faqTitle._actv + next().slideDown(300)
#   즉, .faqTitle 의 바로 다음 형제 요소가 답변 영역
#   jQuery slideDown = display:block + height 애니메이션
JS_EXPAND_FAQ = """
() => {
    const section = document.querySelector('section.faqWrap');
    if (!section) return { ok: false, msg: 'section not found' };

    const SKIP_TAGS = new Set(['SCRIPT','STYLE','NOSCRIPT','META','LINK','HEAD']);
    let opened = 0;

    // ① 떠있는 UI 요소 숨기기 (상담 버튼, 채팅 위젯 등)
    const floatSelectors = [
        '.btn-chat', '.chat-btn', '.chat-wrap', '.floating',
        '.live-chat', '.cs-btn', '[class*="chat"]', '[class*="float"]',
        '.layer-counsel', '.counsel-btn', '.sticky',
        '[id*="chat"]', '[class*="counsel"]',
    ];
    floatSelectors.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
            if (!SKIP_TAGS.has(el.tagName)) el.style.display = 'none';
        });
    });

    // ② .faqTitle 다음 형제(답변)를 직접 펼침
    //    삼성 구조: button.faqTitle + div(답변) — slideDown 방식
    section.querySelectorAll('.faqTitle').forEach(title => {
        // _actv 클래스 부여 (열림 상태)
        title.classList.add('_actv');
        title.setAttribute('aria-expanded', 'true');

        // 다음 형제 요소가 답변
        const answer = title.nextElementSibling;
        if (answer && !SKIP_TAGS.has(answer.tagName)) {
            answer.style.display    = 'block';
            answer.style.height     = 'auto';
            answer.style.maxHeight  = 'none';
            answer.style.overflow   = 'visible';
            answer.style.visibility = 'visible';
            answer.style.opacity    = '1';
            opened++;
        }
    });

    // ③ faqTitle이 없는 경우 대비 — li 구조도 시도
    if (opened === 0) {
        section.querySelectorAll('li').forEach(li => {
            li.classList.add('on', 'active', 'open');
            // dt 다음 dd
            li.querySelectorAll('dt').forEach(dt => {
                const dd = dt.nextElementSibling;
                if (dd && dd.tagName === 'DD') {
                    dd.style.display   = 'block';
                    dd.style.height    = 'auto';
                    dd.style.maxHeight = 'none';
                    dd.style.overflow  = 'visible';
                    opened++;
                }
            });
            // 첫 번째 자식 다음 형제 (제목+답변 패턴)
            const children = [...li.children].filter(c => !SKIP_TAGS.has(c.tagName));
            if (children.length >= 2) {
                for (let i = 1; i < children.length; i++) {
                    children[i].style.display   = 'block';
                    children[i].style.height    = 'auto';
                    children[i].style.maxHeight = 'none';
                    children[i].style.overflow  = 'visible';
                    opened++;
                }
            }
        });
    }

    // ④ 중복 제목(h2) 제거
    const seen = new Set();
    section.querySelectorAll('h2, h3').forEach(h => {
        const txt = h.textContent.trim();
        if (seen.has(txt)) h.style.display = 'none';
        else seen.add(txt);
    });

    return {
        ok: true,
        faqTitle_count: section.querySelectorAll('.faqTitle').length,
        opened,
    };
}
"""

# ── 스펙 탭 클릭 ──────────────────────────────────────────────
JS_CLICK_SPEC_TAB = """
() => {
    // 방법1: 텍스트 "스펙" 탭 찾아 클릭
    const allEls = [...document.querySelectorAll('a, button, li')];
    const tab = allEls.find(el => {
        const t = el.textContent.trim();
        return t === '스펙' || t === 'Spec' || t === 'Specs';
    });
    if (tab) { tab.click(); return '텍스트 클릭: ' + tab.textContent.trim(); }

    // 방법2: #compGoodsSpec 앞 탭 메뉴에서 찾기
    const specSection = document.querySelector('#compGoodsSpec');
    if (specSection) {
        // 탭 메뉴 anchor 중 href가 #compGoodsSpec 인 것
        const anchor = document.querySelector('a[href="#compGoodsSpec"]');
        if (anchor) { anchor.click(); return 'anchor 클릭'; }
    }
    return null;
}
"""

# ── 스펙 펼치기 ────────────────────────────────────────────────
# #compGoodsSpec 내부:
#   - drop-component 클래스: 접힌 상태
#   - .drop-btn 또는 내부 버튼 클릭으로 펼침
#   - 펼쳐도 안 열리면 CSS 강제 적용
JS_EXPAND_SPEC = """
() => {
    // 스펙 내용은 AJAX로 동적 로드됨
    // → CSS 조작 대신 실제 .dropButton#specDropBtn 클릭해서 JS/AJAX 트리거
    const btn = document.querySelector('#specDropBtn')
             || document.querySelector('.dropButton');
    if (!btn) return { ok: false, msg: 'dropButton not found' };

    // 이미 열려있지 않으면 클릭
    if (!btn.classList.contains('open')) {
        btn.click();
        return { ok: true, action: 'clicked', hasOpen: false };
    }
    return { ok: true, action: 'already open', hasOpen: true };
}
"""

JS_SPEC_AFTER_AJAX = """
() => {
    // AJAX 완료 후 호출 — 팝업/불필요 영역 숨기고 콘텐츠 확인
    const SKIP_TAGS = new Set(['SCRIPT','STYLE','NOSCRIPT','META','LINK']);
    const section = document.querySelector('#compGoodsSpec');
    if (!section) return { ok: false };

    // specLayer 팝업 숨김
    const specLayer = section.querySelector('#specLayer, [name="specLayer"]');
    if (specLayer) specLayer.style.display = 'none';

    // spec-link-box 숨김
    const linkBox = section.querySelector('.spec-link-box');
    if (linkBox) linkBox.style.display = 'none';

    // 콘텐츠 상태 확인
    const specTable = section.querySelector('.spec-table');
    const specContents = section.querySelector('#specContents');
    const tableHTML = specTable ? specTable.innerHTML.trim().length : 0;

    return {
        ok: true,
        specTable:    !!specTable,
        tableHTMLLen: tableHTML,
        specContents: !!specContents,
        sectionH:     section.scrollHeight,
        contentsH:    specContents ? specContents.scrollHeight : 0,
    };
}
"""


def get_target(page, selector):
    info = page.evaluate(f"""
        () => {{
            const els = document.querySelectorAll('{selector}');
            return Array.from(els).map((el, i) => {{
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                return {{
                    index:  i,
                    width:  Math.round(r.width),
                    height: Math.round(r.height),
                    top:    Math.round(r.top + window.scrollY),
                    left:   Math.round(r.left),
                    display: s.display,
                    vis:    s.visibility,
                }};
            }});
        }}
    """)
    print(f"      발견 {len(info)}개:")
    for el in info:
        print(f"        [{el['index']}] {el['width']}x{el['height']}px  "
              f"top={el['top']}  display={el['display']}  vis={el['vis']}")
    return next((e for e in info if e["width"] > 0 and e["height"] > 0), None)


def get_combined_target(page, selectors):
    """여러 셀렉터의 bounding box를 하나로 합쳐 반환
    #compGoodsSpec 은 dropcontent 때문에 scrollHeight 로 실제 높이 측정"""
    print(f"      합체 대상 {len(selectors)}개 영역 측정...")
    boxes = []
    for sel in selectors:
        info = page.evaluate(f"""
            () => {{
                const els = document.querySelectorAll('{sel}');
                return Array.from(els).map(el => {{
                    const r   = el.getBoundingClientRect();
                    const top = Math.round(r.top + window.scrollY);

                    // 실제 콘텐츠 높이: scrollHeight 우선
                    let height = Math.max(
                        Math.round(r.height),
                        el.scrollHeight || 0
                    );

                    return {{
                        width:  Math.round(r.width),
                        height: height,
                        top:    top,
                        left:   Math.round(r.left),
                    }};
                }});
            }}
        """)
        valid = [e for e in info if e["width"] > 0 and e["height"] > 0]
        if valid:
            boxes.append(valid[0])
            print(f"        {sel}: {valid[0]['width']}x{valid[0]['height']}px  top={valid[0]['top']}")
        else:
            print(f"        {sel}: 미발견")

    if not boxes:
        return None

    min_left   = min(b["left"] for b in boxes)
    min_top    = min(b["top"]  for b in boxes)
    max_right  = max(b["left"] + b["width"]  for b in boxes)
    max_bottom = max(b["top"]  + b["height"] for b in boxes)

    result = {
        "left":   min_left,
        "top":    min_top,
        "width":  max_right  - min_left,
        "height": max_bottom - min_top,
    }
    print(f"      합체 영역: {result['width']}x{result['height']}px  top={result['top']}")
    return result


def download_images(url: str):
    """대표 이미지 원본을 modal-gallery 에서 추출해 images/ 폴더에 저장"""
    import urllib.request

    save_dir = "images"
    os.makedirs(save_dir, exist_ok=True)

    SEP = '='*58
    print(f"\n{SEP}")
    print(f"  대표이미지 다운로드 모드")
    print(f"  URL  : {url[:65]}")
    print(f"  저장 : ./{save_dir}/")
    print(SEP)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": WIDTH, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        try:
            print("[1/3] 페이지 로딩...")
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(WAIT_SEC)

            # ① 대표 이미지 클릭해서 모달 열기
            print("[2/3] 모달 열기...")
            opened = page.evaluate("""
                () => {
                    // 대표 이미지 클릭 트리거 패턴
                    const triggers = [
                        '.product-image img',
                        '.main-image img',
                        '.pdp-image img',
                        '.image-gallery img',
                        '.swiper-slide-active img',
                        '.img-wrap img',
                        '#mainImage img',
                        '.gallery-image img',
                    ];
                    for (const sel of triggers) {
                        const el = document.querySelector(sel);
                        if (el) { el.click(); return sel; }
                    }
                    return null;
                }
            """)
            print(f"      클릭: {opened}")
            time.sleep(2.0)   # 모달 열림 대기

            # 모달이 안 열렸으면 버튼 패턴 시도
            if not opened:
                page.evaluate("""
                    () => {
                        const btns = [...document.querySelectorAll('button, a')];
                        const btn = btns.find(el =>
                            el.className.includes('gallery') ||
                            el.className.includes('image') ||
                            el.className.includes('zoom')
                        );
                        if (btn) btn.click();
                    }
                """)
                time.sleep(2.0)

            # ② .modal-gallery-item img src 전체 수집
            print("[3/3] 이미지 URL 수집 및 다운로드...")
            imgs = page.evaluate("""
                () => {
                    // 모달 갤러리 이미지
                    const modal = document.querySelectorAll(
                        '.modal-gallery-item img, .modal-gallery-content img'
                    );
                    if (modal.length > 0) {
                        return Array.from(modal).map((img, i) => ({
                            src: img.src || img.getAttribute('src'),
                            alt: img.alt || '',
                            seq: img.dataset.seq || i + 1,
                        }));
                    }
                    // 모달이 없으면 메인 이미지 영역에서 수집
                    const main = document.querySelectorAll(
                        '.swiper-slide img[data-img-tp], ' +
                        '.gallery-list img, ' +
                        '.product-gallery img'
                    );
                    return Array.from(main).map((img, i) => ({
                        src: img.src || img.getAttribute('src'),
                        alt: img.alt || '',
                        seq: img.dataset.seq || i + 1,
                    }));
                }
            """)

        finally:
            browser.close()

    if not imgs:
        print("  ⚠️  이미지를 찾지 못했습니다.")
        return

    # 중복 제거
    seen = set()
    unique_imgs = []
    for img in imgs:
        src = img["src"]
        if src and src not in seen:
            seen.add(src)
            unique_imgs.append(img)

    print(f"  발견된 이미지: {len(unique_imgs)}개\n")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": url,
    }

    saved = []
    for i, img in enumerate(unique_imgs, 1):
        src = img["src"]
        if not src:
            continue

        # //images.samsung.com → https://images.samsung.com
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = "https://www.samsung.com" + src

        # 파일명: seq_alt축약.png
        alt_short = img["alt"][:20].replace(" ", "_").replace("/", "_") if img["alt"] else "img"
        fname = f"{i:02d}_{alt_short}.png"
        fpath = os.path.join(save_dir, fname)

        try:
            req = urllib.request.Request(src, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            with open(fpath, "wb") as f:
                f.write(data)
            kb = len(data) // 1024
            print(f"  [{i:02d}] ✅ {fname}  ({kb} KB)")
            print(f"        {src}")
            saved.append(fpath)
        except Exception as e:
            print(f"  [{i:02d}] ❌ 실패: {src}")
            print(f"        오류: {e}")

    SEP2 = '='*58
    print(f"\n{SEP2}")
    print(f"  완료: {len(saved)}/{len(unique_imgs)}개 저장 → ./{save_dir}/")
    print(f"{SEP2}\n")


def get_product_name(page) -> str:
    """페이지에서 상품명 추출
    우선순위:
      1. #compGoodRevampFeaturesName h2.prod-name (삼성 뉴닷컴 PDP)
      2. h2.prod-name
      3. h1.prod-title
      4. og:title 메타태그
      5. document.title
    """
    name = page.evaluate("""
        () => {
            const selectors = [
                '#compGoodRevampFeaturesName h2.prod-name',
                '#compGoodRevampFeaturesName h2',
                'h2.prod-name',
                '.prod-name',
                'h1.prod-title',
                '.product-name h1',
                '.pd-head h1',
                '.pdp-title h1',
                'h1.title',
                '.itm-info-detail h1',
                '.goods-name',
                'h1',
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.textContent.trim()) {
                    return el.textContent.trim();
                }
            }
            const og = document.querySelector('meta[property="og:title"]');
            if (og) return og.content.split('|')[0].trim();
            return document.title.split('|')[0].trim();
        }
    """)
    import re
    name = re.sub(r'[\/:*?"<>|]', '_', name).strip()
    return name or "상품"


def run_all(url: str):
    """대표이미지 다운로드 + faqFull 캡처 동시 실행"""
    import urllib.request
    from PIL import Image as PILImage

    print(f"\n{'='*58}")
    print(f"  ALL 모드: 대표이미지 다운로드 + 상품상세 캡처")
    print(f"  URL  : {url[:65]}")
    print(f"{'='*58}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": WIDTH, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        try:
            # ① 페이지 로드
            print("[1/6] 페이지 로딩...")
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(WAIT_SEC)

            # ② 상품명 추출
            product_name = get_product_name(page)
            print(f"      상품명: {product_name}")

            save_dir    = product_name
            capture_out = f"{product_name}_상품상세.png"
            os.makedirs(save_dir, exist_ok=True)

            # ③ 대표이미지 수집 — 모달 열지 않고 DOM에서 직접 추출
            print("[2/6] 대표이미지 URL 추출 중 (모달 미사용)...")
            imgs = page.evaluate("""
                () => {
                    // 우선순위1: modal-gallery-item (이미 DOM에 존재)
                    const modalImgs = document.querySelectorAll(
                        '.modal-gallery-item img, .modal-gallery-list img'
                    );
                    if (modalImgs.length > 0) {
                        return Array.from(modalImgs).map((img, i) => ({
                            src: img.getAttribute('src') || img.src,
                            alt: img.alt || '',
                            seq: img.dataset.seq || String(i + 1),
                        }));
                    }

                    // 우선순위2: 썸네일 리스트 img (data-img-tp 속성)
                    const thumbImgs = document.querySelectorAll(
                        'img[data-img-tp], .gallery-list img, .thumb-list img'
                    );
                    if (thumbImgs.length > 0) {
                        return Array.from(thumbImgs).map((img, i) => {
                            // 썸네일 URL → 원본 URL 변환
                            // 삼성: ?$128_128_PNG$ 또는 ?$Q90_776_776_F_JPG$ 제거
                            let src = img.getAttribute('src') || img.src;
                            src = src.split('?')[0];  // 쿼리스트링 제거
                            return {
                                src: src,
                                alt: img.alt || '',
                                seq: img.dataset.seq || String(i + 1),
                            };
                        });
                    }

                    return [];
                }
            """)
            print(f"      추출된 이미지: {len(imgs)}개")

            # ④ 상세 캡처 (faqFull)
            print("[3/6] 스크롤 중...")
            page.evaluate("""
                () => new Promise(resolve => {
                    const dist = 400; let pos = 0;
                    const id = setInterval(() => {
                        window.scrollBy(0, dist); pos += dist;
                        if (pos >= document.body.scrollHeight) {
                            clearInterval(id); window.scrollTo(0, 0); resolve();
                        }
                    }, 100);
                })
            """)
            time.sleep(2.0)

            print("[4/6] 영역 펼치기 (FAQ + 스펙)...")
            result = page.evaluate(JS_EXPAND_FAQ)
            print(f"      FAQ: {result}")
            time.sleep(1.0)

            tab = page.evaluate(JS_CLICK_SPEC_TAB)
            print(f"      스펙 탭: {tab}")
            time.sleep(2.0)
            result = page.evaluate(JS_EXPAND_SPEC)
            print(f"      스펙 클릭: {result}")
            for i in range(10):
                time.sleep(1.0)
                check = page.evaluate(JS_SPEC_AFTER_AJAX)
                print(f"      AJAX 대기 {i+1}초: tableHTMLLen={check.get('tableHTMLLen',0)}")
                if check.get('tableHTMLLen', 0) > 100:
                    print(f"      AJAX 완료!")
                    break
            time.sleep(1.0)
            page.evaluate("() => window.scrollTo(0, 0)")
            time.sleep(0.5)

            print("[5/6] 상세 캡처 중...")
            target = get_combined_target(page, FAQ_FULL_SELECTORS)

            if target and target["height"] > 0:
                full_h = page.evaluate("document.body.scrollHeight")
                page.set_viewport_size({"width": WIDTH, "height": full_h})
                time.sleep(0.8)
                tmp = "__tmp_full.png"
                page.screenshot(path=tmp, full_page=True)
                iw, ih = PILImage.open(tmp).size
                x1 = max(0, target["left"])
                y1 = max(0, target["top"])
                x2 = min(iw, target["left"] + target["width"])
                y2 = min(ih, target["top"]  + target["height"])
                cropped = PILImage.open(tmp).crop((x1, y1, x2, y2))
                # JPG로 저장
                cropped.save(capture_out, "PNG")
                os.remove(tmp)
                print(f"      저장: {capture_out}  ({x2-x1}x{y2-y1}px)")
            else:
                print("      ⚠️  캡처 영역 미발견")

        finally:
            browser.close()

    # ⑤ 대표이미지 다운로드
    print(f"[6/6] 대표이미지 다운로드 ({len(imgs) if imgs else 0}개)...")
    if not imgs:
        print("  ⚠️  이미지 미발견")
    else:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": url,
        }
        seen = set()
        idx  = 1
        for img in imgs:
            src = img["src"]
            if not src or src in seen:
                continue
            seen.add(src)
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = "https://www.samsung.com" + src
            alt_short = img["alt"][:15].replace(" ", "_").replace("/", "_")
            fname = os.path.join(save_dir, f"{idx:02d}_{alt_short}.png")
            try:
                req = urllib.request.Request(src, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                with open(fname, "wb") as f:
                    f.write(data)
                print(f"  [{idx:02d}] ✅ {fname}  ({len(data)//1024} KB)")
                idx += 1
            except Exception as e:
                print(f"  [{idx:02d}] ❌ {src} — {e}")
                idx += 1

    SEP = '='*58
    print(f"\n{SEP}")
    print(f"  ✅ 완료!")
    print(f"  대표이미지 → ./{save_dir}/")
    print(f"  상세 캡처  → {capture_out}")
    print(f"{SEP}\n")


def capture():
    if MODE not in SELECTORS:
        print(f"❌ MODE 오류. {list(SELECTORS.keys())} 중 선택하세요.")
        return

    # 이미지 다운로드 전용 모드
    if MODE == "downloadImages":
        download_images(URL)
        return

    # all 모드: 상품명 추출 → 이미지 다운 + faqFull 캡처 동시
    if MODE == "all":
        run_all(URL)
        return

    selector = SELECTORS[MODE]
    output   = f"capture_{MODE}.png"

    print(f"\n{'='*58}")
    print(f"  URL  : {URL[:65]}")
    print(f"  모드 : {MODE}  ({selector})")
    print(f"  너비 : {WIDTH}px  |  대기 : {WAIT_SEC}초")
    print(f"  저장 : {output}")
    print(f"{'='*58}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": WIDTH, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        try:
            # ① 페이지 로드
            print("[1/5] 페이지 로딩...")
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            print(f"      완료. {WAIT_SEC}초 대기...")
            time.sleep(WAIT_SEC)

            # ② 전체 스크롤 (lazy-load 트리거)
            print("[2/5] 스크롤 중...")
            page.evaluate("""
                () => new Promise(resolve => {
                    const dist = 400; let pos = 0;
                    const id = setInterval(() => {
                        window.scrollBy(0, dist); pos += dist;
                        if (pos >= document.body.scrollHeight) {
                            clearInterval(id); window.scrollTo(0, 0); resolve();
                        }
                    }, 100);
                })
            """)
            time.sleep(2.0)

            # ③ 모드별 펼치기
            print(f"[3/5] 영역 펼치기 ({MODE})...")

            if MODE in ("faqWrap", "faqFull"):
                result = page.evaluate(JS_EXPAND_FAQ)
                print(f"      FAQ 결과: {result}")
                time.sleep(1.0)

            if MODE == "faqFull":
                # 스펙 dropButton 클릭 → AJAX 완료 대기
                tab = page.evaluate(JS_CLICK_SPEC_TAB)
                print(f"      스펙 탭 클릭: {tab}")
                time.sleep(2.0)
                result = page.evaluate(JS_EXPAND_SPEC)
                print(f"      dropButton 클릭: {result}")
                for i in range(10):
                    time.sleep(1.0)
                    check = page.evaluate(JS_SPEC_AFTER_AJAX)
                    print(f"      AJAX 대기 {i+1}초: tableHTMLLen={check.get('tableHTMLLen',0)}")
                    if check.get('tableHTMLLen', 0) > 100:
                        print(f"      AJAX 완료! sectionH={check.get('sectionH')}")
                        break
                time.sleep(1.0)
                page.evaluate("() => window.scrollTo(0, 0)")
                time.sleep(0.5)

            elif MODE == "specAll":
                tab = page.evaluate(JS_CLICK_SPEC_TAB)
                print(f"      탭 클릭: {tab}")
                time.sleep(2.0)
                result = page.evaluate(JS_EXPAND_SPEC)
                print(f"      dropButton 클릭: {result}")
                for i in range(10):
                    time.sleep(1.0)
                    check = page.evaluate(JS_SPEC_AFTER_AJAX)
                    print(f"      AJAX 대기 {i+1}초: tableHTMLLen={check.get('tableHTMLLen',0)}")
                    if check.get('tableHTMLLen', 0) > 100:
                        print(f"      AJAX 완료! sectionH={check.get('sectionH')}")
                        break
                time.sleep(1.0)

            else:
                print("      (펼치기 없음)")

            # ④ 요소 좌표 측정
            print(f"[4/5] 요소 탐색: {selector}")
            if MODE == "faqFull":
                target = get_combined_target(page, FAQ_FULL_SELECTORS)
            else:
                target = get_target(page, selector)

            if not target:
                print("      ⚠️  대안 셀렉터 탐색...")
                for fb in [".pdp-content", ".product-detail", ".cont-wrap", "#container", "main"]:
                    alt = page.evaluate(f"""
                        () => {{
                            const el = document.querySelector('{fb}');
                            if (!el) return null;
                            const r = el.getBoundingClientRect();
                            return {{
                                width:  Math.round(r.width),
                                height: Math.round(r.height),
                                top:    Math.round(r.top + window.scrollY),
                                left:   Math.round(r.left),
                            }};
                        }}
                    """)
                    if alt and alt["height"] > 0:
                        print(f"      대안 사용: {fb}  ({alt['width']}x{alt['height']}px)")
                        target = alt
                        break

            # ⑤ 캡처 — 풀페이지 찍고 PIL 크롭
            print("[5/5] 캡처 중...")
            if target and target["height"] > 0:
                # 풀페이지 높이로 뷰포트 확장
                full_h = page.evaluate("document.body.scrollHeight")
                page.set_viewport_size({"width": WIDTH, "height": full_h})
                time.sleep(0.8)  # 뷰포트 확장 후 재렌더링 대기

                # 풀페이지 스크린샷 → temp 파일
                tmp = output.replace(".png", "_tmp_full.png")
                page.screenshot(path=tmp, full_page=True)

                # PIL로 대상 영역 크롭
                try:
                    from PIL import Image
                    img = Image.open(tmp)
                    iw, ih = img.size
                    print(f"      풀페이지 크기: {iw}x{ih}px")

                    x1 = max(0, target["left"])
                    y1 = max(0, target["top"])
                    x2 = min(iw, target["left"] + target["width"])
                    y2 = min(ih, target["top"]  + target["height"])
                    print(f"      크롭 영역: ({x1},{y1}) → ({x2},{y2})")

                    cropped = img.crop((x1, y1, x2, y2))
                    cropped.save(output)
                    os.remove(tmp)
                    print(f"      크롭 완료: {x2-x1}x{y2-y1}px")
                except ImportError:
                    print("      ⚠️  PIL 없음 → clip 방식 사용")
                    os.rename(tmp, output)
            else:
                print("      ⚠️  전체 페이지 캡처로 대체")
                page.screenshot(path=output, full_page=True)

        finally:
            browser.close()

    size_kb = os.path.getsize(output) // 1024
    print(f"\n{'='*58}")
    print(f"  ✅ 완료: {output}  ({size_kb} KB)")
    print(f"{'='*58}\n")


if __name__ == "__main__":
    # URL 입력 처리
    if URL is None:
        print("=" * 58)
        print("  Samsung 상품 캡처 도구")
        print("=" * 58)
        while True:
            raw = input("\n  상품 URL을 입력하세요: ").strip()
            if raw.startswith("http"):
                URL = raw
                break
            print("  ❌ http:// 또는 https:// 로 시작하는 URL을 입력해주세요.")

    print(f"\n  MODE : {MODE}")
    print(f"  URL  : {URL[:70]}")
    print(f"  WIDTH: {WIDTH}px\n")

    if MODE == "all":
        run_all(URL)
    else:
        capture()
