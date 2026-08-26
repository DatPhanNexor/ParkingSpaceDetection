"""
Legacy desktop dashboard. Management dashboard is now provided by Streamlit.
"""
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import sys
from pathlib import Path

_APP_MODULE_DIR = Path(__file__).resolve().parent
if str(_APP_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_MODULE_DIR))

from database_manager import DatabaseManager, DatabaseError
from auth_ui import AuthSession
from typing import Callable
import threading

class ManagementDashboard(ctk.CTk):
    def __init__(self, db_manager: DatabaseManager, session: AuthSession, on_action: Callable[[str], None]):
        super().__init__()
        self.db_manager = db_manager
        self.session = session
        self.on_action = on_action
        
        self.title("Quản lý Bãi Đỗ Xe Thông Minh")
        self.geometry("1400x850")
        self.minsize(1100, 700)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.colors = {
            "bg": "#091421",
            "panel": "#0f1d30",
            "card": "#14243a",
            "text": "#f8fbff",
            "muted": "#bdcbe0",
            "accent": "#2f8ee8",
            "accent_hover": "#1e72c4",
            "green": "#38d69f",
            "red": "#ff5d7a"
        }
        self.configure(fg_color=self.colors["bg"])
        
        self.filter_var = ctk.StringVar(value="Hôm nay")
        self.search_var = ctk.StringVar(value="")
        
        # Load refresh interval from DB config
        config = self.db_manager.fetch_billing_config()
        self.refresh_interval_ms = config.get('refresh_dashboard_ms', 3000)
        self.refresh_job = None
        self._is_closing = False
        
        self._build_ui()
        self._schedule_refresh()
        
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._build_header()
        
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(2, weight=1)
        
        self._build_cards()
        self._build_charts()
        self._build_table()
        
    def _build_header(self):
        header_frame = ctk.CTkFrame(self, fg_color=self.colors["panel"], height=70, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)
        
        title_label = ctk.CTkLabel(
            header_frame, 
            text="QUẢN LÝ BÃI ĐỖ XE THÔNG MINH\n", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="w")
        
        subtitle_label = ctk.CTkLabel(
            header_frame, 
            text="Dữ liệu cập nhật theo thời gian thực từ hệ thống AI", 
            font=ctk.CTkFont(size=12), text_color=self.colors["muted"]
        )
        subtitle_label.place(x=20, y=40)
        
        right_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_frame.grid(row=0, column=2, padx=20, pady=15, sticky="e")
        
        user_info = ctk.CTkLabel(right_frame, text=f"Xin chào, {self.session.ho_ten} ({self.session.role})", font=ctk.CTkFont(size=14))
        user_info.pack(side="left", padx=(0, 20))
        
        btn_ai = ctk.CTkButton(
            right_frame, text="MỞ HỆ THỐNG NHẬN DIỆN AI", 
            fg_color=self.colors["accent"], hover_color=self.colors["accent_hover"],
            command=lambda: self._handle_action("open_ai")
        )
        btn_ai.pack(side="left", padx=(0, 10))
        
        btn_refresh = ctk.CTkButton(
            right_frame, text="Làm mới", width=80,
            fg_color=self.colors["card"], hover_color=self.colors["panel"],
            border_width=1, border_color=self.colors["accent"],
            command=self._refresh_data
        )
        btn_refresh.pack(side="left", padx=(0, 10))
        
        btn_logout = ctk.CTkButton(
            right_frame, text="Đăng xuất", width=80,
            fg_color=self.colors["red"], hover_color="#c44358",
            command=lambda: self._handle_action("logout")
        )
        btn_logout.pack(side="left")

    def _build_cards(self):
        self.cards_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.cards_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        self.cards_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="card")
        
        self.lbl_total_visits = self._create_card(self.cards_frame, "TỔNG SỐ LƯỢT XE", "0 lượt", 0)
        self.lbl_active_cars = self._create_card(self.cards_frame, "XE ĐANG ĐỖ TẠI BÃI", "0 xe", 1)
        self.lbl_total_revenue = self._create_card(self.cards_frame, "TỔNG DOANH THU ĐÃ THU", "0đ", 2)
        
    def _create_card(self, parent, title, value_placeholder, col):
        card = ctk.CTkFrame(parent, fg_color=self.colors["card"], corner_radius=10)
        card.grid(row=0, column=col, sticky="nsew", padx=10)
        
        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color=self.colors["muted"])
        lbl_title.pack(pady=(15, 5))
        
        lbl_val = ctk.CTkLabel(card, text=value_placeholder, font=ctk.CTkFont(size=28, weight="bold"), text_color=self.colors["text"])
        lbl_val.pack(pady=(0, 15))
        
        return lbl_val

    def _build_charts(self):
        self.charts_frame = ctk.CTkFrame(self.main_container, fg_color="transparent", height=250)
        self.charts_frame.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        self.charts_frame.grid_columnconfigure((0, 1), weight=1, uniform="chart")
        self.charts_frame.grid_propagate(False)
        
        # Chart 1: Doanh thu theo vị trí
        self.chart1_container = ctk.CTkFrame(self.charts_frame, fg_color=self.colors["card"], corner_radius=10)
        self.chart1_container.grid(row=0, column=0, sticky="nsew", padx=10)
        ctk.CTkLabel(self.chart1_container, text="DOANH THU THEO VỊ TRÍ", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.canvas_revenue = tk.Canvas(self.chart1_container, bg=self.colors["card"], highlightthickness=0)
        self.canvas_revenue.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas_revenue.bind("<Configure>", lambda e: self._draw_bar_chart())
        
        # Chart 2: Tần suất đỗ xe theo vị trí
        self.chart2_container = ctk.CTkFrame(self.charts_frame, fg_color=self.colors["card"], corner_radius=10)
        self.chart2_container.grid(row=0, column=1, sticky="nsew", padx=10)
        ctk.CTkLabel(self.chart2_container, text="TẦN SUẤT ĐỖ XE THEO VỊ TRÍ", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.canvas_freq = tk.Canvas(self.chart2_container, bg=self.colors["card"], highlightthickness=0)
        self.canvas_freq.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas_freq.bind("<Configure>", lambda e: self._draw_pie_chart())
        
        self.revenue_data = []
        self.freq_data = []

    def _build_table(self):
        self.table_frame = ctk.CTkFrame(self.main_container, fg_color=self.colors["card"], corner_radius=10)
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=10)
        self.table_frame.grid_rowconfigure(1, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)
        
        header = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=10)
        
        ctk.CTkLabel(header, text="NHẬT KÝ LỊCH SỬ XE RA/VÀO", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        
        self.search_entry = ctk.CTkEntry(header, placeholder_text="Tìm ID vị trí...", textvariable=self.search_var, width=150)
        self.search_entry.pack(side="right", padx=(10, 0))
        self.search_var.trace_add('write', self._on_search_change)
        
        filter_opt = ctk.CTkOptionMenu(
            header, values=["Hôm nay", "7 ngày", "30 ngày", "Tất cả"], 
            variable=self.filter_var, width=120, command=self._on_filter_change
        )
        filter_opt.pack(side="right")
        
        # Style ttk Treeview for dark theme
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure(
            "Treeview", 
            background=self.colors["card"], 
            foreground=self.colors["text"],
            rowheight=35,
            fieldbackground=self.colors["card"],
            borderwidth=0,
            font=("Arial", 11)
        )
        style.configure(
            "Treeview.Heading", 
            background=self.colors["panel"], 
            foreground=self.colors["text"],
            font=("Arial", 12, "bold"),
            borderwidth=0
        )
        style.map("Treeview", background=[("selected", self.colors["accent"])])
        
        tree_container = tk.Frame(self.table_frame, bg=self.colors["card"])
        tree_container.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
        columns = ("id", "slot", "in", "out", "duration", "fee", "mode")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings")
        
        self.tree.heading("id", text="ID Lượt")
        self.tree.heading("slot", text="Mã vị trí")
        self.tree.heading("in", text="Thời gian vào")
        self.tree.heading("out", text="Thời gian ra")
        self.tree.heading("duration", text="Thời gian đỗ")
        self.tree.heading("fee", text="Số tiền thu")
        self.tree.heading("mode", text="Chế độ")
        
        self.tree.column("id", width=250, anchor="w")
        self.tree.column("slot", width=100, anchor="center")
        self.tree.column("in", width=160, anchor="center")
        self.tree.column("out", width=160, anchor="center")
        self.tree.column("duration", width=120, anchor="center")
        self.tree.column("fee", width=120, anchor="e")
        self.tree.column("mode", width=100, anchor="center")
        
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.history_data = []
        self._search_timer = None

    def _format_vnd(self, amount):
        return f"{int(amount):,}".replace(",", ".") + "đ"

    def _refresh_data(self):
        if self._is_closing:
            return
            
        def fetch_task():
            try:
                summary = self.db_manager.fetch_dashboard_summary()
                revenue = self.db_manager.fetch_revenue_by_slot()
                freq = self.db_manager.fetch_frequency_by_slot()
                # pyrefly: ignore [unexpected-keyword]
                hist = self.db_manager.fetch_parking_history(filter_type=self.filter_var.get())
                if not self._is_closing:
                    self.after(0, self._update_ui, summary, revenue, freq, hist)
            except Exception as e:
                print(f"Error fetching data: {e}")
                # Don't crash, keep old data
                pass
                
        threading.Thread(target=fetch_task, daemon=True).start()
        
    def _update_ui(self, summary, revenue, freq, hist):
        if self._is_closing:
            return
            
        # Update cards
        self.lbl_total_visits.configure(text=f"{summary['tong_so_luot']} lượt")
        self.lbl_active_cars.configure(text=f"{summary['xe_dang_do']} xe")
        self.lbl_total_revenue.configure(text=self._format_vnd(summary['tong_doanh_thu']))
        
        # Update charts data
        self.revenue_data = revenue
        self.freq_data = freq
        self._draw_bar_chart()
        self._draw_pie_chart()
        
        # Update table
        self.history_data = hist
        self._filter_and_populate_table()
        
    def _on_filter_change(self, _):
        self._refresh_data()
        
    def _on_search_change(self, *args):
        if self._search_timer:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(300, self._filter_and_populate_table)
        
    def _filter_and_populate_table(self):
        if self._is_closing:
            return
            
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        search_term = self.search_var.get().strip().lower()
        
        for row in self.history_data:
            if search_term and search_term not in str(row['slot_id']).lower():
                continue
                
            out_time = row['gio_ra'].strftime('%d/%m/%Y %H:%M:%S') if row['gio_ra'] else "Đang đỗ..."
            duration = f"{row['duration'] // 60}p {row['duration'] % 60}s" if row['duration'] is not None else "---"
            fee = self._format_vnd(row['fee']) if row['fee'] is not None else "---"
            
            self.tree.insert("", "end", values=(
                row['id'],
                row['slot_id'],
                row['gio_vao'].strftime('%d/%m/%Y %H:%M:%S'),
                out_time,
                duration,
                fee,
                row['mode']
            ))

    def _draw_bar_chart(self):
        c = self.canvas_revenue
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        
        if w <= 1 or h <= 1:
            return
            
        if not self.revenue_data:
            c.create_text(w/2, h/2, text="Chưa có dữ liệu", fill=self.colors["muted"], font=("Arial", 14))
            return
            
        pad_x = 40
        pad_y = 30
        cw = w - pad_x*2
        ch = h - pad_y*2
        
        max_val = max(v for _, v in self.revenue_data)
        if max_val == 0:
            max_val = 1
            
        n = len(self.revenue_data)
        bar_w = cw / (n * 1.5)
        gap = bar_w * 0.5
        
        # Draw axes
        c.create_line(pad_x, h-pad_y, w-pad_x, h-pad_y, fill=self.colors["line"])
        
        for i, (label, val) in enumerate(self.revenue_data):
            x1 = pad_x + i * (bar_w + gap) + gap/2
            y1 = h - pad_y - (val / max_val * ch)
            x2 = x1 + bar_w
            y2 = h - pad_y
            
            c.create_rectangle(x1, y1, x2, y2, fill=self.colors["accent"], outline="")
            # Label X
            c.create_text((x1+x2)/2, y2 + 10, text=str(label), fill=self.colors["text"], font=("Arial", 10))
            # Label Y (VND)
            if val > 0:
                short_val = f"{val//1000}k" if val >= 1000 else str(val)
                c.create_text((x1+x2)/2, y1 - 10, text=short_val, fill=self.colors["muted"], font=("Arial", 9))

    def _draw_pie_chart(self):
        c = self.canvas_freq
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        
        if w <= 1 or h <= 1:
            return
            
        if not self.freq_data or sum(v for _, v in self.freq_data) == 0:
            c.create_text(w/2, h/2, text="Chưa có dữ liệu", fill=self.colors["muted"], font=("Arial", 14))
            return
            
        total = sum(v for _, v in self.freq_data)
        
        pad = 20
        radius = min(w/2 - 100, h/2 - pad) # Leave space for legend
        if radius < 10:
            return
            
        cx, cy = w/2 - 50, h/2
        
        colors = ["#2f8ee8", "#38d69f", "#ffb833", "#ff5d7a", "#8e44ad", "#e67e22", "#1abc9c", "#34495e"]
        
        start_angle = 0
        legend_x = cx + radius + 30
        legend_y_start = cy - (len(self.freq_data) * 20) / 2
        
        for i, (label, val) in enumerate(self.freq_data):
            extent = (val / total) * 360
            color = colors[i % len(colors)]
            
            c.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=start_angle, extent=extent, fill=color, outline=self.colors["card"]
            )
            
            # Donut hole
            c.create_oval(
                cx - radius*0.5, cy - radius*0.5, cx + radius*0.5, cy + radius*0.5,
                fill=self.colors["card"], outline=""
            )
            
            # Legend
            ly = legend_y_start + i * 20
            c.create_rectangle(legend_x, ly-5, legend_x+10, ly+5, fill=color, outline="")
            c.create_text(legend_x + 20, ly, text=f"{label} ({val})", fill=self.colors["text"], anchor="w", font=("Arial", 10))
            
            start_angle += extent

    def _schedule_refresh(self):
        if not self._is_closing:
            self._refresh_data()
            self.refresh_job = self.after(self.refresh_interval_ms, self._schedule_refresh)
            
    def _handle_action(self, action):
        self._is_closing = True
        if self.refresh_job:
            self.after_cancel(self.refresh_job)
        self.destroy()
        self.on_action(action)
