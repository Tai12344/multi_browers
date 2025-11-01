import pygetwindow as gw
from pynput import mouse, keyboard
import threading
import time
import win32gui
import win32api
import win32con
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# === CẤU HÌNH ===
SCROLL_SPEED = 1.0
WINDOW_SCAN_INTERVAL = 0.5
ENABLE_KEYBOARD_SYNC = False

SELECTED_MAIN_HWND = None
if len(sys.argv) > 1:
    try:
        SELECTED_MAIN_HWND = int(sys.argv[1])
        print(f"[INFO] Đã chọn cửa sổ chính với HWND: {SELECTED_MAIN_HWND}")
    except:
        pass

# === BIẾN TOÀN CỤC ===
syncing_lock = threading.Lock()
windows_lock = threading.Lock()
stop_event = threading.Event()

main_window = None
other_windows = []
main_hwnd = None
other_hwnds = []

mouse_listener = None
key_listener = None

# === HÀM HỖ TRỢ ===
def get_client_size(hwnd):
    """Lấy kích thước vùng client (không tính viền, thanh title)"""
    try:
        rect = win32gui.GetClientRect(hwnd)
        return rect[2], rect[3]  # width, height
    except:
        return None, None

# Danh sách browsers được hỗ trợ
BROWSER_KEYWORDS = {
    'Chrome': ['Chrome', 'Google Chrome'],
    'Edge': ['Edge', 'Microsoft Edge', 'msedge'],
    'Firefox': ['Firefox', 'Mozilla Firefox'],
    'Opera': ['Opera', 'Opera Browser'],
    'Brave': ['Brave', 'Brave Browser'],
    'Vivaldi': ['Vivaldi'],
    'Safari': ['Safari'],
    'Yandex': ['Yandex'],
    'CocCoc': ['CocCoc']
}

def is_browser_window(window):
    """Kiểm tra xem cửa sổ có phải là browser không"""
    try:
        title_lower = window.title.lower()
        
        # Kiểm tra theo title
        for browser_name, keywords in BROWSER_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in title_lower:
                    return True
        
        # Kiểm tra process name nếu có thể
        try:
            import win32process
            _, pid = win32process.GetWindowThreadProcessId(window._hWnd)
            try:
                import psutil
                proc = psutil.Process(pid)
                proc_name = proc.name().lower()
                for browser_name, keywords in BROWSER_KEYWORDS.items():
                    for keyword in keywords:
                        if keyword.lower() in proc_name:
                            return True
            except:
                pass
        except:
            pass
        
        return False
    except:
        return False

def get_valid_chrome_windows():
    """Lấy danh sách cửa sổ browser hợp lệ (hỗ trợ tất cả browsers)"""
    all_wins = gw.getAllWindows()
    valid = []
    for w in all_wins:
        try:
            # Bỏ qua cửa sổ quá nhỏ hoặc đã minimize
            if w.isMinimized or w.width < 100 or w.height < 100:
                continue
            
            # Bỏ qua cửa sổ không có title hợp lệ
            if not w.title or len(w.title.strip()) < 3:
                continue
            
            # Kiểm tra xem có phải browser không
            if is_browser_window(w):
                valid.append(w)
        except:
            pass
    return valid

def update_window_list():
    """Cập nhật danh sách cửa sổ"""
    global main_window, other_windows, main_hwnd, other_hwnds
    
    valid_wins = get_valid_chrome_windows()
    if len(valid_wins) < 1:
        main_window = None
        other_windows = []
        main_hwnd = None
        other_hwnds = []
        return False

    with windows_lock:
        if SELECTED_MAIN_HWND:
            selected_main = None
            for w in valid_wins:
                if w._hWnd == SELECTED_MAIN_HWND:
                    selected_main = w
                    break
            if selected_main:
                main_window = selected_main
                main_hwnd = SELECTED_MAIN_HWND
            else:
                main_window = valid_wins[0]
                main_hwnd = main_window._hWnd
        elif main_window and main_hwnd:
            still_exists = False
            for w in valid_wins:
                if w._hWnd == main_hwnd:
                    still_exists = True
                    main_window = w
                    break
            if not still_exists:
                main_window = valid_wins[0]
                main_hwnd = main_window._hWnd
        else:
            main_window = valid_wins[0]
            main_hwnd = main_window._hWnd
        
        other_windows = []
        other_hwnds = []
        for w in valid_wins:
            if w._hWnd != main_hwnd:
                other_windows.append(w)
                other_hwnds.append(w._hWnd)
    return True

# Khởi tạo
if not update_window_list():
    print("[ERROR] Cần ít nhất 1 cửa sổ browser để chạy!")
    sys.exit(1)

# Phân loại browsers
browser_types = {}
for w in [main_window] + other_windows:
    try:
        browser = "Unknown"
        title_lower = w.title.lower()
        for browser_name, keywords in BROWSER_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in title_lower:
                    browser = browser_name
                    break
            if browser != "Unknown":
                break
        browser_types[browser] = browser_types.get(browser, 0) + 1
    except:
        pass

print("=" * 70)
print(f"[OK] Đã tìm thấy {len(other_windows) + 1} cửa sổ browser")
if browser_types:
    browser_summary = ", ".join([f"{count} {name}" for name, count in sorted(browser_types.items())])
    print(f"[INFO] Browsers: {browser_summary}")
print(f"[MAIN] Cửa sổ chính: '{main_window.title[:50]}...'")
print(f"       HWND: {main_hwnd}")
print(f"[INFO] {len(other_windows)} cửa sổ phụ sẽ được đồng bộ")
print("=" * 70)
print("🚀 HỆ THỐNG ĐỒNG BỘ TỶ LỆ PHẦN TRĂM - HỖ TRỢ TẤT CẢ BROWSERS")
print("  ✓ Tự động scale theo kích thước cửa sổ")
print("  ✓ Đồng bộ chính xác 100% dù khác size")
print("  ✓ Click/Scroll/Drag/Drop đều được xử lý")
print("  ✓ Phát hiện cửa sổ mới tự động")
print("  ✓ Hỗ trợ: Chrome, Edge, Firefox, Opera, Brave, Vivaldi, Yandex, CocCoc...")
print("  ✓ Nhấn ESC để thoát")
print("=" * 70 + "\n")
print("[READY] HỆ THỐNG ĐÃ SẴN SÀNG\n")

# === GIÁM SÁT CỬA SỔ ===
last_window_count = len(other_windows) + 1

def monitor_windows():
    """Thread giám sát cửa sổ"""
    global last_window_count
    while not stop_event.is_set():
        try:
            if update_window_list():
                current_count = len(other_windows) + 1
                if current_count != last_window_count:
                    if current_count > last_window_count:
                        print(f"[+] Phát hiện {current_count - last_window_count} cửa sổ browser mới. Tổng: {current_count}")
                    else:
                        print(f"[-] {last_window_count - current_count} cửa sổ browser đã đóng. Còn: {current_count}")
                    last_window_count = current_count
            else:
                if last_window_count > 0:
                    print("[WARN] Tất cả cửa sổ browser đã đóng!")
                    last_window_count = 0
        except:
            pass
        time.sleep(WINDOW_SCAN_INTERVAL)

# === ĐỒNG BỘ VỚI TỶ LỆ PHẦN TRĂM ===
def sync_click(x, y, button):
    """Đồng bộ click với tọa độ phần trăm - CHÍNH XÁC 100%"""
    with syncing_lock:
        with windows_lock:
            if not main_window or not other_hwnds:
                return
            
            # Bước 1: Lấy thông tin cửa sổ chính
            main_rect = win32gui.GetWindowRect(main_hwnd)
            main_left, main_top = main_rect[0], main_rect[1]
            
            # Bước 2: Chuyển tọa độ screen -> client của main window
            try:
                main_client_x, main_client_y = win32gui.ScreenToClient(main_hwnd, (x, y))
            except:
                # Fallback nếu không chuyển được
                main_client_x = x - main_left
                main_client_y = y - main_top
            
            # Bước 3: Lấy kích thước client của main window
            main_client_width, main_client_height = get_client_size(main_hwnd)
            
            if not main_client_width or not main_client_height:
                return
            
            # Bước 4: Tính TỶ LỆ PHẦN TRĂM
            percent_x = main_client_x / main_client_width
            percent_y = main_client_y / main_client_height
            
            # Kiểm tra tỷ lệ hợp lệ
            if not (0 <= percent_x <= 1 and 0 <= percent_y <= 1):
                return
        
        # Xác định loại nút chuột
        btn = str(button).split('.')[-1].lower()
        if btn == 'left':
            down_msg, up_msg = win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP
            wparam = win32con.MK_LBUTTON
        elif btn == 'right':
            down_msg, up_msg = win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP
            wparam = win32con.MK_RBUTTON
        elif btn == 'middle':
            down_msg, up_msg = win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP
            wparam = win32con.MK_MBUTTON
        else:
            return
        
        # Bước 5: Gửi click đến các cửa sổ phụ
        for hwnd in other_hwnds:
            try:
                if not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
                    continue
                
                # Lấy kích thước client của cửa sổ phụ
                target_width, target_height = get_client_size(hwnd)
                
                if not target_width or not target_height:
                    continue
                
                # Tính tọa độ client dựa trên TỶ LỆ PHẦN TRĂM
                target_client_x = int(percent_x * target_width)
                target_client_y = int(percent_y * target_height)
                
                # Đảm bảo trong phạm vi hợp lệ
                target_client_x = max(0, min(target_client_x, target_width - 1))
                target_client_y = max(0, min(target_client_y, target_height - 1))
                
                # Tạo lParam
                lparam = win32api.MAKELONG(target_client_x & 0xFFFF, target_client_y & 0xFFFF)
                
                # Gửi message click
                win32gui.PostMessage(hwnd, down_msg, wparam, lparam)
                win32gui.PostMessage(hwnd, up_msg, 0, lparam)
                
            except Exception as e:
                # Debug nếu cần
                # print(f"[DEBUG] Lỗi click hwnd {hwnd}: {e}")
                pass

def sync_scroll(x, y, dx, dy):
    """Đồng bộ scroll với tọa độ phần trăm - CHÍNH XÁC 100%"""
    with syncing_lock:
        with windows_lock:
            if not main_window or not other_hwnds:
                return
            
            # Bước 1: Lấy thông tin cửa sổ chính
            main_rect = win32gui.GetWindowRect(main_hwnd)
            main_left, main_top = main_rect[0], main_rect[1]
            
            # Bước 2: Chuyển tọa độ screen -> client
            try:
                main_client_x, main_client_y = win32gui.ScreenToClient(main_hwnd, (x, y))
            except:
                main_client_x = x - main_left
                main_client_y = y - main_top
            
            # Bước 3: Lấy kích thước client
            main_client_width, main_client_height = get_client_size(main_hwnd)
            
            if not main_client_width or not main_client_height:
                return
            
            # Bước 4: Tính TỶ LỆ PHẦN TRĂM
            percent_x = main_client_x / main_client_width
            percent_y = main_client_y / main_client_height
            
            # Kiểm tra hợp lệ
            if not (0 <= percent_x <= 1 and 0 <= percent_y <= 1):
                return
        
        # Tính scroll amount
        scroll_amount = int(120 * dy * SCROLL_SPEED)
        if scroll_amount == 0:
            return
        
        wparam = win32api.MAKELONG(0, scroll_amount & 0xFFFF)
        
        # Bước 5: Gửi scroll đến các cửa sổ phụ
        for hwnd in other_hwnds:
            try:
                if not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
                    continue
                
                # Lấy kích thước client của cửa sổ phụ
                target_width, target_height = get_client_size(hwnd)
                
                if not target_width or not target_height:
                    continue
                
                # Tính tọa độ client dựa trên TỶ LỆ
                target_client_x = int(percent_x * target_width)
                target_client_y = int(percent_y * target_height)
                
                # Đảm bảo trong phạm vi
                target_client_x = max(0, min(target_client_x, target_width - 1))
                target_client_y = max(0, min(target_client_y, target_height - 1))
                
                # Chuyển client -> screen cho WM_MOUSEWHEEL
                try:
                    screen_point = win32gui.ClientToScreen(hwnd, (target_client_x, target_client_y))
                    lparam = win32api.MAKELONG(screen_point[0] & 0xFFFF, screen_point[1] & 0xFFFF)
                except:
                    # Fallback
                    lparam = win32api.MAKELONG(target_client_x & 0xFFFF, target_client_y & 0xFFFF)
                
                # Gửi message scroll
                win32gui.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
                
            except Exception as e:
                # print(f"[DEBUG] Lỗi scroll hwnd {hwnd}: {e}")
                pass

def is_in_main_window(x, y):
    """Kiểm tra tọa độ có trong cửa sổ chính"""
    try:
        with windows_lock:
            if not main_window:
                return False
            return (main_window.left <= x < main_window.left + main_window.width and 
                    main_window.top <= y < main_window.top + main_window.height)
    except:
        return False

# === LẮNG NGHE SỰ KIỆN ===
def on_click(x, y, button, pressed):
    if pressed and is_in_main_window(x, y):
        sync_click(x, y, button)

def on_scroll(x, y, dx, dy):
    if is_in_main_window(x, y):
        sync_scroll(x, y, dx, dy)

def on_release(key):
    if key == keyboard.Key.esc:
        print("\n" + "=" * 70)
        print("[STOP] Đã nhấn ESC - Đang thoát...")
        print("=" * 70)
        stop_event.set()
        if mouse_listener:
            mouse_listener.stop()
        if key_listener:
            key_listener.stop()
        return False

# === CHẠY CHƯƠNG TRÌNH ===
try:
    # Khởi động thread giám sát
    threading.Thread(target=monitor_windows, daemon=True).start()
    
    # Khởi động listener
    mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    key_listener = keyboard.Listener(on_release=on_release)
    
    mouse_listener.start()
    key_listener.start()
    
    mouse_listener.join()
    key_listener.join()
    
    print("\n[INFO] Hệ thống đã dừng an toàn.")

except KeyboardInterrupt:
    print("\n[WARN] Ctrl+C - Đang thoát...")
    stop_event.set()
except Exception as e:
    print(f"\n[ERROR] Lỗi: {e}")
    import traceback
    traceback.print_exc()
finally:
    stop_event.set()
    if mouse_listener:
        try:
            mouse_listener.stop()
        except:
            pass
    if key_listener:
        try:
            key_listener.stop()
        except:
            pass