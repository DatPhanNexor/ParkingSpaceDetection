from __future__ import annotations

from pathlib import Path
import signal
import sys
import threading
import tkinter as tk
import customtkinter as ctk

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app_gui import ParkingSpaceDesktopApp
from database_manager import DatabaseManager
from auth_ui import AuthWindow, AuthSession

def main() -> int:
    # 1. Khởi tạo một Root duy nhất
    root = ctk.CTk()
    root.title("Parking Space Detection")
    
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    w = min(1400, int(screen_w * 0.94))
    h = min(820, int(screen_h * 0.92))
    root.geometry(f"{w}x{h}")
    root.minsize(1024, 720)

    closing = threading.Event()
    
    def cancel_all_tcl_afters(r: tk.Tk | ctk.CTk):
        try:
            if not r.winfo_exists():
                return
            after_ids = r.tk.call("after", "info")
            if isinstance(after_ids, str):
                after_ids = (after_ids,)
            for after_id in after_ids:
                try:
                    r.after_cancel(after_id)
                except tk.TclError:
                    pass
        except Exception:
            pass

    current_app = None

    def handle_sigint(signum, frame):
        closing.set()
        print("\nCtrl+C received. Closing app safely...")
        if current_app and hasattr(current_app, "shutdown_from_terminal"):
            try:
                current_app.shutdown_from_terminal()
            except Exception:
                root.quit()
        else:
            root.quit()

    old_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handle_sigint)

    db_manager = DatabaseManager()

    # 2. Logic chuyển View
    def show_auth():
        nonlocal current_app
        if current_app:
            current_app.destroy()
            current_app = None

        def on_login(session: AuthSession):
            show_ai(session)
            
        current_app = AuthWindow(
            parent=root, 
            db_manager=db_manager, 
            on_login_success=on_login
        )
        current_app.pack(fill="both", expand=True)

    def show_ai(session: AuthSession):
        nonlocal current_app
        if current_app:
            current_app.destroy()
            current_app = None

        def on_ai_action(action: str):
            if action == "logout":
                show_auth()
            elif action == "exit":
                root.quit()

        current_app = ParkingSpaceDesktopApp(
            parent=root, 
            project_root=PROJECT_ROOT, 
            app_dir=APP_DIR, 
            auth_session=session, 
            on_action=on_ai_action
        )
        if hasattr(current_app, 'billing_manager'):
            current_app.billing_manager.db_manager = db_manager
            current_app.billing_manager.db_user_id = session.user_id
            
        current_app.pack(fill="both", expand=True)

    # 3. Setup đóng chương trình an toàn qua dấu X
    def on_root_close():
        if current_app and hasattr(current_app, "_request_window_close"):
            # Yêu cầu AI app tự dọn dẹp camera trước
            current_app._request_window_close("exit")
        else:
            root.quit()

    root.protocol("WM_DELETE_WINDOW", on_root_close)

    # 4. Hiển thị trang đăng nhập đầu tiên
    show_auth()

    # 5. Gọi mainloop ĐÚNG MỘT LẦN
    try:
        root.mainloop()
    except KeyboardInterrupt:
        if current_app and hasattr(current_app, "shutdown_from_terminal"):
            try:
                current_app.shutdown_from_terminal()
            except:
                pass

    # 6. Dọn dẹp sạch sẽ
    cancel_all_tcl_afters(root)
    try:
        root.destroy()
    except Exception:
        pass

    signal.signal(signal.SIGINT, old_sigint)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
