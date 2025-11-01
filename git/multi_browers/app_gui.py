# -*- coding: utf-8 -*-
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import queue
import sys
import os
import pygetwindow as gw
import ctypes

# === BIẾN TOÀN CỤC ===
process = None
output_queue = queue.Queue()
is_running = False
selected_hwnd = None

# === BẢNG MÀU HIỆN ĐẠI ===
COLORS = {
    'primary': '#667eea',
    'primary_dark': '#5568d3',
    'success': '#48bb78',
    'success_hover': '#38a169',
    'danger': '#f56565',
    'danger_hover': '#e53e3e',
    'warning': '#ed8936',
    'warning_hover': '#dd6b20',
    'info': '#4299e1',
    'dark': '#2d3748',
    'light': '#edf2f7',
    'card_bg': '#ffffff',
    'text': '#2d3748',
    'text_light': '#718096'
}

# === CLASS NÚT HIỆN ĐẠI ===
class ModernButton(tk.Button):
    def __init__(self, parent, text, icon, bg, hover_bg, **kwargs):
        super().__init__(
            parent,
            text=f"{icon}  {text}",
            font=("Segoe UI", 10, "bold"),
            bg=bg,
            fg="white",
            activebackground=hover_bg,
            activeforeground="white",
            cursor="hand2",
            relief=tk.FLAT,
            bd=0,
            padx=20,
            pady=12,
            **kwargs
        )
        self.default_bg = bg
        self.hover_bg = hover_bg
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
    
    def _on_enter(self, e):
        if self['state'] != 'disabled':
            self['background'] = self.hover_bg
    
    def _on_leave(self, e):
        if self['state'] != 'disabled':
            self['background'] = self.default_bg

# === HÀM CHÍNH ===
def get_chrome_windows():
    """Lấy danh sách cửa sổ Chrome"""
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
    
    if not windows:
        messagebox.showwarning("Cảnh báo", "Không tìm thấy cửa sổ Chrome nào!\nVui lòng mở Chrome trước.")
        return
    
    # Popup
    selector = tk.Toplevel(root)
    selector.title("Chọn cửa sổ chính")
    selector.geometry("750x550")
    selector.resizable(False, False)
    selector.grab_set()
    selector.configure(bg=COLORS['light'])
    
    # Header
    header = tk.Frame(selector, bg=COLORS['primary'], height=100)
    header.pack(fill=tk.X)
    header.pack_propagate(False)
    
    tk.Label(
        header,
        text="🎯 Chọn cửa sổ Chrome làm cửa sổ chính",
        font=("Segoe UI", 16, "bold"),
        bg=COLORS['primary'],
        fg="white"
    ).pack(pady=15)
    
    tk.Label(
        header,
        text="Cửa sổ được chọn sẽ điều khiển tất cả các cửa sổ Chrome khác",
        font=("Segoe UI", 10),
        bg=COLORS['primary'],
        fg="white"
    ).pack()
    
    # Content
    content = tk.Frame(selector, bg=COLORS['light'])
    content.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)
    
    tk.Label(
        content,
        text=f"📊 Tìm thấy {len(windows)} cửa sổ Chrome",
        font=("Segoe UI", 11, "bold"),
        bg=COLORS['light'],
        fg=COLORS['text']
    ).pack(anchor=tk.W, pady=(0, 10))
    
    # List container
    list_container = tk.Frame(content, bg=COLORS['card_bg'])
    list_container.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
    
    scrollbar = tk.Scrollbar(list_container)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=3, pady=3)
    
    listbox = tk.Listbox(
        list_container,
        font=("Consolas", 9),
        yscrollcommand=scrollbar.set,
        selectmode=tk.SINGLE,
        height=14,
        bg=COLORS['card_bg'],
        fg=COLORS['text'],
        selectbackground=COLORS['primary'],
        selectforeground="white",
        bd=0,
        highlightthickness=0
    )
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)
    scrollbar.config(command=listbox.yview)
    
    for i, win in enumerate(windows):
        title = win['title'][:60] + "..." if len(win['title']) > 60 else win['title']
        listbox.insert(tk.END, f"  [{i+1}]  HWND: {win['hwnd']}  •  {title}")
    
    listbox.select_set(0)
    listbox.activate(0)
    
    selected_idx = [0]
    
    def on_select(e):
        if listbox.curselection():
            selected_idx[0] = listbox.curselection()[0]
    
    def on_confirm():
        global selected_hwnd
        selected_win = windows[selected_idx[0]]
        selected_hwnd = selected_win['hwnd']
        title = selected_win['title'][:45]
        
        window_info_label.config(
            text=f"✓  {title}... (HWND: {selected_hwnd})",
            foreground=COLORS['success']
        )
        
        log_text.insert(tk.END, f"\n🎯 Đã chọn cửa sổ chính: {title}...\n")
        log_text.insert(tk.END, f"   HWND: {selected_hwnd}\n\n")
        log_text.see(tk.END)
        
        selector.destroy()
    
    def on_refresh():
        selector.destroy()
        root.after(100, open_window_selector)
    
    listbox.bind('<<ListboxSelect>>', on_select)
    listbox.bind('<Double-Button-1>', lambda e: on_confirm())
    
    # Buttons
    btn_frame = tk.Frame(content, bg=COLORS['light'])
    btn_frame.pack(fill=tk.X)
    
    ModernButton(
        btn_frame, "Xác nhận", "✓",
        COLORS['success'], COLORS['success_hover'],
        command=on_confirm, width=20
    ).pack(side=tk.LEFT, padx=5)
    
    ModernButton(
        btn_frame, "Làm mới", "🔄",
        COLORS['warning'], COLORS['warning_hover'],
        command=on_refresh, width=20
    ).pack(side=tk.LEFT, padx=5)
    
    ModernButton(
        btn_frame, "Hủy", "✗",
        COLORS['danger'], COLORS['danger_hover'],
        command=selector.destroy, width=20
    ).pack(side=tk.LEFT, padx=5)

def read_output(pipe, queue):
    """Đọc output từ subprocess"""
    try:
        for line in iter(pipe.readline, ''):
            if line:
                queue.put(line.strip())
        pipe.close()
    except:
        pass

def update_log():
    """Cập nhật log"""
    try:
        while True:
            line = output_queue.get_nowait()
            log_text.insert(tk.END, line + '\n')
            log_text.see(tk.END)
            
            if "sẵn sàng" in line.lower() or "đang chạy" in line.lower():
                status_label.config(
                    text="●  Đang chạy",
                    foreground=COLORS['success']
                )
            elif "phát hiện" in line.lower():
                windows_count_label.config(text=line[:60])
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
    
    if not os.path.exists("brower.py"):
        messagebox.showerror("Lỗi", "Không tìm thấy file 'brower.py'!")
        return
    
    windows = get_chrome_windows()
    if not windows:
        messagebox.showwarning("Cảnh báo", "Không tìm thấy cửa sổ Chrome!")
        return
    
    try:
        log_text.delete(1.0, tk.END)
        
        cmd = [sys.executable, "brower.py"]
        if selected_hwnd:
            cmd.append(str(selected_hwnd))
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        is_running = True
        
        threading.Thread(target=read_output, args=(process.stdout, output_queue), daemon=True).start()
        update_log()
        
        status_label.config(
            text="●  Đang khởi động...",
            foreground=COLORS['warning']
        )
        start_btn.config(state="disabled", bg="#cbd5e0")
        stop_btn.config(state="normal", bg=COLORS['danger'])
        select_window_btn.config(state="disabled")
        
        log_text.insert(tk.END, "✅ Đã khởi động hệ thống đồng bộ...\n")
        if selected_hwnd:
            log_text.insert(tk.END, f"🎯 Sử dụng HWND: {selected_hwnd}\n\n")
        
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không thể khởi động:\n{e}")
        is_running = False
        start_btn.config(state="normal", bg=COLORS['success'])

def stop_sync():
    """Dừng đồng bộ"""
    global process, is_running
    
    if process is None:
        return
    
    try:
        process.terminate()
        process.wait(timeout=3)
    except:
        process.kill()
    
    process = None
    is_running = False
    
    status_label.config(text="●  Đã dừng", foreground=COLORS['danger'])
    start_btn.config(state="normal", bg=COLORS['success'])
    stop_btn.config(state="disabled", bg="#cbd5e0")
    select_window_btn.config(state="normal")
    
    log_text.insert(tk.END, "\n🛑 Đã dừng hệ thống.\n")
    log_text.see(tk.END)

def clear_log():
    log_text.delete(1.0, tk.END)

def on_close():
    if process is not None:
        if messagebox.askyesno("Xác nhận", "Đồng bộ đang chạy. Dừng và thoát?"):
            stop_sync()
            root.destroy()
    else:
        root.destroy()

# === GIAO DIỆN CHÍNH ===
root = tk.Tk()
root.title("Chrome Sync Controller")
root.geometry("900x700")
root.configure(bg=COLORS['light'])

try:
    myappid = 'ChromeSyncTool.GUI.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    root.iconbitmap("icon.ico")
except:
    pass

# === HEADER ===
header = tk.Frame(root, bg=COLORS['primary'], height=130)
header.pack(fill=tk.X)
header.pack_propagate(False)

tk.Label(
    header,
    text="🖥️",
    font=("Segoe UI", 45),
    bg=COLORS['primary'],
    fg="white"
).pack(pady=(20, 5))

tk.Label(
    header,
    text="Chrome Sync Controller",
    font=("Segoe UI", 22, "bold"),
    bg=COLORS['primary'],
    fg="white"
).pack()

tk.Label(
    header,
    text="Đồng bộ nhiều cửa sổ Chrome - Chuột, Bàn phím, Text - Chính xác 100%",
    font=("Segoe UI", 10),
    bg=COLORS['primary'],
    fg="white"
).pack(pady=(0, 15))

# === MAIN CONTENT ===
content = tk.Frame(root, bg=COLORS['light'])
content.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)

# CARD 1: Cửa sổ
window_card = tk.Frame(content, bg=COLORS['card_bg'])
window_card.pack(fill=tk.X, pady=(0, 15))

card_header = tk.Frame(window_card, bg=COLORS['card_bg'])
card_header.pack(fill=tk.X, padx=20, pady=(15, 10))

tk.Label(
    card_header,
    text="🎯 Cửa sổ điều khiển Chrome",
    font=("Segoe UI", 12, "bold"),
    bg=COLORS['card_bg'],
    fg=COLORS['text']
).pack(side=tk.LEFT)

window_info_label = tk.Label(
    card_header,
    text="○  Chưa chọn (mặc định: cửa sổ đầu tiên)",
    font=("Segoe UI", 9),
    bg=COLORS['card_bg'],
    fg=COLORS['text_light']
)
window_info_label.pack(side=tk.LEFT, padx=15)

select_window_btn = ModernButton(
    card_header,
    "Chọn cửa sổ",
    "⚙",
    COLORS['info'],
    COLORS['primary_dark'],
    command=open_window_selector
)
select_window_btn.pack(side=tk.RIGHT)

# CARD 2: Trạng thái
status_card = tk.Frame(content, bg=COLORS['card_bg'])
status_card.pack(fill=tk.X, pady=(0, 15))

status_header = tk.Frame(status_card, bg=COLORS['card_bg'])
status_header.pack(fill=tk.X, padx=20, pady=15)

tk.Label(
    status_header,
    text="📊 Trạng thái hệ thống",
    font=("Segoe UI", 12, "bold"),
    bg=COLORS['card_bg'],
    fg=COLORS['text']
).pack(side=tk.LEFT)

status_label = tk.Label(
    status_header,
    text="●  Đang chờ bắt đầu",
    font=("Segoe UI", 10, "bold"),
    bg=COLORS['card_bg'],
    fg=COLORS['text_light']
)
status_label.pack(side=tk.LEFT, padx=15)

windows_count_label = tk.Label(
    status_header,
    text="",
    font=("Segoe UI", 9),
    bg=COLORS['card_bg'],
    fg=COLORS['text_light']
)
windows_count_label.pack(side=tk.LEFT)

# CONTROL BUTTONS
btn_frame = tk.Frame(content, bg=COLORS['light'])
btn_frame.pack(fill=tk.X, pady=(0, 15))

start_btn = ModernButton(
    btn_frame,
    "Bắt đầu đồng bộ",
    "▶",
    COLORS['success'],
    COLORS['success_hover'],
    command=start_sync,
    width=22
)
start_btn.pack(side=tk.LEFT, padx=(0, 10))

stop_btn = ModernButton(
    btn_frame,
    "Dừng",
    "⏹",
    "#cbd5e0",
    COLORS['danger_hover'],
    command=stop_sync,
    width=22,
    state="disabled"
)
stop_btn.pack(side=tk.LEFT, padx=(0, 10))

clear_btn = ModernButton(
    btn_frame,
    "Xóa log",
    "🗑",
    COLORS['warning'],
    COLORS['warning_hover'],
    command=clear_log,
    width=15
)
clear_btn.pack(side=tk.LEFT)

# CARD 3: Log
log_card = tk.Frame(content, bg=COLORS['card_bg'])
log_card.pack(fill=tk.BOTH, expand=True)

log_header = tk.Frame(log_card, bg=COLORS['card_bg'])
log_header.pack(fill=tk.X, padx=20, pady=(15, 5))

tk.Label(
    log_header,
    text="📋 Nhật ký hoạt động",
    font=("Segoe UI", 12, "bold"),
    bg=COLORS['card_bg'],
    fg=COLORS['text']
).pack(side=tk.LEFT)

log_text = scrolledtext.ScrolledText(
    log_card,
    font=("Consolas", 9),
    bg="#1e1e1e",
    fg="#d4d4d4",
    insertbackground="white",
    wrap=tk.WORD,
    bd=0,
    padx=15,
    pady=15
)
log_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

# Log ban đầu
log_text.insert(tk.END, "╔" + "═" * 78 + "╗\n")
log_text.insert(tk.END, "║" + " " * 20 + "Chrome Sync Tool - Sẵn sàng" + " " * 30 + "║\n")
log_text.insert(tk.END, "╚" + "═" * 78 + "╝\n\n")
log_text.insert(tk.END, "📌 HƯỚNG DẪN:\n\n")
log_text.insert(tk.END, "  1️⃣  Mở nhiều cửa sổ Chrome (Ctrl+N)\n")
log_text.insert(tk.END, "  2️⃣  Nhấn 'Chọn cửa sổ' để chọn cửa sổ điều khiển\n")
log_text.insert(tk.END, "  3️⃣  Nhấn 'Bắt đầu đồng bộ'\n")
log_text.insert(tk.END, "  4️⃣  Click/Scroll/Drag trong cửa sổ chính → Tất cả đồng bộ\n")
log_text.insert(tk.END, "  5️⃣  Gõ text/nhấn phím trong cửa sổ chính → Tất cả đồng bộ\n")
log_text.insert(tk.END, "  6️⃣  Nhấn ESC để dừng\n\n")
log_text.insert(tk.END, "⚡ Đồng bộ với TỶ LỆ PHẦN TRĂM - Chính xác 100%!\n")
log_text.insert(tk.END, "🖱️  Đồng bộ CHUỘT: Click, Scroll, Drag & Drop\n")
log_text.insert(tk.END, "⌨️  Đồng bộ BÀN PHÍM: Text input, phím tắt, special keys\n")
log_text.insert(tk.END, "━" * 80 + "\n\n")
log_text.insert(tk.END, "⏳ Chờ bắt đầu...\n")

# === FOOTER ===
footer = tk.Frame(root, bg=COLORS['dark'], height=55)
footer.pack(fill=tk.X, side=tk.BOTTOM)
footer.pack_propagate(False)

tk.Label(
    footer,
    text="💡 Chrome Sync - Đồng bộ Chuột, Bàn phím, Text bằng tỷ lệ % - Hoạt động với mọi kích thước",
    font=("Segoe UI", 9),
    bg=COLORS['dark'],
    fg="white"
).pack(side=tk.LEFT, padx=25, pady=15)

ModernButton(
    footer,
    "Thoát",
    "✕",
    COLORS['danger'],
    COLORS['danger_hover'],
    command=on_close,
    width=12
).pack(side=tk.RIGHT, padx=20, pady=10)

root.protocol("WM_DELETE_WINDOW", on_close)

try:
    root.mainloop()
except KeyboardInterrupt:
    root.destroy()