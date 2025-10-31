import subprocess
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import queue
import sys
import os
import pygetwindow as gw
import ctypes
# Biến toàn cục
process = None
output_queue = queue.Queue()
is_running = False
selected_hwnd = None

def get_chrome_windows():
    """Lấy danh sách tất cả cửa sổ Chrome"""
    all_windows = gw.getWindowsWithTitle('Chrome')
    windows = []
    for w in all_windows:
        try:
            if not w.isMinimized and w.width > 100 and w.height > 100:
                windows.append({
                    'hwnd': w._hWnd,
                    'title': w.title,
                    'pos': (w.left, w.top),
                    'size': (w.width, w.height)
                })
        except:
            pass
    return windows

def open_window_selector():
    """Mở cửa sổ chọn cửa sổ chính"""
    windows = get_chrome_windows()
    
    if len(windows) == 0:
        messagebox.showwarning("Cảnh báo", "Không tìm thấy cửa sổ Chrome nào!\nVui lòng mở Chrome trước.")
        return
    
    # Tạo cửa sổ popup
    selector = tk.Toplevel(root)
    selector.title("Chọn cửa sổ chính")
    selector.geometry("600x400")
    selector.resizable(False, False)
    selector.grab_set()  # Modal window
    
    # Header
    header = tk.Label(
        selector,
        text="🎯 Chọn cửa sổ Chrome làm cửa sổ chính",
        font=("Segoe UI", 12, "bold"),
        bg="#2196F3",
        fg="white",
        pady=15
    )
    header.pack(fill=tk.X)
    
    # Info
    info = tk.Label(
        selector,
        text="Cửa sổ chính sẽ điều khiển tất cả các cửa sổ khác",
        font=("Segoe UI", 9),
        fg="#666"
    )
    info.pack(pady=5)
    
    # Frame cho listbox
    list_frame = tk.Frame(selector)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    # Scrollbar
    scrollbar = tk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Listbox
    listbox = tk.Listbox(
        list_frame,
        font=("Consolas", 9),
        yscrollcommand=scrollbar.set,
        selectmode=tk.SINGLE,
        height=12
    )
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)
    
    # Thêm các cửa sổ vào listbox
    for i, win in enumerate(windows):
        title = win['title'][:60] + "..." if len(win['title']) > 60 else win['title']
        item_text = f"[{i+1}] HWND: {win['hwnd']} | {title}"
        listbox.insert(tk.END, item_text)
    
    # Chọn item đầu tiên mặc định
    listbox.select_set(0)
    
    # Biến lưu lựa chọn
    selected_index = [0]
    
    def on_select(event):
        if listbox.curselection():
            selected_index[0] = listbox.curselection()[0]
    
    listbox.bind('<<ListboxSelect>>', on_select)
    
    # Frame buttons
    btn_frame = tk.Frame(selector)
    btn_frame.pack(fill=tk.X, padx=20, pady=10)
    
    def on_confirm():
        global selected_hwnd
        selected_hwnd = windows[selected_index[0]]['hwnd']
        selected_title = windows[selected_index[0]]['title'][:40]
        
        window_info_label.config(
            text=f"🎯 Đã chọn: {selected_title}... (HWND: {selected_hwnd})",
            foreground="green"
        )
        
        log_text.insert(tk.END, f"\n🎯 Đã chọn cửa sổ chính: {selected_title}...\n")
        log_text.insert(tk.END, f"   HWND: {selected_hwnd}\n\n")
        log_text.see(tk.END)
        
        selector.destroy()
    
    def on_cancel():
        selector.destroy()
    
    confirm_btn = tk.Button(
        btn_frame,
        text="✓ Xác nhận",
        font=("Segoe UI", 10, "bold"),
        bg="#4CAF50",
        fg="white",
        width=15,
        command=on_confirm,
        cursor="hand2"
    )
    confirm_btn.pack(side=tk.LEFT, padx=5)
    
    cancel_btn = tk.Button(
        btn_frame,
        text="✗ Hủy",
        font=("Segoe UI", 10),
        bg="#f44336",
        fg="white",
        width=15,
        command=on_cancel,
        cursor="hand2"
    )
    cancel_btn.pack(side=tk.LEFT, padx=5)
    
    refresh_btn = tk.Button(
        btn_frame,
        text="🔄 Làm mới",
        font=("Segoe UI", 10),
        bg="#FF9800",
        fg="white",
        width=15,
        command=lambda: [selector.destroy(), open_window_selector()],
        cursor="hand2"
    )
    refresh_btn.pack(side=tk.LEFT, padx=5)

def read_output(pipe, queue):
    """Đọc output từ subprocess và đưa vào queue"""
    try:
        for line in iter(pipe.readline, b''):
            if line:
                queue.put(line.decode('utf-8', errors='ignore').strip())
        pipe.close()
    except:
        pass

def update_log():
    """Cập nhật log text từ queue"""
    try:
        while True:
            line = output_queue.get_nowait()
            log_text.insert(tk.END, line + '\n')
            log_text.see(tk.END)
            
            # Cập nhật status dựa trên output
            if "đang chạy" in line.lower():
                status_label.config(text="🟢 Hệ thống đồng bộ đang chạy", foreground="green")
            elif "phát hiện" in line.lower() and "cửa sổ" in line.lower():
                status_label.config(text=f"🟢 {line}", foreground="green")
    except queue.Empty:
        pass
    
    if is_running:
        root.after(100, update_log)

def start_sync():
    """Khởi động đồng bộ"""
    global process, is_running
    
    if process is not None:
        messagebox.showinfo("Thông báo", "Đồng bộ đã đang chạy!")
        return
    
    # Kiểm tra file brower.py
    if not os.path.exists("brower.py"):
        messagebox.showerror("Lỗi", "Không tìm thấy file 'brower.py'!\nVui lòng đặt file trong cùng thư mục.")
        return
    
    # Kiểm tra có cửa sổ Chrome không
    windows = get_chrome_windows()
    if len(windows) == 0:
        messagebox.showwarning("Cảnh báo", "Không tìm thấy cửa sổ Chrome nào!\nVui lòng mở Chrome trước khi bắt đầu.")
        return
    
    try:
        # Xóa log cũ
        log_text.delete(1.0, tk.END)
        
        # Tạo command
        cmd = [sys.executable, "brower.py"]
        if selected_hwnd:
            cmd.append(str(selected_hwnd))
        
        # Khởi động subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=-1
        )
        
        is_running = True
        
        # Khởi động thread đọc output
        threading.Thread(target=read_output, args=(process.stdout, output_queue), daemon=True).start()
        
        # Bắt đầu cập nhật log
        update_log()
        
        status_label.config(text="🟢 Đang khởi động...", foreground="orange")
        start_btn.config(state="disabled")
        stop_btn.config(state="disabled")
        select_window_btn.config(state="disabled")
        
        log_text.insert(tk.END, "✅ Đã khởi động hệ thống đồng bộ...\n")
        if selected_hwnd:
            log_text.insert(tk.END, f"🎯 Sử dụng cửa sổ đã chọn (HWND: {selected_hwnd})\n")
        log_text.insert(tk.END, "⏳ Đang chờ phát hiện cửa sổ Chrome...\n\n")
        
        # Enable stop button sau 1s
        root.after(1000, lambda: stop_btn.config(state="normal"))
        
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể khởi động:\n{str(e)}")
        is_running = False
        start_btn.config(state="normal")
        select_window_btn.config(state="normal")

def stop_sync():
    """Dừng đồng bộ"""
    global process, is_running
    
    if process is None:
        messagebox.showinfo("Thông báo", "Chưa có tiến trình nào đang chạy.")
        return
    
    try:
        process.terminate()
        process.wait(timeout=3)
    except:
        process.kill()
    
    process = None
    is_running = False
    
    status_label.config(text="🛑 Đã dừng đồng bộ", foreground="red")
    start_btn.config(state="normal")
    stop_btn.config(state="disabled")
    select_window_btn.config(state="normal")
    
    log_text.insert(tk.END, "\n🛑 Đã dừng hệ thống đồng bộ.\n")
    log_text.see(tk.END)

def clear_log():
    """Xóa log"""
    log_text.delete(1.0, tk.END)

def on_close():
    """Xử lý khi đóng cửa sổ"""
    if process is not None:
        if messagebox.askyesno("Xác nhận", "Hệ thống đồng bộ đang chạy.\nBạn có muốn dừng và thoát?"):
            stop_sync()
            root.destroy()
    else:
        root.destroy()

# ============== GIAO DIỆN ==============
root = tk.Tk()
root.title("Chrome Sync Tool - Controller")
root.geometry("750x600")
root.resizable(True, True)
myappid = 'ChromeSyncTool.GUI.1.0'  # Tên định danh duy nhất
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
root.iconbitmap("icon.ico")
# Style
style = ttk.Style()
style.theme_use('clam')

# === FRAME TIÊU ĐỀ ===
header_frame = tk.Frame(root, bg="#2196F3", height=80)
header_frame.pack(fill=tk.X)
header_frame.pack_propagate(False)

title_label = tk.Label(
    header_frame,
    text="🖥️ Chrome Sync Controller",
    font=("Segoe UI", 18, "bold"),
    bg="#2196F3",
    fg="white"
)
title_label.pack(pady=10)

subtitle_label = tk.Label(
    header_frame,
    text="Đồng bộ nhiều cửa sổ Chrome cùng lúc",
    font=("Segoe UI", 10),
    bg="#2196F3",
    fg="white"
)
subtitle_label.pack()

# === FRAME CHỌN CỬA SỔ ===
window_select_frame = tk.Frame(root, bg="#f5f5f5")
window_select_frame.pack(fill=tk.X, pady=5, padx=10)

window_info_label = tk.Label(
    window_select_frame,
    text="⚪ Chưa chọn cửa sổ chính (sẽ dùng cửa sổ đầu tiên)",
    font=("Segoe UI", 9),
    bg="#f5f5f5",
    fg="#666"
)
window_info_label.pack(side=tk.LEFT, padx=10, pady=5)

select_window_btn = tk.Button(
    window_select_frame,
    text="🎯 Chọn cửa sổ chính",
    font=("Segoe UI", 9),
    bg="#2196F3",
    fg="white",
    command=open_window_selector,
    cursor="hand2",
    relief=tk.FLAT
)
select_window_btn.pack(side=tk.RIGHT, padx=10, pady=5)

# === FRAME TRẠNG THÁI ===
status_frame = tk.Frame(root, bg="#f5f5f5", height=50)
status_frame.pack(fill=tk.X, pady=5, padx=10)

status_label = tk.Label(
    status_frame,
    text="🔸 Đang chờ bắt đầu...",
    font=("Segoe UI", 11, "bold"),
    bg="#f5f5f5",
    fg="#666"
)
status_label.pack(pady=10)

# === FRAME ĐIỀU KHIỂN ===
control_frame = tk.Frame(root)
control_frame.pack(fill=tk.X, pady=5, padx=10)

start_btn = tk.Button(
    control_frame,
    text="▶ Bắt đầu đồng bộ",
    font=("Segoe UI", 11, "bold"),
    bg="#4CAF50",
    fg="white",
    width=18,
    height=2,
    command=start_sync,
    cursor="hand2",
    relief=tk.FLAT
)
start_btn.pack(side=tk.LEFT, padx=5)

stop_btn = tk.Button(
    control_frame,
    text="⏹ Dừng",
    font=("Segoe UI", 11, "bold"),
    bg="#f44336",
    fg="white",
    width=18,
    height=2,
    command=stop_sync,
    cursor="hand2",
    relief=tk.FLAT,
    state="disabled"
)
stop_btn.pack(side=tk.LEFT, padx=5)

clear_btn = tk.Button(
    control_frame,
    text="🗑️ Xóa log",
    font=("Segoe UI", 11),
    bg="#FF9800",
    fg="white",
    width=12,
    height=2,
    command=clear_log,
    cursor="hand2",
    relief=tk.FLAT
)
clear_btn.pack(side=tk.LEFT, padx=5)

# === FRAME LOG ===
log_frame = tk.LabelFrame(
    root,
    text="📋 Nhật ký hoạt động",
    font=("Segoe UI", 10, "bold"),
    bg="#f5f5f5",
    fg="#333"
)
log_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

log_text = scrolledtext.ScrolledText(
    log_frame,
    font=("Consolas", 9),
    bg="#1e1e1e",
    fg="#d4d4d4",
    insertbackground="white",
    wrap=tk.WORD,
    height=12
)
log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# Log ban đầu
log_text.insert(tk.END, "=" * 70 + "\n")
log_text.insert(tk.END, "Chrome Sync Tool - Hệ thống đồng bộ nhiều cửa sổ Chrome\n")
log_text.insert(tk.END, "=" * 70 + "\n\n")
log_text.insert(tk.END, "📌 Hướng dẫn sử dụng:\n")
log_text.insert(tk.END, "  1. Mở nhiều cửa sổ Chrome (không phải tab)\n")
log_text.insert(tk.END, "  2. Nhấn 'Chọn cửa sổ chính' để chọn cửa sổ điều khiển\n")
log_text.insert(tk.END, "  3. Nhấn 'Bắt đầu đồng bộ'\n")
log_text.insert(tk.END, "  4. Click/Scroll trong cửa sổ chính\n")
log_text.insert(tk.END, "  5. Các cửa sổ khác sẽ tự động đồng bộ\n")
log_text.insert(tk.END, "  6. Nhấn ESC trong cửa sổ chính để dừng\n\n")
log_text.insert(tk.END, "⏳ Sẵn sàng bắt đầu...\n\n")

# === FRAME FOOTER ===
footer_frame = tk.Frame(root, bg="#e0e0e0", height=40)
footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
footer_frame.pack_propagate(False)

exit_btn = tk.Button(
    footer_frame,
    text="❌ Thoát",
    font=("Segoe UI", 10),
    bg="#9E9E9E",
    fg="white",
    width=15,
    command=on_close,
    cursor="hand2",
    relief=tk.FLAT
)
exit_btn.pack(side=tk.RIGHT, padx=10, pady=5)

info_label = tk.Label(
    footer_frame,
    text="💡 Tip: Chọn cửa sổ chính trước khi bắt đầu để kiểm soát chính xác",
    font=("Segoe UI", 9),
    bg="#e0e0e0",
    fg="#666"
)
info_label.pack(side=tk.LEFT, padx=10, pady=5)

# Xử lý đóng cửa sổ
root.protocol("WM_DELETE_WINDOW", on_close)

# Chạy ứng dụng
try:
    root.mainloop()
except KeyboardInterrupt:
    root.destroy()