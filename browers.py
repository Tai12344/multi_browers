import threading
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By # Thư viện để tìm kiếm element
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from webdriver_manager.chrome import ChromeDriverManager

# =================================================================
# PHẦN BẠN CẦN TÙY CHỈNH
# =================================================================

# 1. DANH SÁCH CÁC THƯ MỤC HỒ SƠ
# Hãy đảm bảo đường dẫn này chính xác trên máy của bạn
profile_paths = [
    r"D:\\MultiBrowers\\Profile 1",
    r"D:\\MultiBrowers\\Profile 2",
    r"D:\\MultiBrowers\\Profile 3",
]

# Cấu hình chung
DEFAULT_URL = (
    "https://tiki.vn/dien-thoai-tecno-spark-go-1-3gb-64gb-hang-chinh-hang-p277930407.html?spid=277930411"
)
HEADLESS = False  # Đổi sang True nếu muốn chạy ẩn
MIRROR_DURATION_SEC = 300  # Thời gian chạy mô phỏng (5 phút)
LEADER_INDEX = 0  # Trình duyệt dẫn đầu để ghi nhận thao tác
VIEWPORT_SIZE = (1366, 768)  # Chuẩn hóa kích thước cửa sổ

# 2. HÀM THỰC HIỆN CÔNG VIỆC "QUÉT"
# Đây là nơi bạn định nghĩa các hành động cho mỗi trình duyệt
def perform_scan(driver):

    try:
        driver.get(DEFAULT_URL)
        print(f"[{driver.session_id[-5:]}] Đã truy cập URL.")

        wait = WebDriverWait(driver, 15)

        # Đồng bộ URL, in xác nhận
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        print(f"[{driver.session_id[-5:]}] Trang đã sẵn sàng để mirror")

    except Exception as e:
        print(f"[{getattr(driver, 'session_id', '-----')[-5:]}] Lỗi khi quét: {e}")

# =================================================================
# PHẦN LÕI ĐIỀU KHIỂN ĐA LUỒNG (Thường không cần sửa)
# =================================================================

def launch_and_scan(profile_path):
    """
    Hàm khởi chạy một trình duyệt với hồ sơ riêng và gọi hàm quét.
    """
    print(f"Đang khởi chạy hồ sơ: {profile_path}")
    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={profile_path}")
    if HEADLESS:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"--window-size={VIEWPORT_SIZE[0]},{VIEWPORT_SIZE[1]}")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--force-device-scale-factor=1")

    service = Service(ChromeDriverManager().install())
    driver = None # Khởi tạo driver là None
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        # Chuẩn hóa viewport cho non-headless
        try:
            if not HEADLESS:
                driver.set_window_size(VIEWPORT_SIZE[0], VIEWPORT_SIZE[1])
        except Exception:
            pass
        # Zoom 100%
        try:
            driver.execute_script("document.body.style.zoom='100%'")
        except Exception:
            pass
        perform_scan(driver)
        return driver
    except Exception:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        raise

# --- Phần chính để thực thi ---
def _inject_common_helper(driver):
    helper_js = r"""
    (function(){
      if (window.__mirrorHelperInstalled) return; window.__mirrorHelperInstalled = true;
      // Find the primary scrollable container (largest overflow content)
      window.__getScrollTarget = function(){
        if (window._mirrorScrollEl && document.contains(window._mirrorScrollEl)) return window._mirrorScrollEl;
        var docs = [document.scrollingElement || document.documentElement, document.body];
        var best = null, bestDelta = 0;
        var all = document.querySelectorAll('*');
        for (var i=0;i<all.length;i++){
          var el = all[i];
          if (!(el instanceof Element)) continue;
          var delta = (el.scrollHeight - el.clientHeight) + (el.scrollWidth - el.clientWidth);
          if (delta > bestDelta && getComputedStyle(el).overflowY !== 'hidden'){
            bestDelta = delta; best = el;
          }
        }
        best = best || docs[0] || docs[1] || window;
        window._mirrorScrollEl = best; return best;
      };
    })();
    return true;
    """
    driver.execute_script(helper_js)


def _inject_leader_capture_script(driver):
    capture_js = r"""
    (function(){
      if (window.__mirrorInstalled) return; 
      window.__mirrorInstalled = true;
      window._eventQueue = [];

      function cssPath(el){
        if (!(el instanceof Element)) return null;
        var path = [];
        while (el && el.nodeType === Node.ELEMENT_NODE && path.length < 25){
          var selector = el.nodeName.toLowerCase();
          if (el.id){
            selector += '#' + CSS.escape(el.id);
            path.unshift(selector);
            break;
          } else {
            var sib = el, nth = 1;
            while (sib = sib.previousElementSibling){
              if (sib.nodeName.toLowerCase() === selector) nth++;
            }
            selector += ':nth-of-type(' + nth + ')';
          }
          path.unshift(selector);
          el = el.parentNode;
        }
        return path.join(' > ');
      }

      function pushEvent(evt){
        window._eventQueue.push(evt);
      }

      // Poll-based scroll capture on main scrollable container
      var tgt = (window.__getScrollTarget && window.__getScrollTarget()) || window;
      var lastSX = (tgt===window?window.scrollX:tgt.scrollLeft), lastSY = (tgt===window?window.scrollY:tgt.scrollTop);
      setInterval(function(){
        if (!tgt || !(document.contains(tgt) || tgt===window)){
          tgt = (window.__getScrollTarget && window.__getScrollTarget()) || window;
        }
        var sx = (tgt===window?window.scrollX:tgt.scrollLeft);
        var sy = (tgt===window?window.scrollY:tgt.scrollTop);
        if (sx !== lastSX || sy !== lastSY){
          lastSX = sx; lastSY = sy;
          pushEvent({type:'scroll', x: sx, y: sy, ts: Date.now()});
        }
      }, 120);

      document.addEventListener('click', function(e){
        var sel = cssPath(e.target);
        pushEvent({type:'click', selector: sel, clientX: e.clientX, clientY: e.clientY, ts: Date.now()});
      }, true);

      // Wheel (delta-based) to support scrolling inside containers
      document.addEventListener('wheel', function(e){
        pushEvent({type:'wheel', deltaX: e.deltaX||0, deltaY: e.deltaY||0, ts: Date.now()});
      }, {passive:true});

      // Mouse move for visual following (coordinates only)
      document.addEventListener('mousemove', function(e){
        pushEvent({type:'mousemove', clientX: e.clientX, clientY: e.clientY, ts: Date.now()});
      }, {passive:true});

      document.addEventListener('input', function(e){
        var t = e.target;
        var sel = cssPath(t);
        var val = (t && 'value' in t) ? t.value : null;
        pushEvent({type:'input', selector: sel, value: val, ts: Date.now()});
      }, true);

      window.addEventListener('hashchange', function(){
        pushEvent({type:'navigate', url: location.href, ts: Date.now()});
      });
      window.addEventListener('popstate', function(){
        pushEvent({type:'navigate', url: location.href, ts: Date.now()});
      });

      var lastUrl = location.href;
      setInterval(function(){
        if (location.href !== lastUrl){
          lastUrl = location.href;
          pushEvent({type:'navigate', url: location.href, ts: Date.now()});
        }
      }, 500);
    })();
    return true;
    """
    driver.execute_script(capture_js)


def _drain_events(driver):
    return driver.execute_script(
        "var q = window._eventQueue || []; window._eventQueue = []; return q;"
    )


def _apply_event(driver, event):
    etype = event.get('type')
    if etype == 'scroll':
        driver.execute_script(
            r"(function(x,y){\n"
            r"  function getTarget(){\n"
            r"    if (window._mirrorScrollEl && document.contains(window._mirrorScrollEl)) return window._mirrorScrollEl;\n"
            r"    var base = document.scrollingElement || document.documentElement || document.body;\n"
            r"    var best = null, bestDelta = 0;\n"
            r"    var all = document.querySelectorAll('*');\n"
            r"    for (var i=0;i<all.length;i++){\n"
            r"      var el = all[i];\n"
            r"      if (!(el instanceof Element)) continue;\n"
            r"      var delta = (el.scrollHeight - el.clientHeight) + (el.scrollWidth - el.clientWidth);\n"
            r"      if (delta > bestDelta && getComputedStyle(el).overflowY !== 'hidden'){ bestDelta = delta; best = el; }\n"
            r"    }\n"
            r"    best = best || base || window; window._mirrorScrollEl = best; return best;\n"
            r"  }\n"
            r"  var t = getTarget();\n"
            r"  if (t===window || t===document.body || t===document.documentElement || t===document.scrollingElement){ window.scrollTo(x,y); }\n"
            r"  else { try{ t.scrollTo({top:y,left:x,behavior:'auto'});}catch(e){ t.scrollTop=y; t.scrollLeft=x; } }\n"
            r"})(arguments[0], arguments[1]);",
            event.get('x', 0),
            event.get('y', 0),
        )
        return
    if etype == 'click':
        selector = event.get('selector')
        cx = event.get('clientX')
        cy = event.get('clientY')
        if cx is not None and cy is not None:
            driver.execute_script(
                "var el = document.elementFromPoint(arguments[0], arguments[1]); if(el){var ev=new MouseEvent('click',{bubbles:true,cancelable:true,view:window,clientX:arguments[0],clientY:arguments[1]}); el.dispatchEvent(ev);}",
                cx,
                cy,
            )
        elif selector:
            driver.execute_script(
                "var el = document.querySelector(arguments[0]); if(el){el.click();}", selector
            )
        return
    if etype == 'wheel':
        dx = float(event.get('deltaX', 0) or 0)
        dy = float(event.get('deltaY', 0) or 0)
        driver.execute_script(
            r"(function(dx,dy){\n"
            r"  function getTarget(){\n"
            r"    if (window._mirrorScrollEl && document.contains(window._mirrorScrollEl)) return window._mirrorScrollEl;\n"
            r"    var base = document.scrollingElement || document.documentElement || document.body;\n"
            r"    var best = null, bestDelta = 0;\n"
            r"    var all = document.querySelectorAll('*');\n"
            r"    for (var i=0;i<all.length;i++){\n"
            r"      var el = all[i]; if (!(el instanceof Element)) continue;\n"
            r"      var delta = (el.scrollHeight - el.clientHeight) + (el.scrollWidth - el.clientWidth);\n"
            r"      if (delta > bestDelta && getComputedStyle(el).overflowY !== 'hidden'){ bestDelta = delta; best = el; }\n"
            r"    }\n"
            r"    best = best || base || window; window._mirrorScrollEl = best; return best;\n"
            r"  }\n"
            r"  var t = getTarget();\n"
            r"  if (t===window || t===document.body || t===document.documentElement || t===document.scrollingElement){ window.scrollBy(dx,dy); }\n"
            r"  else { try{ t.scrollBy({top:dy,left:dx,behavior:'auto'});}catch(e){ t.scrollTop+=dy; t.scrollLeft+=dx; } }\n"
            r"})(arguments[0], arguments[1]);",
            dx,
            dy,
        )
        return
    if etype == 'mousemove':
        cx = event.get('clientX')
        cy = event.get('clientY')
        if cx is not None and cy is not None:
            driver.execute_script(
                "var el = document.elementFromPoint(arguments[0], arguments[1]); if(el){var ev=new MouseEvent('mousemove',{bubbles:true,view:window,clientX:arguments[0],clientY:arguments[1]}); el.dispatchEvent(ev);}",
                cx,
                cy,
            )
        return
    if etype == 'input':
        selector = event.get('selector')
        value = event.get('value')
        if selector is not None:
            driver.execute_script(
                "var el = document.querySelector(arguments[0]); if(el){el.value=arguments[1]; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));}",
                selector,
                value,
            )
        return
    if etype == 'navigate':
        url = event.get('url')
        if url:
            driver.execute_script("if(location.href!==arguments[0]){ location.href = arguments[0]; }", url)
        return


if __name__ == "__main__":
    max_workers = min(len(profile_paths), 9)
    drivers: List[webdriver.Chrome] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(launch_and_scan, p): p for p in profile_paths}
        for future in as_completed(futures):
            path = futures[future]
            try:
                drv = future.result()
                if drv:
                    drivers.append(drv)
            except Exception as exc:
                print(f"Lỗi ở hồ sơ {path}: {exc}")

    if not drivers:
        print("Không có trình duyệt nào khởi chạy thành công.")
    else:
        # Đồng bộ tất cả trình duyệt tới URL ban đầu
        leader = drivers[min(LEADER_INDEX, len(drivers)-1)]
        try:
            for drv in drivers:
                if drv is not leader:
                    try:
                        drv.get(DEFAULT_URL)
                    except Exception:
                        pass
            # Inject helper on all, and capture on leader
            for drv in drivers:
                try:
                    _inject_common_helper(drv)
                except Exception:
                    pass
            _inject_leader_capture_script(leader)

            start = time.time()
            while time.time() - start < MIRROR_DURATION_SEC:
                try:
                    events = _drain_events(leader)
                except Exception:
                    events = []
                if events:
                    for ev in events:
                        for drv in drivers:
                            if drv is leader:
                                continue
                            try:
                                _apply_event(drv, ev)
                            except Exception:
                                pass
                time.sleep(0.15)
        finally:
            for drv in drivers:
                try:
                    try:
                        drv.execute_script("window.close();")
                    except Exception:
                        pass
                    try:
                        drv.quit()
                    except Exception:
                        pass
                except Exception:
                    pass

    print("\n======= TẤT CẢ CÁC LUỒNG ĐÃ HOÀN THÀNH! =======")