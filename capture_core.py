"""
Samsung 상품 페이지 캡처 핵심 로직 (selenium)
Chrome 드라이버를 재사용해서 2번째, 3번째 URL도 빠르게 처리
"""

import io
import re
import time
import zipfile
import urllib.request
from PIL import Image as PILImage
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

WIDTH    = 768
WAIT_SEC = 2

FAQ_FULL_SELECTORS = [
    "div.wrap-component.feature-benefit",
    "div.wrap-component.textbox-simple",
    "section.faqWrap",
    "div.itm-notice",
    "#compGoodsSpec",
]

JS_EXPAND_FAQ = """
const sections = document.querySelectorAll('section.faqWrap');
if (!sections.length) return {ok:false, count:0};
const SKIP = new Set(['SCRIPT','STYLE','NOSCRIPT','META','LINK','HEAD']);
let opened = 0;

// 떠있는 UI 요소 숨기기
['[class*="chat"]','[class*="float"]','.layer-counsel','.counsel-btn','.sticky'].forEach(sel => {
    document.querySelectorAll(sel).forEach(el => { if (!SKIP.has(el.tagName)) el.style.display='none'; });
});

// 모든 faqWrap 섹션 처리
sections.forEach(section => {
    section.querySelectorAll('.faqTitle').forEach(t => {
        t.classList.add('_actv');
        t.setAttribute('aria-expanded','true');
        const a = t.nextElementSibling;
        if (a && !SKIP.has(a.tagName)) {
            a.style.cssText='display:block!important;height:auto!important;max-height:none!important;overflow:visible!important;visibility:visible!important;opacity:1!important;';
            opened++;
        }
    });

    // faqTitle이 없으면 li 구조로 시도
    if (section.querySelectorAll('.faqTitle').length === 0) {
        section.querySelectorAll('li').forEach(li => {
            li.classList.add('on','active','open');
            const ch=[...li.children].filter(c=>!SKIP.has(c.tagName));
            if (ch.length>=2) { for(let i=1;i<ch.length;i++){ch[i].style.display='block';ch[i].style.height='auto';ch[i].style.overflow='visible';opened++;} }
        });
    }

    // 중복 제목 제거
    const seen=new Set();
    section.querySelectorAll('h2,h3').forEach(h=>{const t=h.textContent.trim();if(seen.has(t))h.style.display='none';else seen.add(t);});
});

return {ok:true, sections:sections.length, opened:opened};
"""

JS_CLICK_SPEC_TAB = """
const tab=[...document.querySelectorAll('a,button,li')].find(el=>['스펙','Spec','Specs'].includes(el.textContent.trim()));
if(tab){tab.click();return 'clicked';}
const a=document.querySelector('a[href="#compGoodsSpec"]');
if(a){a.click();return 'anchor';}
return null;
"""

JS_EXPAND_SPEC = """
const btn=document.querySelector('#specDropBtn')||document.querySelector('.dropButton');
if(!btn) return {ok:false};
if(!btn.classList.contains('open')){btn.click();return {ok:true,action:'clicked'};}
return {ok:true,action:'already open'};
"""

JS_SPEC_CHECK = """
const s=document.querySelector('#compGoodsSpec');
if(!s) return {ok:false,len:0,tabs:[]};
const sl=s.querySelector('#specLayer,[name="specLayer"]');
if(sl) sl.style.display='none';
const lb=s.querySelector('.spec-link-box');
if(lb) lb.style.display='none';
// 탭 목록 수집 — a[name='spec-tab'] 의 data-disp-nm 기준
const tabEls = s.querySelectorAll("ul.spec-tabcontent-tab li.tab-item a[name='spec-tab']");
const tabs = Array.from(tabEls).map((a, i) => ({
    index: i,
    text:  (a.getAttribute('data-disp-nm') || a.innerText).trim()
}));
// 콘텐츠 길이 — #specTabContent 기준
const content = document.querySelector('#specTabContent');
return {ok:true, len: content ? content.innerHTML.trim().length : 0, tabs: tabs};
"""

JS_CLICK_SPEC_TAB_BY_INDEX = """
(idx) => {
    const tabs = document.querySelectorAll('ul.spec-tabcontent-tab li.tab-item');
    if(idx >= tabs.length) return {ok:false, reason:'idx out of range', total:tabs.length};

    const li = tabs[idx];

    // jQuery trigger (Samsung 페이지 jQuery 이벤트 핸들러 직접 호출)
    if (window.jQuery) {
        window.jQuery(li).trigger('click');
    } else {
        li.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}));
    }

    return {ok:true, clicked: li.textContent.trim()};
}
"""


def sanitize(name: str) -> str:
    return re.sub(r'[\/:*?"<>|]', '_', name).strip()


def make_driver() -> webdriver.Chrome:
    """Chrome 드라이버 생성 — 빠른 시작 옵션 포함"""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={WIDTH},900")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
    # 불필요한 기능 비활성화 → 시작 속도 개선
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-plugins")
    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--disable-sync")
    opts.add_argument("--no-first-run")
    opts.add_argument("--disable-translate")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--mute-audio")

    import shutil
    chrome_bin = (shutil.which("chromium") or shutil.which("chromium-browser")
                  or shutil.which("google-chrome"))
    if chrome_bin:
        opts.binary_location = chrome_bin
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception:
        driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=opts)

    driver.set_page_load_timeout(60)
    return driver


def _capture_one(driver: webdriver.Chrome, url: str, log) -> dict:
    """드라이버를 받아 URL 1개를 캡처 — Chrome 재시작 없음"""
    result = {"product_name": "", "detail_png": None, "spec_png": None, "images": [], "error": None}
    imgs   = []

    try:
        # 1. 페이지 로드
        log("📄 페이지 로딩 중...")
        driver.get(url)
        # 뷰포트 초기화 (이전 URL 에서 크기가 바뀌었을 수 있음)
        driver.set_window_size(WIDTH, 900)
        time.sleep(WAIT_SEC)

        # 2. 상품명 추출
        product_name = driver.execute_script("""
            const sels=['#compGoodRevampFeaturesName h2.prod-name','#compGoodRevampFeaturesName h2',
                        'h2.prod-name','.prod-name','h1.prod-title','h1'];
            for(const s of sels){const el=document.querySelector(s);if(el&&el.textContent.trim())return el.textContent.trim();}
            const og=document.querySelector('meta[property="og:title"]');
            if(og) return og.content.split('|')[0].trim();
            return document.title.split('|')[0].trim();
        """)
        product_name = sanitize(product_name or "상품")
        result["product_name"] = product_name
        log(f"🏷️  상품명: {product_name}")

        # 3. 대표이미지 URL 수집
        log("🖼️  대표이미지 URL 추출 중...")
        imgs = driver.execute_script("""
            const modal=document.querySelectorAll('.modal-gallery-item img,.modal-gallery-list img');
            if(modal.length>0) return Array.from(modal).map((img,i)=>({src:img.getAttribute('src')||img.src,alt:img.alt||'',seq:img.dataset.seq||String(i+1)}));
            const thumb=document.querySelectorAll('img[data-img-tp],.gallery-list img');
            return Array.from(thumb).map((img,i)=>{let src=(img.getAttribute('src')||img.src).split('?')[0];return{src,alt:img.alt||'',seq:img.dataset.seq||String(i+1)};});
        """)
        log(f"   → {len(imgs)}개 발견")

        # 4. 스크롤
        log("🔄 스크롤 중...")
        driver.execute_script("""
            return new Promise(resolve=>{
                const dist=400;let pos=0;
                const id=setInterval(()=>{window.scrollBy(0,dist);pos+=dist;
                if(pos>=document.body.scrollHeight){clearInterval(id);window.scrollTo(0,0);resolve();}},100);
            });
        """)
        time.sleep(0.7)

        # 5. FAQ 펼치기
        log("📖 FAQ 펼치는 중...")
        driver.execute_script(JS_EXPAND_FAQ)
        time.sleep(0.3)

        # 6. 스펙 섹션 로딩
        log("📊 스펙 로딩 중...")
        driver.execute_script(JS_CLICK_SPEC_TAB)
        time.sleep(1.0)
        driver.execute_script(JS_EXPAND_SPEC)

        # 첫 번째 탭 로드 대기
        spec_tabs = []
        for i in range(12):
            time.sleep(0.5)
            check = driver.execute_script(JS_SPEC_CHECK)
            log(f"   로드 대기 {i+1}회 (len={check.get('len',0)})")
            if check.get("len", 0) > 100:
                spec_tabs = check.get("tabs", [])
                log(f"   → 완료! 탭 {len(spec_tabs)}개: {[t['text'] for t in spec_tabs]}")
                break
        time.sleep(0.2)

        # 탭이 2개 이상이면 탭별 캡처
        if len(spec_tabs) >= 2:
            log(f"📋 탭별 스펙 캡처 ({len(spec_tabs)}개 탭)...")
            tab_imgs = []

            # 뷰포트를 페이지 전체 높이로 확장
            full_h = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(WIDTH, full_h)
            time.sleep(0.5)

            for tab in spec_tabs:
                tab_name = tab["text"]
                tab_idx  = tab["index"]
                log(f"   탭 [{tab_idx+1}/{len(spec_tabs)}] {tab_name}")

                # <a> 태그 찾기 (li 안의 a[name='spec-tab'])
                a_els = driver.find_elements(
                    By.CSS_SELECTOR,
                    "#specContents ul.spec-tabcontent-tab li.tab-item a[name='spec-tab']"
                )
                log(f"      a 요소 수: {len(a_els)}")
                if tab_idx >= len(a_els):
                    log(f"      a 요소 없음")
                    continue

                a_el = a_els[tab_idx]
                log(f"      data-disp-nm: {a_el.get_attribute('data-disp-nm')}")

                # 클릭 전 #cstrt-nm 텍스트 저장 (탭 전환 시 이 h3이 바뀜)
                before_nm = driver.execute_script(
                    "const h=document.querySelector('#cstrt-nm');"
                    "return h ? h.innerText.trim() : '';"
                )
                log(f"      클릭 전 #cstrt-nm: {before_nm!r}")

                # <a> 태그 직접 클릭
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center', behavior:'instant'});", a_el
                )
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", a_el)
                log(f"      a 클릭 완료")

                # #cstrt-nm이 tab_name으로 바뀔 때까지 대기 (최대 10초)
                for j in range(15):
                    time.sleep(0.7)
                    after_nm = driver.execute_script(
                        "const h=document.querySelector('#cstrt-nm');"
                        "return h ? h.innerText.trim() : '';"
                    )
                    matched = (tab_name in after_nm) or (after_nm in tab_name)
                    log(f"      대기 {j+1}회 | #cstrt-nm={after_nm!r} matched={matched}")
                    if matched:
                        log(f"      → 전환 확인!")
                        break
                time.sleep(0.5)

                # #specContents 전체 영역 캡처
                spec_box = driver.execute_script("""
                    const el = document.querySelector('#specContents');
                    if(!el) return null;
                    const r = el.getBoundingClientRect();
                    return {
                        top:    Math.round(r.top + window.scrollY),
                        left:   Math.round(r.left),
                        width:  Math.round(r.width),
                        height: Math.max(Math.round(r.height), el.scrollHeight)
                    };
                """)
                if spec_box and spec_box["height"] > 0:
                    raw = driver.get_screenshot_as_png()
                    img = PILImage.open(io.BytesIO(raw))
                    iw, ih = img.size
                    x1 = max(0, spec_box["left"])
                    y1 = max(0, spec_box["top"])
                    x2 = min(iw, spec_box["left"] + spec_box["width"])
                    y2 = min(ih, spec_box["top"]  + spec_box["height"])
                    tab_imgs.append((tab_name, img.crop((x1, y1, x2, y2))))
                    log(f"      → 캡처 완료 {x2-x1}x{y2-y1}px")

            # 탭별 이미지 세로 합치기
            if tab_imgs:
                total_h = sum(im.height for _, im in tab_imgs)
                max_w   = max(im.width  for _, im in tab_imgs)
                combined = PILImage.new("RGB", (max_w, total_h), (255, 255, 255))
                y_off = 0
                for _, im in tab_imgs:
                    combined.paste(im, (0, y_off))
                    y_off += im.height
                buf = io.BytesIO()
                combined.save(buf, "PNG")
                result["spec_png"] = buf.getvalue()
                log(f"   → {len(tab_imgs)}개 탭 합체: {max_w}x{total_h}px")

        driver.execute_script("window.scrollTo(0,0)")
        time.sleep(0.2)

        # 7. 영역 측정 + 캡처
        log("📸 상세 캡처 중...")
        boxes = []
        for sel in FAQ_FULL_SELECTORS:
            info = driver.execute_script(f"""
                const els=document.querySelectorAll('{sel}');
                return Array.from(els).map(el=>{{
                    const r=el.getBoundingClientRect();
                    return {{width:Math.round(r.width),height:Math.max(Math.round(r.height),el.scrollHeight||0),
                            top:Math.round(r.top+window.scrollY),left:Math.round(r.left)}};
                }});
            """)
            valid = [e for e in (info or []) if e["width"] > 0 and e["height"] > 0]
            if valid:
                # 같은 셀렉터에 여러 요소가 있으면 모두 포함 (예: faqWrap 2개)
                for v in valid:
                    boxes.append(v)
                log(f"   {sel}: {len(valid)}개 → " + ", ".join(f"{v['width']}x{v['height']}px" for v in valid))
            else:
                log(f"   {sel}: 미발견")

        if boxes:
            tgt = {
                "left":   min(b["left"] for b in boxes),
                "top":    min(b["top"]  for b in boxes),
                "width":  max(b["left"]+b["width"]  for b in boxes) - min(b["left"] for b in boxes),
                "height": max(b["top"] +b["height"] for b in boxes) - min(b["top"]  for b in boxes),
            }
            full_h = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(WIDTH, full_h)
            time.sleep(0.3)
            raw = driver.get_screenshot_as_png()
            img_full = PILImage.open(io.BytesIO(raw))
            iw, ih = img_full.size
            x1,y1 = max(0,tgt["left"]), max(0,tgt["top"])
            x2,y2 = min(iw,tgt["left"]+tgt["width"]), min(ih,tgt["top"]+tgt["height"])
            buf = io.BytesIO()
            img_full.crop((x1,y1,x2,y2)).save(buf,"PNG")
            result["detail_png"] = buf.getvalue()
            log(f"   → {x2-x1}x{y2-y1}px 완료")
        else:
            log("⚠️  영역 미발견 → 전체 페이지 캡처")
            result["detail_png"] = driver.get_screenshot_as_png()

    except Exception as e:
        result["error"] = str(e)
        log(f"❌ 오류: {e}")

    # 8. 대표이미지 병렬 다운로드
    if not result["error"] and imgs:
        import concurrent.futures
        log(f"⬇️  대표이미지 병렬 다운로드 ({len(imgs)}개)...")
        headers = {"User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/120.0.0.0", "Referer": url}

        # 중복 제거 + URL 정규화
        seen = set()
        tasks = []
        for i, img in enumerate(imgs):
            src = img["src"]
            if not src or src in seen: continue
            seen.add(src)
            if src.startswith("//"): src = "https:" + src
            elif src.startswith("/"): src = "https://www.samsung.com" + src
            fname = f"{len(tasks)+1:02d}_{sanitize(img['alt'][:15]) or 'img'}.jpg"
            tasks.append((src, fname))

        def _download(args):
            src, fname = args
            try:
                req = urllib.request.Request(src, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                _im = PILImage.open(io.BytesIO(data)).convert("RGB")
                _im = _im.resize((500, 500), PILImage.LANCZOS)
                _buf = io.BytesIO()
                _im.save(_buf, "JPEG", quality=90)
                return fname, _buf.getvalue(), None
            except Exception as e:
                return fname, None, str(e)

        # 최대 5개 스레드로 병렬 다운로드
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(_download, t): t for t in tasks}
            ordered = {}
            for f in concurrent.futures.as_completed(futures):
                fname, data, err = f.result()
                if err:
                    log(f"   ❌ {fname}: {err}")
                else:
                    ordered[fname] = data
                    log(f"   ✅ {fname} ({len(data)//1024}KB)")

        # 파일명 순서대로 정렬
        for src, fname in tasks:
            if fname in ordered:
                result["images"].append({"filename": fname, "data": ordered[fname]})

        log(f"✅ 완료! 대표이미지 {len(result['images'])}개")

    return result


def run_capture(url: str, log=print) -> dict:
    """단일 URL 캡처 — Chrome 1회 시작/종료"""
    driver = None
    try:
        log("🚀 브라우저 시작 중...")
        driver = make_driver()
        return _capture_one(driver, url, log)
    finally:
        if driver:
            driver.quit()


def run_capture_multi(urls: list, log=print) -> list:
    """여러 URL 캡처 — Chrome 1번만 시작해서 모두 처리"""
    results = []
    driver  = None
    try:
        log("🚀 브라우저 시작 중... (전체 공유)")
        driver = make_driver()
        for i, url in enumerate(urls, 1):
            log(f"\n── [{i}/{len(urls)}] {url[:60]}")
            result = _capture_one(driver, url, log)
            results.append(result)
    except Exception as e:
        log(f"❌ 브라우저 오류: {e}")
    finally:
        if driver:
            driver.quit()
            log("🔒 브라우저 종료")
    return results


def _to_jpg(png_bytes: bytes, quality: int = 90) -> bytes:
    """PNG bytes → JPG bytes 변환"""
    buf = io.BytesIO()
    PILImage.open(io.BytesIO(png_bytes)).convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def make_zip(product_name: str, detail_png: bytes, images: list, spec_png: bytes = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if detail_png:
            zf.writestr(f"{product_name}_상품상세.jpg", _to_jpg(detail_png))
        if spec_png:
            zf.writestr(f"{product_name}_스펙.jpg", _to_jpg(spec_png))
        for img in images:
            # 대표이미지는 이미 JPG지만 확장자 보정
            fname = img["filename"]
            if not fname.lower().endswith(".jpg"):
                fname = fname.rsplit(".", 1)[0] + ".jpg"
            zf.writestr(f"{product_name}/{fname}", img["data"])
    return buf.getvalue()
