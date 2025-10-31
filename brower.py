import pygetwindow as gw
import pyautogui
from pynput import mouse, keyboard
import threading
import time
import win32api
import win32con
import win32gui

# --- CÀI ĐẶT ---
# pip install pygetwindow pyautogui pynput

# Cấu hình
SCROLL_MULTIPLIER = 120  # Độ mượt của cuộn
SYNC_DELAY = 0.001  # Delay cực nhỏ để chuột trả về nhanh hơn
ENABLE_KEYBOARD_SYNC = True  # Bật/tắt đồng bộ bàn phím
# Thiết lập PyAutoGUI để tránh dừng khẩn cấp và tăng tốc độ
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# --- TIỆN ÍCH WIN32: GỬI SỰ KIỆN CHUỘT KHÔNG DI CHUYỂN CON TRỎ ---
def _to_client(hwnd, x_screen, y_screen):
    try:
        return win32gui.ScreenToClient(hwnd, (int(x_screen), int(y_screen)))
    except Exception:
        # Fallback: 0,0 if chuyển đổi lỗi
        return (0, 0)

def _make_lparam(x, y):
    return win32api.MAKELONG(int(x) & 0xFFFF, int(y) & 0xFFFF)

def _send_mouse_click(hwnd, x_screen, y_screen, button):
    if not hwnd:
        return
    cx, cy = _to_client(hwnd, x_screen, y_screen)
    lparam = _make_lparam(cx, cy)
    btn = str(button).split('.')[-1].lower()
    if btn == 'left':
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    elif btn == 'right':
        win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lparam)
        win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, lparam)
    elif btn == 'middle':
        win32api.PostMessage(hwnd, win32con.WM_MBUTTONDOWN, win32con.MK_MBUTTON, lparam)
        win32api.PostMessage(hwnd, win32con.WM_MBUTTONUP, 0, lparam)

def _send_mouse_wheel(hwnd, x_screen, y_screen, delta_y):
    if not hwnd or not delta_y:
        return
    cx, cy = _to_client(hwnd, x_screen, y_screen)
    lparam = _make_lparam(cx, cy)
    wparam = win32api.MAKELONG(0, int(delta_y) * win32con.WHEEL_DELTA)
    win32api.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)

# Biến toàn cục
syncing_lock = threading.Lock()
windows_lock = threading.Lock()
stop_event = threading.Event()
mouse_listener = None
key_listener = None
window_monitor_thread = None

try:
    # Lấy danh sách các cửa sổ Chrome
    all_windows = gw.getWindowsWithTitle('Chrome')
    
    # Lọc các cửa sổ hợp lệ (không bị thu nhỏ, có kích thước > 0)
    windows = []
    for w in all_windows:
        try:
            if not w.isMinimized and w.width > 0 and w.height > 0:
                windows.append(w)
        except:
            continue

    if len(windows) < 2:
        print("❌ Cần ít nhất 2 cửa sổ Chrome để đồng bộ!")
        print("Mở thêm cửa sổ Chrome và chạy lại script.")
        print(f"\nHiện tại tìm thấy {len(windows)} cửa sổ Chrome.")
        exit()

    main_window = windows[0]
    other_windows = windows[1:]

    print("=" * 60)
    print(f"✅ Đã tìm thấy {len(windows)} cửa sổ Chrome")
    print(f"🎯 Cửa sổ chính: '{main_window.title[:50]}...'")
    print(f"   Vị trí: ({main_window.left}, {main_window.top})")
    print(f"   Kích thước: {main_window.width}x{main_window.height}")
    print(f"\n📋 Danh sách {len(other_windows)} cửa sổ phụ:")
    for i, w in enumerate(other_windows, 1):
        print(f"   {i}. '{w.title[:40]}...' - ({w.left}, {w.top})")
    print("=" * 60)
    print("🟢 Hệ thống đồng bộ đang chạy")
    print("   • Click/Scroll trong cửa sổ chính để đồng bộ")
    if ENABLE_KEYBOARD_SYNC:
        print("   • Gõ phím trong cửa sổ chính để đồng bộ")
    print("   • Nhấn ESC để thoát")
    print("=" * 60 + "\n")

except Exception as e:
    print(f"❌ Lỗi khởi tạo: {e}")
    import traceback
    traceback.print_exc()
    exit()

# --- GIÁM SÁT CỬA SỔ: TỰ ĐỘNG CẬP NHẬT DANH SÁCH ---
def _monitor_windows():
    global main_window, other_windows
    last_handles = set()
    while not stop_event.is_set():
        try:
            all_windows = gw.getWindowsWithTitle('Chrome')
            valid = []
            for w in all_windows:
                try:
                    if not w.isMinimized and w.width > 0 and w.height > 0:
                        valid.append(w)
                except Exception:
                    continue

            with windows_lock:
                # Giữ nguyên cửa sổ chính nếu còn tồn tại
                current_main = main_window
                current_main_handle = getattr(current_main, '_hWnd', None) if current_main else None

                # Bản đồ handle -> window
                handle_to_win = {getattr(w, '_hWnd', None): w for w in valid}

                if current_main_handle in handle_to_win:
                    new_main = handle_to_win[current_main_handle]
                else:
                    # Chọn main mới nếu main cũ không còn
                    new_main = valid[0] if valid else None

                if new_main:
                    new_others = [w for w in valid if getattr(w, '_hWnd', None) != getattr(new_main, '_hWnd', None)]
                else:
                    new_others = []

                main_window = new_main
                other_windows = new_others

                current_handles = set(handle_to_win.keys())

            # Thông báo khi có thay đổi số lượng cửa sổ
            if current_handles != last_handles:
                added = current_handles - last_handles
                removed = last_handles - current_handles
                if added:
                    print(f"➕ Đã phát hiện {len(added)} cửa sổ Chrome mới. Đồng bộ đã cập nhật.")
                if removed:
                    print(f"➖ {len(removed)} cửa sổ Chrome đã đóng hoặc không hợp lệ. Đã loại khỏi đồng bộ.")
                last_handles = current_handles
        except Exception:
            pass
        time.sleep(1.0)

# --- HÀM ĐỒNG BỘ ---
def sync_action(action, *args):
    """Thực hiện đồng bộ hành động sang các cửa sổ phụ"""
    with syncing_lock:
        try:
            # Lấy snapshot cửa sổ hiện tại để thao tác an toàn
            with windows_lock:
                current_main = main_window
                current_others = list(other_windows)
            if not current_main:
                return
            main_pos = (current_main.left, current_main.top)
            # Lưu vị trí chuột ban đầu (không di chuyển chuột khi đồng bộ)
            original_mouse_pos = pyautogui.position()
            
            for w in current_others:
                # Bỏ qua cửa sổ bị thu nhỏ hoặc không hợp lệ
                try:
                    if w.isMinimized or w.width <= 0 or w.height <= 0:
                        continue
                except:
                    continue
                
                try:
                    if action == 'click':
                        x, y, button = args
                        # Tính toán vị trí tương đối
                        target_x = w.left + (x - main_pos[0])
                        target_y = w.top + (y - main_pos[1])
                        
                        # Kiểm tra xem vị trí có nằm trong cửa sổ phụ không
                        if (w.left <= target_x < w.left + w.width and 
                            w.top <= target_y < w.top + w.height):
                            # Gửi click trực tiếp qua Win32, không di chuyển chuột
                            hwnd = getattr(w, '_hWnd', None)
                            _send_mouse_click(hwnd, target_x, target_y, button)
                            time.sleep(SYNC_DELAY)

                    elif action == 'scroll':
                        x, y, dx, dy = args
                        # Tính vị trí tương đối để cuộn
                        target_x = w.left + (x - main_pos[0])
                        target_y = w.top + (y - main_pos[1])
                        
                        # Đảm bảo vị trí cuộn nằm trong cửa sổ
                        if (w.left <= target_x < w.left + w.width and 
                            w.top <= target_y < w.top + w.height):
                            # Gửi wheel qua Win32, không di chuyển chuột
                            hwnd = getattr(w, '_hWnd', None)
                            # Quy đổi dy sang số nấc bánh xe: mỗi nấc là WHEEL_DELTA (120)
                            steps = int(dy)
                            if steps != 0:
                                _send_mouse_wheel(hwnd, target_x, target_y, steps)
                            time.sleep(SYNC_DELAY)

                    elif action == 'key':
                        key_value = args[0]
                        # Kích hoạt cửa sổ phụ
                        w.activate()
                        time.sleep(0.05)
                        pyautogui.press(key_value)
                        # Trả chuột về vị trí ban đầu và kích hoạt lại cửa sổ chính
                        pyautogui.moveTo(original_mouse_pos[0], original_mouse_pos[1], duration=0)
                        with windows_lock:
                            cm = main_window
                        if cm:
                            cm.activate()
                        time.sleep(SYNC_DELAY)
                
                except Exception as e:
                    # Không di chuyển chuột thực trong trường hợp lỗi
                    print(f"⚠️  Lỗi đồng bộ với cửa sổ '{w.title[:30]}': {e}")
                
        except Exception as e:
            print(f"⚠️  Lỗi đồng bộ: {e}")

def is_in_main_window(x, y):
    """Kiểm tra xem tọa độ có nằm trong cửa sổ chính không"""
    try:
        with windows_lock:
            mw = main_window
        if not mw:
            return False
        return (mw.left <= x < mw.left + mw.width and 
                mw.top <= y < mw.top + mw.height)
    except:
        return False

# --- LẮNG NGHE SỰ KIỆN ---
def on_click(x, y, button, pressed):
    """Xử lý sự kiện click chuột"""
    if pressed and is_in_main_window(x, y):
        threading.Thread(
            target=sync_action, 
            args=('click', x, y, button),
            daemon=True
        ).start()

def on_scroll(x, y, dx, dy):
    """Xử lý sự kiện cuộn chuột"""
    if is_in_main_window(x, y):
        threading.Thread(
            target=sync_action, 
            args=('scroll', x, y, dx, dy),
            daemon=True
        ).start()

def on_press(key):
    """Xử lý sự kiện nhấn phím"""
    if not ENABLE_KEYBOARD_SYNC:
        return
    
    # Kiểm tra xem cửa sổ chính có đang active không
    try:
        active_window = gw.getActiveWindow()
        # So sánh theo handle để chính xác hơn thay vì so sánh object
        active_handle = getattr(active_window, '_hWnd', None)
        with windows_lock:
            mw = main_window
        main_handle = getattr(mw, '_hWnd', None)
        if not active_window or (active_handle is not None and main_handle is not None and active_handle != main_handle):
            return
    except:
        return
    
    try:
        # Phím ký tự (a, b, c, 1, 2, 3, ...)
        key_value = key.char
        threading.Thread(
            target=sync_action, 
            args=('key', key_value),
            daemon=True
        ).start()
    except AttributeError:
        # Phím đặc biệt (enter, space, backspace, ...)
        special_keys = {
            keyboard.Key.enter: 'enter',
            keyboard.Key.space: 'space',
            keyboard.Key.backspace: 'backspace',
            keyboard.Key.delete: 'delete',
            keyboard.Key.tab: 'tab',
            keyboard.Key.up: 'up',
            keyboard.Key.down: 'down',
            keyboard.Key.left: 'left',
            keyboard.Key.right: 'right',
            keyboard.Key.home: 'home',
            keyboard.Key.end: 'end',
            keyboard.Key.page_up: 'pageup',
            keyboard.Key.page_down: 'pagedown'
        }
        
        if key in special_keys:
            threading.Thread(
                target=sync_action, 
                args=('key', special_keys[key]),
                daemon=True
            ).start()

def on_release(key):
    """Xử lý sự kiện nhả phím"""
    if key == keyboard.Key.esc:
        print("\n" + "=" * 60)
        print("🛑 Đã nhấn ESC - Đang thoát chương trình...")
        print("=" * 60)
        if mouse_listener:
            mouse_listener.stop()
        if key_listener:
            key_listener.stop()
        return False

# --- CHẠY CHƯƠNG TRÌNH ---
try:
    mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    key_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    window_monitor_thread = threading.Thread(target=_monitor_windows, daemon=True)

    mouse_listener.start()
    key_listener.start()
    window_monitor_thread.start()

    mouse_listener.join()
    key_listener.join()

    print("\n✅ Hệ thống đã dừng an toàn.")

except KeyboardInterrupt:
    print("\n\n⚠️  Đã nhận Ctrl+C - Đang thoát...")
    if mouse_listener:
        mouse_listener.stop()
    if key_listener:
        key_listener.stop()
    stop_event.set()
    if window_monitor_thread:
        try:
            window_monitor_thread.join(timeout=1.0)
        except Exception:
            pass
except Exception as e:
    print(f"\n❌ Lỗi: {e}")
    import traceback
    traceback.print_exc()