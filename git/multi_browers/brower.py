import pygetwindow as gw
from pynput import mouse, keyboard
import threading
import time
import win32gui
import win32api
import win32con

# === CẤU HÌNH ===
SCROLL_SPEED = 1.0          # Tốc độ cuộn (1.0 = bình thường)
WINDOW_SCAN_INTERVAL = 0.5  # Quét cửa sổ mới mỗi 0.5s (càng nhỏ càng nhanh phát hiện)
ENABLE_KEYBOARD_SYNC = False # Tắt đồng bộ phím (vì Win32 API không đồng bộ phím tốt)

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

# === KHỞI TẠO BAN ĐẦU ===
def get_valid_chrome_windows():
    """Lấy danh sách tất cả cửa sổ Chrome hợp lệ"""
    all_wins = gw.getWindowsWithTitle('Chrome')
    valid = []
    for w in all_wins:
        try:
            # Chỉ lấy cửa sổ không bị thu nhỏ và có kích thước > 0
            if not w.isMinimized and w.width > 100 and w.height > 100:
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
        # Giữ nguyên cửa sổ chính nếu còn tồn tại
        if main_window and main_hwnd:
            # Kiểm tra main window còn trong danh sách không
            current_main = None
            for w in valid_wins:
                try:
                    if w._hWnd == main_hwnd:
                        current_main = w
                        break
                except:
                    pass
            
            if current_main:
                main_window = current_main
            else:
                # Main window bị đóng, chọn cửa sổ đầu tiên làm main
                main_window = valid_wins[0]
                main_hwnd = main_window._hWnd
        else:
            # Lần đầu hoặc chưa có main
            main_window = valid_wins[0]
            main_hwnd = main_window._hWnd
        
        # Cập nhật danh sách cửa sổ phụ
        other_windows = []
        other_hwnds = []
        for w in valid_wins:
            try:
                if w._hWnd != main_hwnd:
                    other_windows.append(w)
                    other_hwnds.append(w._hWnd)
            except:
                pass
    
    return True

# Khởi tạo lần đầu
if not update_window_list():
    print("❌ Cần ít nhất 1 cửa sổ Chrome để chạy!")
    print("   Mở Chrome và chạy lại script.")
    exit()

print("=" * 70)
print(f"✅ Đã tìm thấy {len(other_windows) + 1} cửa sổ Chrome")
print(f"🎯 Cửa sổ chính: '{main_window.title[:50]}...'")
print(f"   HWND: {main_hwnd}")
print(f"📋 {len(other_windows)} cửa sổ phụ sẽ được đồng bộ")
print("=" * 70)
print("🚀 Hệ thống đồng bộ siêu nhanh đang chạy")
print("   ✓ Tự động phát hiện cửa sổ mới mỗi 0.5s")
print("   ✓ Click/Scroll đồng bộ ngay lập tức")
print("   ✓ Con trỏ chuột KHÔNG di chuyển (Win32 API)")
print("   ✓ Độ trễ cực thấp")
print("   • Nhấn ESC để thoát")
print("=" * 70 + "\n")

# === GIÁM SÁT CỬA SỔ (AUTO-DETECT) ===
last_window_count = len(other_windows) + 1

def monitor_windows():
    """Thread giám sát và tự động cập nhật cửa sổ"""
    global last_window_count
    
    while not stop_event.is_set():
        try:
            if update_window_list():
                current_count = len(other_windows) + 1
                
                if current_count != last_window_count:
                    if current_count > last_window_count:
                        diff = current_count - last_window_count
                        print(f"➕ Đã phát hiện {diff} cửa sổ Chrome mới! Tổng: {current_count} cửa sổ")
                    else:
                        diff = last_window_count - current_count
                        print(f"➖ {diff} cửa sổ Chrome đã đóng. Còn lại: {current_count} cửa sổ")
                    
                    last_window_count = current_count
            else:
                if last_window_count > 0:
                    print("⚠️  Tất cả cửa sổ Chrome đã đóng!")
                    last_window_count = 0
        except:
            pass
        
        time.sleep(WINDOW_SCAN_INTERVAL)

# === ĐỒNG BỘ NHANH VỚI WIN32 ===
def sync_click(x, y, button):
    """Đồng bộ click cực nhanh"""
    with syncing_lock:
        with windows_lock:
            if not main_window or not other_hwnds:
                return
            
            main_left = main_window.left
            main_top = main_window.top
            rel_x = x - main_left
            rel_y = y - main_top
        
        # Xác định loại nút
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
        
        # Gửi click đến tất cả cửa sổ phụ
        for hwnd in other_hwnds:
            try:
                if not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
                    continue
                
                # Chuyển tọa độ sang client coordinates
                lparam = win32api.MAKELONG(rel_x & 0xFFFF, rel_y & 0xFFFF)
                
                # Gửi message
                win32gui.PostMessage(hwnd, down_msg, wparam, lparam)
                win32gui.PostMessage(hwnd, up_msg, 0, lparam)
            except:
                pass

def sync_scroll(x, y, dx, dy):
    """Đồng bộ cuộn cực nhanh"""
    with syncing_lock:
        with windows_lock:
            if not main_window or not other_hwnds:
                return
            
            main_left = main_window.left
            main_top = main_window.top
            rel_x = x - main_left
            rel_y = y - main_top
        
        # Tính scroll amount
        scroll_amount = int(120 * dy * SCROLL_SPEED)
        if scroll_amount == 0:
            return
        
        wparam = win32api.MAKELONG(0, scroll_amount & 0xFFFF)
        
        # Gửi scroll đến tất cả cửa sổ phụ
        for hwnd in other_hwnds:
            try:
                if not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
                    continue
                
                # Lấy vị trí cửa sổ phụ
                rect = win32gui.GetWindowRect(hwnd)
                screen_x = rect[0] + rel_x
                screen_y = rect[1] + rel_y
                
                lparam = win32api.MAKELONG(screen_x & 0xFFFF, screen_y & 0xFFFF)
                win32gui.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
            except:
                pass

def is_in_main_window(x, y):
    """Kiểm tra tọa độ có trong cửa sổ chính không"""
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
        # Không dùng thread cho click để giảm độ trễ
        sync_click(x, y, button)

def on_scroll(x, y, dx, dy):
    if is_in_main_window(x, y):
        # Không dùng thread cho scroll để giảm độ trễ
        sync_scroll(x, y, dx, dy)

def on_release(key):
    if key == keyboard.Key.esc:
        print("\n" + "=" * 70)
        print("🛑 Đã nhấn ESC - Đang thoát...")
        print("=" * 70)
        stop_event.set()
        if mouse_listener:
            mouse_listener.stop()
        if key_listener:
            key_listener.stop()
        return False

# === CHẠY CHƯƠNG TRÌNH ===
try:
    # Khởi động thread giám sát cửa sổ
    monitor_thread = threading.Thread(target=monitor_windows, daemon=True)
    monitor_thread.start()
    
    # Khởi động listener
    mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    key_listener = keyboard.Listener(on_release=on_release)
    
    mouse_listener.start()
    key_listener.start()
    
    mouse_listener.join()
    key_listener.join()
    
    print("\n✅ Hệ thống đã dừng an toàn.")

except KeyboardInterrupt:
    print("\n⚠️  Ctrl+C - Đang thoát...")
    stop_event.set()
except Exception as e:
    print(f"\n❌ Lỗi: {e}")
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