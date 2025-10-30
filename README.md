🪟 Chrome Window Sync Tool

Một script Python giúp đồng bộ thao tác chuột (click và cuộn) giữa nhiều cửa sổ Google Chrome trên Windows bằng Win32 API.
Khi bạn click hoặc cuộn trong cửa sổ chính, các cửa sổ Chrome khác sẽ tự động thực hiện hành động tương tự.

⚙️ Cài đặt
Yêu cầu hệ thống

Hệ điều hành: Windows 10/11

Python 3.8+

Cài đặt thư viện cần thiết
pip install pygetwindow pynput pywin32

🚀 Cách sử dụng

Mở ít nhất 2 cửa sổ Google Chrome.

Chạy script:

python chrome_sync.py


Script sẽ:

Tự động tìm các cửa sổ Chrome đang mở.

Chọn cửa sổ đầu tiên làm cửa sổ chính.

Đồng bộ thao tác chuột từ cửa sổ chính sang các cửa sổ phụ.

🖱️ Tính năng
Hành động	Mô tả
🖱️ Click	Khi bạn click trong cửa sổ chính, các cửa sổ Chrome khác sẽ nhận cùng tọa độ click (bằng Win32 message).
🧭 Scroll	Khi bạn cuộn chuột trong cửa sổ chính, các cửa sổ phụ cũng sẽ cuộn theo hướng và tốc độ tương ứng.
⌨️ ESC để thoát	Dừng toàn bộ hệ thống lắng nghe và thoát chương trình an toàn.
🧩 Mã nguồn chính

Các phần quan trọng trong script:

sync_action_win32(action, *args): Gửi thông điệp WM_LBUTTONDOWN/UP, WM_MOUSEWHEEL,... đến các cửa sổ Chrome khác.

on_click, on_scroll: Lắng nghe sự kiện chuột bằng pynput.

gw.getWindowsWithTitle('Chrome'): Lấy danh sách các cửa sổ Chrome đang mở.

⚠️ Lưu ý

Chỉ hoạt động trên Windows (vì dùng thư viện win32api, win32gui).

Không hỗ trợ đồng bộ bàn phím (do hạn chế của Win32 API).

Nếu chỉ có 1 cửa sổ Chrome, script sẽ dừng và yêu cầu mở thêm.
