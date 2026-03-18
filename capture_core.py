"""
Samsung 상품 페이지 캡처 핵심 로직 (selenium — greenlet 불필요)
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

WIDTH    = 1000
WAIT_SEC = 3

FAQ_FULL_SELECTORS = [
    "div.wrap-component.feature-benefit",
    "div.wrap-component.textbox-simple",
    "section.faqWrap",
    "div.itm-notice",
    "#compGoodsSpec",
]

JS_EXPAND_FAQ = """
const section = document.querySelector('section.faqWrap');
if (!section) return {ok:false};
const SKIP = new Set(['SCRIPT','STYLE','NOSCRIPT','META','LINK','HEAD']);
let opened = 0;
['[class*="chat"]','[class*="float"]','.layer-counsel','.counsel-btn','.sticky'].forEach(sel => {
    document.querySelectorAll(sel).forEach(el => { if (!SKIP.has(el.tagName)) el.style.display='none'; });
});
section.querySelectorAll('.faqTitle').forEach(t => {
    t.classList.add('_actv');
    t.setAttribute('aria-expanded','true');
    const a = t.nextElementSibling;
    if (a && !SKIP.has(a.tagName)) {
        a.style.cssText='display:block!important;height:auto!important;max-height:none!important;overflow:visible!important;visibility:visible!important;opacity:1!important;';
        opened++;
    }
});
if (opened === 0) {
    section.querySelectorAll('li').forEach(li => {
        li.classList.add('on','active','open');
        const ch=[...li.children].filter(c=>!SKIP.has(c.tagName));
        if (ch.length>=2) { for(let i=1;i<ch.length;i++){ch[i].style.display='block';ch[i].style.height='auto';ch[i].style.overflow='visible';opened++;} }
    });
}
const seen=new Set();
section.querySelectorAll('h2,h3').forEach(h=>{const t=h.textContent.trim();if(seen.has(t))h.style.display='none';else seen.add(t);});
return {ok:true, opened:opened};
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
if(!s) return {ok:false,len:0};
const sl=s.querySelector('#specLayer,[name="specLayer"]');
if(sl) sl.style.display='none';
const lb=s.querySelector('.spec-link-box');
if(lb) lb.style.display='none';
const tbl=s.querySelector('.spec-table');
return {ok:true, len: tbl ? tbl.innerHTML.trim().length : 0};
"""


def sanitize(name: str) -> str:
    return re.sub(r'[\/:*?"<>|]', '_', name).strip()


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={WIDTH},900")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
    # Streamlit Cloud / Docker 환경 대응
    import shutil
    chrome_bin = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if chrome_bin:
        opts.binary_location = chrome_bin
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception:
        # chromedriver 경로 직접 지정
        driver = webdriver.Chrome(
            service=Service("/usr/bin/chromedriver"),
            options=opts,
        )
    return driver


def run_capture(url: str, log=print) -> dict:
    result = {"product_name": "", "detail_png": None, "images": [], "error": None}
    driver = None

    try:
        driver = make_driver()

        # 1. 페이지 로드
        log("📄 페이지 로딩 중...")
        driver.get(url)
        time.sleep(WAIT_SEC)

        # 2. 상품명 추출
        product_name = driver.execute_script("""
            const sels=['#compGoodRevampFeaturesName h2.prod-name','#compGoodRevampFeaturesName h2','h2.prod-name','.prod-name','h1.prod-title','h1'];
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

        # 4. 스크롤 (lazy-load)
        log("🔄 스크롤 중...")
        driver.execute_script("""
            return new Promise(resolve=>{
                const dist=400;let pos=0;
                const id=setInterval(()=>{window.scrollBy(0,dist);pos+=dist;
                if(pos>=document.body.scrollHeight){clearInterval(id);window.scrollTo(0,0);resolve();}},100);
            });
        """)
        time.sleep(1.2)

        # 5. FAQ 펼치기
        log("📖 FAQ 펼치는 중...")
        driver.execute_script(JS_EXPAND_FAQ)
        time.sleep(0.6)

        # 6. 스펙 탭 + AJAX 대기
        log("📊 스펙 로딩 중...")
        driver.execute_script(JS_CLICK_SPEC_TAB)
        time.sleep(1.5)
        driver.execute_script(JS_EXPAND_SPEC)
        for i in range(10):
            time.sleep(0.8)
            check = driver.execute_script(JS_SPEC_CHECK)
            log(f"   AJAX 대기 {i+1}초 (len={check.get('len',0)})")
            if check.get("len", 0) > 100:
                log("   → 완료!")
                break
        time.sleep(0.5)
        driver.execute_script("window.scrollTo(0,0)")
        time.sleep(0.3)

        # 7. 영역 측정 + 캡처
        log("📸 상세 캡처 중...")
        boxes = []
        for sel in FAQ_FULL_SELECTORS:
            info = driver.execute_script(f"""
                const els=document.querySelectorAll('{sel}');
                return Array.from(els).map(el=>{{
                    const r=el.getBoundingClientRect();
                    return {{width:Math.round(r.width),height:Math.max(Math.round(r.height),el.scrollHeight||0),top:Math.round(r.top+window.scrollY),left:Math.round(r.left)}};
                }});
            """)
            valid = [e for e in (info or []) if e["width"] > 0 and e["height"] > 0]
            if valid:
                boxes.append(valid[0])
                log(f"   {sel}: {valid[0]['width']}x{valid[0]['height']}px")
            else:
                log(f"   {sel}: 미발견")

        if boxes:
            tgt = {
                "left":   min(b["left"] for b in boxes),
                "top":    min(b["top"]  for b in boxes),
                "width":  max(b["left"]+b["width"]  for b in boxes) - min(b["left"] for b in boxes),
                "height": max(b["top"] +b["height"] for b in boxes) - min(b["top"]  for b in boxes),
            }
            # 뷰포트 높이 확장
            full_h = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(WIDTH, full_h)
            time.sleep(0.5)
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
    finally:
        if driver:
            driver.quit()

    # 8. 대표이미지 다운로드
    if not result["error"] and imgs:
        log(f"⬇️  대표이미지 다운로드 ({len(imgs)}개)...")
        headers = {"User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/120.0.0.0", "Referer": url}
        seen = set(); idx = 1
        for img in imgs:
            src = img["src"]
            if not src or src in seen: continue
            seen.add(src)
            if src.startswith("//"): src = "https:" + src
            elif src.startswith("/"): src = "https://www.samsung.com" + src
            fname = f"{idx:02d}_{sanitize(img['alt'][:15]) or 'img'}.png"
            try:
                req = urllib.request.Request(src, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                # 500x500 리사이즈 + JPG 변환
                from PIL import Image as _Img
                import io as _io
                try:
                    _im = _Img.open(_io.BytesIO(data)).convert("RGB")
                    _im = _im.resize((500, 500), _Img.LANCZOS)
                    _buf = _io.BytesIO()
                    _im.save(_buf, "JPEG", quality=90)
                    data = _buf.getvalue()
                    fname = fname.replace(".png", ".jpg")
                except Exception:
                    pass
                result["images"].append({"filename": fname, "data": data})
                log(f"   [{idx:02d}] ✅ {fname} ({len(data)//1024}KB)")
                idx += 1
            except Exception as e:
                log(f"   [{idx:02d}] ❌ {e}")
                idx += 1
        log(f"✅ 완료! 대표이미지 {len(result['images'])}개")

    return result


def make_zip(product_name: str, detail_png: bytes, images: list) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if detail_png:
            zf.writestr(f"{product_name}_상품상세.png", detail_png)
        for img in images:
            zf.writestr(f"{product_name}/{img['filename']}", img["data"])
    return buf.getvalue()
