import pygetwindow as gw
from pynput import mouse, keyboard
import threading
import win32gui
import win32api
import win32con
import time

# --- CÀI ĐẶT ---
# pip install pygetwindow pynput pywin32

# Biến toàn cục
mouse_listener = None
key_listener = None
syncing_lock = threading.Lock()

try:
    all_windows = gw.getWindowsWithTitle('Chrome')
    windows = [w for w in all_windows if not w.isMinimized and w.width > 0]
    if len(windows) < 2:
        print(" Cần ít nhất 2 cửa sổ Chrome để đồng bộ!")
        print(f"   Hiện tại chỉ có {len(windows)} cửa sổ Chrome.")
        print("   Mở thêm cửa sổ Chrome và chạy lại script.")
        exit()

    main_window = windows[0]
    other_windows = windows[1:]
    
    # Lấy HWND (handle) của các cửa sổ
    main_hwnd = main_window._hWnd
    other_hwnds = [w._hWnd for w in other_windows]

    print("=" * 70)
    print(f" Đã tìm thấy {len(windows)} cửa sổ Chrome")
    print(f" Cửa sổ chính: '{main_window.title[:50]}...'")
    print(f"   HWND: {main_hwnd} | Vị trí: ({main_window.left}, {main_window.top})")
    print(f"\n Danh sách {len(other_windows)} cửa sổ phụ:")
    for i, (w, hwnd) in enumerate(zip(other_windows, other_hwnds), 1):
        print(f"   {i}. HWND: {hwnd} - '{w.title[:45]}...'")
    print("=" * 70)
    print("Hệ thống đồng bộ Win32 API đang chạy")
    print("   • Nhấn ESC để thoát")
    print("=" * 70 + "\n")

except Exception as e:
    print(f" Lỗi khởi tạo: {e}")
    import traceback
    traceback.print_exc()
    exit()

# --- HÀM ĐỒNG BỘ WIN32 ---
def sync_action_win32(action, *args):
    """Đồng bộ sử dụng Win32 API - không di chuyển chuột thật"""
    with syncing_lock:
        try:
            # Lấy vị trí cửa sổ chính (có thể thay đổi khi người dùng di chuyển)
            main_rect = win32gui.GetWindowRect(main_hwnd)
            main_pos = (main_rect[0], main_rect[1])

            for hwnd in other_hwnds:
                # Bỏ qua cửa sổ bị thu nhỏ
                if win32gui.IsIconic(hwnd):
                    continue
                
                # Kiểm tra cửa sổ vẫn tồn tại
                if not win32gui.IsWindow(hwnd):
                    continue

                try:
                    if action == 'click':
                        x, y, button = args
                        # Tính tọa độ tương đối bên trong cửa sổ
                        rel_x = x - main_pos[0]
                        rel_y = y - main_pos[1]
                        
                        # Tạo lParam chứa tọa độ
                        lParam = win32api.MAKELONG(rel_x, rel_y)

                        # Xác định message cho nút chuột
                        if button == mouse.Button.left:
                            down_msg = win32con.WM_LBUTTONDOWN
                            up_msg = win32con.WM_LBUTTONUP
                            wParam = win32con.MK_LBUTTON
                        elif button == mouse.Button.right:
                            down_msg = win32con.WM_RBUTTONDOWN
                            up_msg = win32con.WM_RBUTTONUP
                            wParam = win32con.MK_RBUTTON
                        elif button == mouse.Button.middle:
                            down_msg = win32con.WM_MBUTTONDOWN
                            up_msg = win32con.WM_MBUTTONUP
                            wParam = win32con.MK_MBUTTON
                        else:
                            continue
                        
                        # Gửi message click
                        win32gui.PostMessage(hwnd, down_msg, wParam, lParam)
                        time.sleep(0.001)  # Delay nhỏ giữa down và up
                        win32gui.PostMessage(hwnd, up_msg, 0, lParam)

                    elif action == 'scroll':
                        x, y, dx, dy = args
                        # Tính tọa độ tương đối
                        rel_x = x - main_pos[0]
                        rel_y = y - main_pos[1]
                        
                        # dy > 0: cuộn lên, dy < 0: cuộn xuống
                        scroll_amount = int(120 * dy)  # 120 = một "notch" cuộn
                        
                        # Tạo wParam (scroll amount ở 16 bit cao)
                        wParam = win32api.MAKELONG(0, scroll_amount)
                        
                        # Tạo lParam (tọa độ màn hình, không phải client)
                        other_rect = win32gui.GetWindowRect(hwnd)
                        screen_x = other_rect[0] + rel_x
                        screen_y = other_rect[1] + rel_y
                        lParam = win32api.MAKELONG(screen_x, screen_y)
                        
                        # Gửi message cuộn
                        win32gui.PostMessage(hwnd, win32con.WM_MOUSEWHEEL, wParam, lParam)

                except Exception as e:
                    # Bỏ qua lỗi với cửa sổ cụ thể
                    pass

        except Exception as e:
            # print(f"⚠️  Lỗi đồng bộ: {e}")
            pass

def is_in_main_window(x, y):
    """Kiểm tra xem tọa độ có nằm trong cửa sổ chính không"""
    try:
        return (main_window.left <= x < main_window.left + main_window.width and 
                main_window.top <= y < main_window.top + main_window.height)
    except:
        return False

# --- LẮNG NGHE SỰ KIỆN ---
def on_click(x, y, button, pressed):
    """Xử lý click chuột"""
    if pressed and is_in_main_window(x, y):
        threading.Thread(
            target=sync_action_win32, 
            args=('click', x, y, button), 
            daemon=True
        ).start()

def on_scroll(x, y, dx, dy):
    """Xử lý cuộn chuột"""
    if is_in_main_window(x, y):
        threading.Thread(
            target=sync_action_win32, 
            args=('scroll', x, y, dx, dy), 
            daemon=True
        ).start()

def on_press(key):
    """Xử lý nhấn phím - tắt vì Win32 API không đồng bộ phím tốt"""
    # Để đồng bộ phím, nên dùng pyautogui thay vì Win32 API
    pass

def on_release(key):
    """Xử lý nhả phím"""
    if key == keyboard.Key.esc:
        print("\n" + "=" * 70)
        print("Đã nhấn ESC - Đang thoát chương trình...")
        print("=" * 70)
        if mouse_listener:
            mouse_listener.stop()
        if key_listener:
            key_listener.stop()
        return False

# --- CHẠY CHƯƠNG TRÌNH ---
try:
    mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    key_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    
    mouse_listener.start()
    key_listener.start()
    
    mouse_listener.join()
    key_listener.join()
    
    print("\nHệ thống đã dừng an toàn.")

except KeyboardInterrupt:
    print("\n\nĐã nhận Ctrl+C - Đang thoát...")
    if mouse_listener:
        mouse_listener.stop()
    if key_listener:
        key_listener.stop()
except Exception as e:
    print(f"\n Lỗi: {e}")
    import traceback
    traceback.print_exc()