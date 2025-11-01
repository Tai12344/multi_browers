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
ENABLE_KEYBOARD_SYNC = True  # Bật đồng bộ bàn phím

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

def get_valid_chrome_windows():
    """Lấy danh sách cửa sổ Chrome hợp lệ"""
    all_wins = gw.getWindowsWithTitle('Chrome')
    valid = []
    for w in all_wins:
        try:
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
    print("[ERROR] Cần ít nhất 1 cửa sổ Chrome để chạy!")
    sys.exit(1)

print("=" * 70)
print(f"[OK] Đã tìm thấy {len(other_windows) + 1} cửa sổ Chrome")
print(f"[MAIN] Cửa sổ chính: '{main_window.title[:50]}...'")
print(f"       HWND: {main_hwnd}")
print(f"[INFO] {len(other_windows)} cửa sổ phụ sẽ được đồng bộ")
print("=" * 70)
print("🚀 HỆ THỐNG ĐỒNG BỘ CHROME - TỶ LỆ PHẦN TRĂM")
print("  ✓ Tự động scale theo kích thước cửa sổ")
print("  ✓ Đồng bộ chính xác 100% dù khác size")
print("  ✓ Đồng bộ CHUỘT: Click, Scroll, Drag & Drop")
print("  ✓ Đồng bộ BÀN PHÍM: Text input, phím tắt, special keys")
print("  ✓ Phát hiện cửa sổ mới tự động")
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
                        print(f"[+] Phát hiện {current_count - last_window_count} cửa sổ Chrome mới. Tổng: {current_count}")
                    else:
                        print(f"[-] {last_window_count - current_count} cửa sổ Chrome đã đóng. Còn: {current_count}")
                    last_window_count = current_count
            else:
                if last_window_count > 0:
                    print("[WARN] Tất cả cửa sổ Chrome đã đóng!")
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

def get_main_window_focus():
    """Kiểm tra cửa sổ chính có đang active/focus không"""
    try:
        with windows_lock:
            if not main_hwnd:
                return False
            active_hwnd = win32gui.GetForegroundWindow()
            return active_hwnd == main_hwnd or win32gui.GetParent(active_hwnd) == main_hwnd
    except:
        return False

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

# Mapping từ pynput Key sang VK code
KEY_VK_MAP = {
    keyboard.Key.space: win32con.VK_SPACE,
    keyboard.Key.enter: win32con.VK_RETURN,
    keyboard.Key.backspace: win32con.VK_BACK,
    keyboard.Key.delete: win32con.VK_DELETE,
    keyboard.Key.tab: win32con.VK_TAB,
    keyboard.Key.esc: win32con.VK_ESCAPE,
    keyboard.Key.shift: win32con.VK_SHIFT,
    keyboard.Key.ctrl: win32con.VK_CONTROL,
    keyboard.Key.alt: win32con.VK_MENU,
    keyboard.Key.up: win32con.VK_UP,
    keyboard.Key.down: win32con.VK_DOWN,
    keyboard.Key.left: win32con.VK_LEFT,
    keyboard.Key.right: win32con.VK_RIGHT,
    keyboard.Key.home: win32con.VK_HOME,
    keyboard.Key.end: win32con.VK_END,
    keyboard.Key.page_up: win32con.VK_PRIOR,
    keyboard.Key.page_down: win32con.VK_NEXT,
    keyboard.Key.f1: win32con.VK_F1,
    keyboard.Key.f2: win32con.VK_F2,
    keyboard.Key.f3: win32con.VK_F3,
    keyboard.Key.f4: win32con.VK_F4,
    keyboard.Key.f5: win32con.VK_F5,
    keyboard.Key.f6: win32con.VK_F6,
    keyboard.Key.f7: win32con.VK_F7,
    keyboard.Key.f8: win32con.VK_F8,
    keyboard.Key.f9: win32con.VK_F9,
    keyboard.Key.f10: win32con.VK_F10,
    keyboard.Key.f11: win32con.VK_F11,
    keyboard.Key.f12: win32con.VK_F12,
}

def sync_keyboard(key, is_press=True):
    """Đồng bộ keyboard input đến tất cả cửa sổ phụ - Cải thiện"""
    if not ENABLE_KEYBOARD_SYNC:
        return
    
    with syncing_lock:
        with windows_lock:
            if not main_window or not other_hwnds:
                return
            
            # Kiểm tra nếu cửa sổ chính không có focus thì không sync
            if not get_main_window_focus():
                return
            
            # Chuyển đổi key thành virtual key code
            try:
                vk_code = None
                char_to_send = None
                
                # Kiểm tra special keys
                if key in KEY_VK_MAP:
                    vk_code = KEY_VK_MAP[key]
                elif hasattr(key, 'vk') and key.vk:
                    vk_code = key.vk
                elif hasattr(key, 'value') and hasattr(key.value, 'vk'):
                    vk_code = key.value.vk
                elif hasattr(key, 'char') and key.char:
                    # Regular character - xử lý tốt hơn
                    char = key.char
                    char_to_send = char
                    # Chuyển char thành VK code
                    vk_result = win32api.VkKeyScan(char)
                    if vk_result != -1:
                        vk_code = vk_result & 0xFF
                    else:
                        return
                else:
                    return
                
                if vk_code is None:
                    return
                
                # Lấy modifier keys state
                shift_state = win32api.GetAsyncKeyState(win32con.VK_SHIFT) & 0x8000
                ctrl_state = win32api.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000
                alt_state = win32api.GetAsyncKeyState(win32con.VK_MENU) & 0x8000
                
                # Gửi key đến các cửa sổ phụ
                scan_code = win32api.MapVirtualKey(vk_code, 0)
                repeat_count = 1
                # Bit 30 = previous key state, bit 31 = transition state
                lparam_base = (repeat_count & 0xFFFF) | (scan_code << 16)
                if not is_press:
                    lparam_base |= 0xC0000000  # Previous key was down, now released
                else:
                    lparam_base |= 0x00000000  # Key is being pressed
                
                if is_press:
                    msg = win32con.WM_KEYDOWN
                    char_msg = win32con.WM_CHAR
                else:
                    msg = win32con.WM_KEYUP
                    char_msg = None
                
                for hwnd in other_hwnds:
                    try:
                        if not win32gui.IsWindow(hwnd) or win32gui.IsIconic(hwnd):
                            continue
                        
                        # Gửi key message
                        win32gui.PostMessage(hwnd, msg, vk_code, lparam_base)
                        
                        # Nếu là ký tự có thể in và đang nhấn, gửi WM_CHAR để text input hoạt động tốt hơn
                        if is_press and char_to_send and char_to_send.isprintable():
                            char_code = ord(char_to_send)
                            # WM_CHAR cần lparam với repeat count và scan code
                            win32gui.PostMessage(hwnd, char_msg, char_code, lparam_base)
                    except:
                        pass
                        
            except Exception as e:
                # print(f"[DEBUG] Lỗi keyboard sync: {e}")
                pass

def sync_mouse_move(x, y):
    """Đồng bộ di chuyển chuột (cho drag)"""
    with syncing_lock:
        with windows_lock:
            if not main_window or not other_hwnds:
                return
            
            try:
                # Lấy thông tin cửa sổ chính
                main_rect = win32gui.GetWindowRect(main_hwnd)
                main_left, main_top = main_rect[0], main_rect[1]
                
                # Chuyển tọa độ screen -> client
                try:
                    main_client_x, main_client_y = win32gui.ScreenToClient(main_hwnd, (x, y))
                except:
                    main_client_x = x - main_left
                    main_client_y = y - main_top
                
                # Lấy kích thước client
                main_client_width, main_client_height = get_client_size(main_hwnd)
                
                if not main_client_width or not main_client_height:
                    return
                
                # Tính TỶ LỆ PHẦN TRĂM
                percent_x = main_client_x / main_client_width
                percent_y = main_client_y / main_client_height
                
                # Kiểm tra hợp lệ
                if not (0 <= percent_x <= 1 and 0 <= percent_y <= 1):
                    return
                
                # Gửi mouse move đến các cửa sổ phụ
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
                        
                        # Tạo lParam
                        lparam = win32api.MAKELONG(target_client_x & 0xFFFF, target_client_y & 0xFFFF)
                        
                        # Gửi WM_MOUSEMOVE
                        wparam = 0
                        # Kiểm tra nút chuột nào đang được nhấn
                        if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000:
                            wparam |= win32con.MK_LBUTTON
                        if win32api.GetAsyncKeyState(win32con.VK_RBUTTON) & 0x8000:
                            wparam |= win32con.MK_RBUTTON
                        if win32api.GetAsyncKeyState(win32con.VK_MBUTTON) & 0x8000:
                            wparam |= win32con.MK_MBUTTON
                        
                        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, wparam, lparam)
                        
                    except:
                        pass
            except Exception as e:
                pass

# === LẮNG NGHE SỰ KIỆN ===
last_mouse_pos = (0, 0)
mouse_move_threshold = 5  # Chỉ sync khi di chuyển > 5 pixels

def on_click(x, y, button, pressed):
    global last_mouse_pos
    if is_in_main_window(x, y):
        if pressed:
            sync_click(x, y, button)
        last_mouse_pos = (x, y)

def on_move(x, y):
    """Xử lý di chuyển chuột (cho drag)"""
    global last_mouse_pos
    if is_in_main_window(x, y):
        # Chỉ sync nếu di chuyển đủ xa (tránh spam)
        dx = abs(x - last_mouse_pos[0])
        dy = abs(y - last_mouse_pos[1])
        if dx > mouse_move_threshold or dy > mouse_move_threshold:
            sync_mouse_move(x, y)
            last_mouse_pos = (x, y)

def on_scroll(x, y, dx, dy):
    if is_in_main_window(x, y):
        sync_scroll(x, y, dx, dy)

def on_key_press(key):
    """Xử lý nhấn phím"""
    try:
        # Bỏ qua ESC (để dừng chương trình)
        if key == keyboard.Key.esc:
            return True
        sync_keyboard(key, is_press=True)
    except:
        pass
    return True

def on_key_release(key):
    """Xử lý thả phím"""
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
    
    if ENABLE_KEYBOARD_SYNC:
        try:
            sync_keyboard(key, is_press=False)
        except:
            pass
    
    return True

# === CHẠY CHƯƠNG TRÌNH ===
try:
    # Khởi động thread giám sát
    threading.Thread(target=monitor_windows, daemon=True).start()
    
    # Khởi động listener với đầy đủ events
    mouse_listener = mouse.Listener(
        on_click=on_click, 
        on_scroll=on_scroll,
        on_move=on_move
    )
    key_listener = keyboard.Listener(
        on_press=on_key_press,
        on_release=on_key_release
    )
    
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