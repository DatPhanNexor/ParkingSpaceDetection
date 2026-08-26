import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from dataclasses import dataclass
from typing import Optional, Callable
from PIL import Image, ImageOps
import platform
import sys
from pathlib import Path

_APP_MODULE_DIR = Path(__file__).resolve().parent
if str(_APP_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_MODULE_DIR))

from database_manager import DatabaseManager, DatabaseError

@dataclass
class AuthSession:
    user_id: int
    username: str
    ho_ten: str
    role: str

class AuthWindow(ctk.CTkFrame):
    def __init__(self, parent, db_manager: DatabaseManager, on_login_success: Callable[[AuthSession], None]):
        super().__init__(parent)
        self.db_manager = db_manager
        self.on_login_success = on_login_success
        self.session: Optional[AuthSession] = None
        
        # Window setup
        self.winfo_toplevel().title("Đăng nhập hệ thống - AI Parking")
        self.winfo_toplevel().geometry("1400x820")
        self.winfo_toplevel().minsize(1050, 650)
        
        # Center window
        self.update_idletasks()
        width = 1400
        height = 820
        x = max(0, (self.winfo_screenwidth() // 2) - (width // 2))
        y = max(0, (self.winfo_screenheight() // 2) - (height // 2))
        self.winfo_toplevel().geometry(f"{width}x{height}+{x}+{y}")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.colors = {
            "bg": "#091421",
            "card": "#14243a",
            "text": "#f8fbff",
            "accent": "#2f8ee8",
            "accent_hover": "#1e72c4",
            "error": "#ff5d7a",
            "success": "#38d69f"
        }
        self.configure(fg_color=self.colors["bg"])
        
        self._load_app_logo()
        
        # Grid layout: 2 columns (50% left, 50% right)
        self.grid_columnconfigure(0, weight=1, uniform="auth_columns")
        self.grid_columnconfigure(1, weight=1, uniform="auth_columns")
        self.grid_rowconfigure(0, weight=1)
        
        self._create_left_panel()
        self._create_right_panel()
        
        # Check DB connection
        if not self.db_manager.test_connection():
            self._show_error("Chưa kết nối được cơ sở dữ liệu. Hãy import database\\ai_parking_system.sql vào phpMyAdmin.", is_db_error=True)

    def _load_app_logo(self):
        self.window_icon_ref = None
        self.header_logo_image = None
        try:
            png_path = _APP_MODULE_DIR / "assets" / "parking_logo_3d.png"
            ico_path = _APP_MODULE_DIR / "assets" / "parking_logo_3d.ico"
            if png_path.exists():
                from PIL import ImageTk
                logo = Image.open(png_path).convert("RGBA")
                icon = ImageOps.contain(logo, (64, 64), Image.Resampling.LANCZOS)
                self.window_icon_ref = ImageTk.PhotoImage(icon)
                # pyrefly: ignore [bad-argument-type]
                self.winfo_toplevel().iconphoto(True, self.window_icon_ref)
                if platform.system() == "Windows" and ico_path.exists():
                    self.winfo_toplevel().iconbitmap(default=str(ico_path))
                
                self.header_logo_image = ctk.CTkImage(
                    light_image=logo,
                    dark_image=logo,
                    size=(96, 96)
                )
        except Exception as e:
            print(f"Error loading logo: {e}")

    def _create_left_panel(self):
        self.hero_panel = ctk.CTkFrame(self, fg_color=self.colors["bg"], corner_radius=0)
        self.hero_panel.grid(row=0, column=0, sticky="nsew")
        self.hero_panel.grid_rowconfigure(0, weight=1)
        self.hero_panel.grid_rowconfigure(2, weight=1)
        self.hero_panel.grid_columnconfigure(0, weight=1)
        self.hero_panel.grid_columnconfigure(2, weight=1)
        
        self.hero_content = ctk.CTkFrame(self.hero_panel, fg_color="transparent")
        self.hero_content.grid(row=1, column=1, sticky="")
        
        if self.header_logo_image:
            logo_label = ctk.CTkLabel(self.hero_content, text="", image=self.header_logo_image)
        else:
            logo_label = ctk.CTkLabel(self.hero_content, text="🅿️", font=("Arial", 80))
        logo_label.pack(pady=(0, 26))
        
        title1 = ctk.CTkLabel(
            self.hero_content, 
            text="HỆ THỐNG QUẢN LÝ", 
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=self.colors["text"],
            justify="center"
        )
        title1.pack(pady=(0, 4))
        
        title2 = ctk.CTkLabel(
            self.hero_content, 
            text="BÃI ĐỖ XE THÔNG MINH", 
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=self.colors["text"],
            justify="center"
        )
        title2.pack(pady=(0, 18))
        
        subtitle = ctk.CTkLabel(
            self.hero_content,
            text="Nhận diện, theo dõi và quản lý bãi đỗ xe bằng AI",
            font=ctk.CTkFont(size=16),
            text_color="#8ea4c8",
            wraplength=380,
            justify="center"
        )
        subtitle.pack()

    def _create_right_panel(self):
        self.auth_panel = ctk.CTkFrame(self, fg_color=self.colors["bg"], corner_radius=0)
        self.auth_panel.grid(row=0, column=1, sticky="nsew")
        self.auth_panel.grid_rowconfigure(0, weight=1)
        self.auth_panel.grid_rowconfigure(2, weight=1)
        self.auth_panel.grid_columnconfigure(0, weight=1)
        self.auth_panel.grid_columnconfigure(2, weight=1)
        
        self.auth_card = ctk.CTkFrame(self.auth_panel, fg_color=self.colors["card"], corner_radius=15)
        self.auth_card.grid(row=1, column=1, sticky="")
        self.auth_card.grid_columnconfigure(0, weight=1)
        
        self.login_frame = ctk.CTkFrame(self.auth_card, fg_color="transparent")
        self.register_frame = ctk.CTkFrame(self.auth_card, fg_color="transparent")
        
        self._build_login_form()
        self._build_register_form()
        
        self.login_frame.grid(row=0, column=0, sticky="nsew", padx=40, pady=40)
        
    def _build_login_form(self):
        # minsize 460 + 80 padding = 540 total width
        self.login_frame.grid_columnconfigure(0, weight=1, minsize=460)
        
        lbl_title = ctk.CTkLabel(self.login_frame, text="ĐĂNG NHẬP", font=ctk.CTkFont(size=24, weight="bold"))
        lbl_title.grid(row=0, column=0, pady=(0, 48))
        
        self.login_msg = ctk.CTkLabel(self.login_frame, text="", text_color=self.colors["error"], font=ctk.CTkFont(size=13))
        self.login_msg.grid(row=1, column=0, pady=(0, 10))
        
        self.log_username = ctk.CTkEntry(self.login_frame, placeholder_text="Tên đăng nhập", height=48, font=ctk.CTkFont(size=15))
        self.log_username.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        
        self.log_password = ctk.CTkEntry(self.login_frame, placeholder_text="Mật khẩu", show="*", height=48, font=ctk.CTkFont(size=15))
        self.log_password.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        self.log_password.bind("<Return>", lambda e: self._attempt_login())
        
        self.log_show_pwd = ctk.BooleanVar()
        chk_show = ctk.CTkCheckBox(self.login_frame, text="Hiện mật khẩu", variable=self.log_show_pwd, command=self._toggle_login_pwd)
        chk_show.grid(row=4, column=0, sticky="w", pady=(0, 24))
        
        btn_login = ctk.CTkButton(
            self.login_frame, text="ĐĂNG NHẬP", height=48, 
            fg_color=self.colors["accent"], hover_color=self.colors["accent_hover"],
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._attempt_login
        )
        btn_login.grid(row=5, column=0, sticky="ew", pady=(0, 24))
        
        btn_switch = ctk.CTkButton(
            self.login_frame, text="Chưa có tài khoản? Tạo tài khoản", 
            fg_color="transparent", hover_color=self.colors["card"],
            text_color=self.colors["accent"],
            font=ctk.CTkFont(size=14),
            command=lambda: self._switch_frame(self.register_frame)
        )
        btn_switch.grid(row=6, column=0)
        
    def _build_register_form(self):
        # minsize 480 + 80 padding = 560 total width
        self.register_frame.grid_columnconfigure(0, weight=1, minsize=480)
        self.register_frame.grid_rowconfigure(3, weight=1) # Allow scrollable area to expand
        
        lbl_title = ctk.CTkLabel(self.register_frame, text="TẠO TÀI KHOẢN", font=ctk.CTkFont(size=24, weight="bold"))
        lbl_title.grid(row=0, column=0, pady=(0, 24))
        
        self.reg_msg = ctk.CTkLabel(self.register_frame, text="", text_color=self.colors["error"], font=ctk.CTkFont(size=13))
        self.reg_msg.grid(row=1, column=0, pady=(0, 5))
        
        # Internal scrollable frame for fields in case of small height
        self.reg_fields = ctk.CTkScrollableFrame(self.register_frame, fg_color="transparent", height=280)
        self.reg_fields.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        self.reg_fields.grid_columnconfigure(0, weight=1)
        
        self.reg_name = ctk.CTkEntry(self.reg_fields, placeholder_text="Họ và tên", height=48, font=ctk.CTkFont(size=15))
        self.reg_name.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        
        self.reg_username = ctk.CTkEntry(self.reg_fields, placeholder_text="Tên đăng nhập", height=48, font=ctk.CTkFont(size=15))
        self.reg_username.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        
        self.reg_password = ctk.CTkEntry(self.reg_fields, placeholder_text="Mật khẩu", show="*", height=48, font=ctk.CTkFont(size=15))
        self.reg_password.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        
        self.reg_password_conf = ctk.CTkEntry(self.reg_fields, placeholder_text="Nhập lại mật khẩu", show="*", height=48, font=ctk.CTkFont(size=15))
        self.reg_password_conf.grid(row=3, column=0, sticky="ew", pady=(0, 14))
        
        self.reg_show_pwd = ctk.BooleanVar()
        chk_show = ctk.CTkCheckBox(self.reg_fields, text="Hiện mật khẩu", variable=self.reg_show_pwd, command=self._toggle_reg_pwd)
        chk_show.grid(row=4, column=0, sticky="w", pady=(0, 10))
        
        btn_reg = ctk.CTkButton(
            self.register_frame, text="TẠO TÀI KHOẢN", height=48, 
            fg_color=self.colors["accent"], hover_color=self.colors["accent_hover"],
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._attempt_register
        )
        btn_reg.grid(row=4, column=0, sticky="ew", pady=(0, 24))
        
        btn_switch = ctk.CTkButton(
            self.register_frame, text="Đã có tài khoản? Đăng nhập", 
            fg_color="transparent", hover_color=self.colors["card"],
            text_color=self.colors["accent"],
            font=ctk.CTkFont(size=14),
            command=lambda: self._switch_frame(self.login_frame)
        )
        btn_switch.grid(row=5, column=0)
        
    def _toggle_login_pwd(self):
        show = "" if self.log_show_pwd.get() else "*"
        self.log_password.configure(show=show)
        
    def _toggle_reg_pwd(self):
        show = "" if self.reg_show_pwd.get() else "*"
        self.reg_password.configure(show=show)
        self.reg_password_conf.configure(show=show)
        
    def _switch_frame(self, frame_to_show):
        self.login_frame.grid_forget()
        self.register_frame.grid_forget()
        self.login_msg.configure(text="")
        self.reg_msg.configure(text="")
        frame_to_show.grid(row=0, column=0, sticky="nsew", padx=40, pady=40)
        
    def _show_error(self, message: str, is_db_error: bool = False):
        if is_db_error:
            self.login_msg.configure(text=message, text_color=self.colors["error"])
            self.reg_msg.configure(text=message, text_color=self.colors["error"])
        else:
            if self.login_frame.winfo_ismapped():
                self.login_msg.configure(text=message, text_color=self.colors["error"])
            else:
                self.reg_msg.configure(text=message, text_color=self.colors["error"])

    def _show_success(self, message: str):
        self.reg_msg.configure(text=message, text_color=self.colors["success"])
        
    def _attempt_login(self):
        username = self.log_username.get().strip()
        password = self.log_password.get()
        
        if not username or not password:
            self._show_error("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.")
            return
            
        try:
            user_data = self.db_manager.authenticate_user(username, password)
            if user_data:
                self.db_manager.update_last_login(user_data['user_id'])
                self.session = AuthSession(**user_data)
                self.on_login_success(self.session)
            else:
                self._show_error("Tên đăng nhập hoặc mật khẩu không đúng.")
        except DatabaseError as e:
            self._show_error(str(e))
        except Exception:
            self._show_error("Lỗi hệ thống. Vui lòng thử lại sau.")
            
    def _attempt_register(self):
        name = self.reg_name.get().strip()
        username = self.reg_username.get().strip()
        pwd = self.reg_password.get()
        pwd_conf = self.reg_password_conf.get()
        
        if not name or not username or not pwd or not pwd_conf:
            self._show_error("Vui lòng điền đầy đủ thông tin.")
            return
            
        if len(name) < 2:
            self._show_error("Họ và tên phải từ 2 ký tự.")
            return
            
        if not (4 <= len(username) <= 50) or " " in username or not all(c.isalnum() or c in "._" for c in username):
            self._show_error("Tên đăng nhập 4-50 ký tự, không chứa khoảng trắng, chỉ dùng chữ, số, dấu chấm, gạch dưới.")
            return
            
        if len(pwd) < 8 or not any(c.isalpha() for c in pwd) or not any(c.isdigit() for c in pwd):
            self._show_error("Mật khẩu tối thiểu 8 ký tự, gồm cả chữ và số.")
            return
            
        if pwd != pwd_conf:
            self._show_error("Hai mật khẩu không khớp.")
            return
            
        try:
            if self.db_manager.create_user(username, pwd, name):
                # Clear fields
                self.reg_name.delete(0, tk.END)
                self.reg_username.delete(0, tk.END)
                self.reg_password.delete(0, tk.END)
                self.reg_password_conf.delete(0, tk.END)
                
                # Switch to login and prefill username
                self._switch_frame(self.login_frame)
                self.log_username.delete(0, tk.END)
                self.log_username.insert(0, username)
                self.login_msg.configure(text="Đăng ký thành công. Vui lòng đăng nhập.", text_color=self.colors["success"])
        except DatabaseError as e:
            self._show_error(str(e))
        except Exception:
            self._show_error("Lỗi hệ thống khi đăng ký.")
