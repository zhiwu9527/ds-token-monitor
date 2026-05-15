import tkinter as tk
from tkinter import ttk
import threading
import urllib.request
import urllib.error
import json
import ssl
from datetime import datetime
import os

try:
    import keyboard as _kb
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

ACCOUNT = {
    "email": "",
    "mobile": "",
    "password": "",
    "area_code": "+86",
    "device_id": "",
    "os": "web",
}

LOGIN_URL = "https://platform.deepseek.com/auth-api/v0/users/login"
USAGE_URL = "https://platform.deepseek.com/api/v0/usage/amount"
SUMMARY_URL = "https://platform.deepseek.com/api/v0/users/get_user_summary"

COLORS_DARK = {
    "bg": "#1a1a2e",
    "bg2": "#16213e",
    "bg3": "#0f0f1a",
    "bg4": "#252540",
    "accent": "#d4a843",
    "accent2": "#c9952e",
    "accent_light": "#2a2a40",
    "success": "#d4a843",
    "danger": "#e74c3c",
    "warning": "#d4a843",
    "text": "#f0e6d3",
    "text2": "#b8a88a",
    "text3": "#7a6f5f",
    "border": "#3a3a50",
    "border2": "#4a4a60",
    "card": "#1e1e30",
    "card_border": "#3a3a50",
    "hover": "#252540",
    "shadow": "#0a0a15",
    "frost": "#1a1a2e",
    "input_bg": "#252540",
    "btn_fg": "#0f0f1a",
}

COLORS_LIGHT = {
    "bg": "#f7f8fc",
    "bg2": "#ffffff",
    "bg3": "#ffffff",
    "bg4": "#f0f1f5",
    "accent": "#6c5ce7",
    "accent2": "#5a4bd1",
    "accent_light": "#f0eeff",
    "success": "#2bcd71",
    "danger": "#e74c3c",
    "warning": "#f0a030",
    "text": "#2d3436",
    "text2": "#636e72",
    "text3": "#b2bec3",
    "border": "#e0e3e8",
    "border2": "#d0d3d8",
    "card": "#ffffff",
    "card_border": "#e0e3e8",
    "hover": "#f0f1f5",
    "shadow": "#d0d3d8",
    "frost": "#f7f8fc",
    "input_bg": "#f5f6fa",
    "btn_fg": "#ffffff",
}

# 默认使用暗色主题
COLORS = dict(COLORS_DARK)

def set_theme(theme_name):
    """切换主题: 'dark' 或 'light'"""
    global COLORS
    if theme_name == "light":
        COLORS.update(COLORS_LIGHT)
    else:
        COLORS.update(COLORS_DARK)

def get_current_theme():
    """获取当前主题名"""
    return "dark" if COLORS["bg"] == COLORS_DARK["bg"] else "light"

class TokenRecord:
    __slots__ = ("date", "cached", "uncached", "total")
    def __init__(self, date="", cached=0, uncached=0, total=0):
        self.date = date
        self.cached = cached
        self.uncached = uncached
        self.total = total or (cached + uncached)
    @property
    def hit_rate(self):
        return (self.cached / self.total * 100) if self.total > 0 else 0.0

class TokenMonitor:
    _instance = None
    _lock = threading.Lock()
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance
    def _init(self):
        self.records = []
        self.extra_info = {}
        self.records_lock = threading.Lock()
        self._listeners = []
        self._last_update = None
    def set_records(self, records):
        with self.records_lock:
            self.records = list(records)
            self._last_update = datetime.now()
        self._notify()
    def set_extra_info(self, info):
        with self.records_lock:
            self.extra_info = dict(info)
        self._notify()
    def get_extra_info(self):
        with self.records_lock:
            return dict(self.extra_info)
    def get_records(self):
        with self.records_lock:
            return list(self.records)
    def get_stats(self):
        with self.records_lock:
            records = list(self.records)
        total_cached = sum(r.cached for r in records)
        total_uncached = sum(r.uncached for r in records)
        total_all = total_cached + total_uncached
        return {
            "total_cached": total_cached,
            "total_uncached": total_uncached,
            "total_all": total_all,
            "count": len(records),
            "hit_rate": (total_cached / total_all * 100) if total_all > 0 else 0,
        }
    def add_listener(self, callback):
        self._listeners.append(callback)
    def _notify(self):
        for cb in self._listeners:
            try:
                cb()
            except Exception:
                pass

ssl_ctx = ssl.create_default_context()

def _make_headers(token=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://platform.deepseek.com",
        "Referer": "https://platform.deepseek.com/",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def _deep_get(obj, *paths):
    for path in paths:
        keys = path.split(".")
        val = obj
        try:
            for k in keys:
                if isinstance(val, list):
                    val = val[int(k)]
                else:
                    val = val[k]
            if val is not None:
                return val
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return 0

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def api_login_manual(mobile, password):
    payload = dict(ACCOUNT)
    payload["mobile"] = mobile
    payload["password"] = password
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(LOGIN_URL, data=data, headers=_make_headers(), method="POST")
    try:
        resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=15)
        body = json.loads(resp.read().decode("utf-8"))
        token = _deep_get(body, "data.biz_data.user.token", "data.token", "token", "data.access_token", "access_token")
        return token, None
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("message", err_body.get("msg", str(e)))
        except Exception:
            msg = str(e)
        return None, msg
    except Exception as e:
        return None, str(e)

def api_fetch_usage(token, month=None, year=None):
    now = datetime.now()
    m = month or now.month
    y = year or now.year
    url = f"{USAGE_URL}?month={m}&year={y}"
    req = urllib.request.Request(url, headers=_make_headers(token), method="GET")
    try:
        resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=15)
        body = json.loads(resp.read().decode("utf-8"))
        return body, None
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("message", err_body.get("msg", str(e)))
        except Exception:
            msg = str(e)
        if e.code == 401:
            return None, "token_expired"
        return None, msg
    except Exception as e:
        return None, str(e)

def api_fetch_summary(token):
    req = urllib.request.Request(SUMMARY_URL, headers=_make_headers(token), method="GET")
    try:
        resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=15)
        body = json.loads(resp.read().decode("utf-8"))
        return body, None
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("message", err_body.get("msg", str(e)))
        except Exception:
            msg = str(e)
        if e.code == 401:
            return None, "token_expired"
        return None, msg
    except Exception as e:
        return None, str(e)

def parse_summary_response(data):
    result = {"balance": 0, "monthly_usage": 0, "monthly_tokens": 0}
    # 从 biz_data 中提取余额: normal_wallets[0].balance + bonus_wallets[0].balance
    biz_data = _deep_get(data, "data.biz_data")
    if isinstance(biz_data, dict):
        # 余额 (CNY)
        normal_wallets = biz_data.get("normal_wallets", [])
        if isinstance(normal_wallets, list) and len(normal_wallets) > 0:
            balance_raw = normal_wallets[0].get("balance", "0")
            try:
                result["balance"] = float(balance_raw)
            except (TypeError, ValueError):
                pass
        # 赠金余额
        bonus_wallets = biz_data.get("bonus_wallets", [])
        if isinstance(bonus_wallets, list) and len(bonus_wallets) > 0:
            bonus_raw = bonus_wallets[0].get("balance", "0")
            try:
                result["balance"] += float(bonus_raw)
            except (TypeError, ValueError):
                pass
        # 本月消费 (CNY)
        monthly_costs = biz_data.get("monthly_costs", [])
        if isinstance(monthly_costs, list) and len(monthly_costs) > 0:
            cost_raw = monthly_costs[0].get("amount", "0")
            try:
                result["monthly_usage"] = float(cost_raw)
            except (TypeError, ValueError):
                pass
        # 本月 token 用量
        monthly_token_raw = biz_data.get("monthly_token_usage", biz_data.get("monthly_usage", "0"))
        try:
            result["monthly_tokens"] = int(float(monthly_token_raw))
        except (TypeError, ValueError):
            pass
    else:
        # 兜底: 尝试旧路径
        balance_raw = _deep_get(data, "data.available_amount", "data.balance", "data.amount",
                                 "available_amount", "balance", "amount")
        monthly_raw = _deep_get(data, "data.monthly_usage", "data.this_month_usage",
                                 "monthly_usage", "this_month_usage")
        if isinstance(balance_raw, (int, float, str)):
            try:
                result["balance"] = float(balance_raw)
            except (TypeError, ValueError):
                pass
        if isinstance(monthly_raw, (int, float, str)):
            try:
                result["monthly_usage"] = float(monthly_raw)
            except (TypeError, ValueError):
                pass
    return result

def parse_usage_response(data):
    records = []
    days = _deep_get(data, "data.biz_data.days", "biz_data.days", "data.days", "days")
    if isinstance(days, list) and len(days) > 0:
        for day_entry in days:
            day_date = str(_deep_get(day_entry, "date", "Date"))
            day_data = _deep_get(day_entry, "data", "Data")
            if not isinstance(day_data, list):
                continue
            day_cached = 0
            day_uncached = 0
            for model_entry in day_data:
                usages = _deep_get(model_entry, "usage", "Usage")
                if not isinstance(usages, list):
                    continue
                for u in usages:
                    utype = str(_deep_get(u, "type", "Type"))
                    amount = int(float(_deep_get(u, "amount", "Amount") or 0))
                    if "CACHE_HIT" in utype or "cache_hit" in utype:
                        day_cached += amount
                    elif "CACHE_MISS" in utype or "cache_miss" in utype:
                        day_uncached += amount
            if day_cached > 0 or day_uncached > 0:
                records.append(TokenRecord(date=day_date, cached=day_cached, uncached=day_uncached))
        if records:
            return records
    total_list = _deep_get(data, "data.biz_data.total", "biz_data.total", "data.total", "total")
    if isinstance(total_list, list) and len(total_list) > 0:
        total_cached = 0
        total_uncached = 0
        for model_entry in total_list:
            usages = _deep_get(model_entry, "usage", "Usage")
            if not isinstance(usages, list):
                continue
            for u in usages:
                utype = str(_deep_get(u, "type", "Type"))
                amount = int(float(_deep_get(u, "amount", "Amount") or 0))
                if "CACHE_HIT" in utype or "cache_hit" in utype:
                    total_cached += amount
                elif "CACHE_MISS" in utype or "cache_miss" in utype:
                    total_uncached += amount
        if total_cached > 0 or total_uncached > 0:
            records.append(TokenRecord(
                date=f"{datetime.now().year}-{datetime.now().month:02d}",
                cached=total_cached, uncached=total_uncached
            ))
            return records
    cached = int(_deep_get(data, "data.cached_tokens", "cached_tokens", "cachedTokens",
                           "data.cachedTokens", "cached", "total_cached","totalCached"))
    uncached = int(_deep_get(data, "data.uncached_tokens", "uncached_tokens", "uncachedTokens",
                             "data.uncachedTokens", "uncached", "total_uncached","totalUncached"))
    total = int(_deep_get(data, "data.total_tokens", "total_tokens", "totalTokens",
                          "data.totalTokens", "data.total", "total",
                          "total_amount", "totalAmount"))
    if cached > 0 or uncached > 0 or total > 0:
        records.append(TokenRecord(
            date=f"{datetime.now().year}-{datetime.now().month:02d}",
            cached=cached, uncached=uncached, total=total
        ))
        return records
    amount = _deep_get(data, "data.amount", "amount", "data")
    if isinstance(amount, dict):
        cached = int(_deep_get(amount, "cached_tokens", "cachedTokens", "cached"))
        uncached = int(_deep_get(amount, "uncached_tokens", "uncachedTokens", "uncached"))
        total = int(_deep_get(amount, "total_tokens", "totalTokens", "total"))
        if cached > 0 or uncached > 0 or total > 0:
            records.append(TokenRecord(
                date=f"{datetime.now().year}-{datetime.now().month:02d}",
                cached=cached, uncached=uncached, total=total
            ))
            return records
    return records

def _format_num(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.2f}K"
    if isinstance(n, float):
        return f"{n:.2f}"
    return str(n)

class ManualLoginWindow:
    def __init__(self, parent, callback, quit_callback=None):
        self.win = tk.Toplevel(parent)
        self.win.title("DeepSeek 登录")
        self.win.configure(bg=COLORS["bg3"])
        self.win.resizable(False, False)
        self.win.overrideredirect(True)
        self.callback = callback
        self.quit_callback = quit_callback
        self._drag_data = {"x": 0, "y": 0}
        self._pwd_visible = False
        self._mobile_placeholder = True
        self._pwd_placeholder = True

        self.win.update_idletasks()
        w, h = 320, 280
        if parent.winfo_viewable():
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            px = parent.winfo_x()
            py = parent.winfo_y()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
        else:
            screen_w = parent.winfo_screenwidth()
            screen_h = parent.winfo_screenheight()
            x = (screen_w - w) // 2
            y = (screen_h - h) // 2
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.win.attributes("-alpha", 0.97)

        # 外框
        border_frame = tk.Frame(self.win, bg=COLORS["border"], bd=0)
        border_frame.pack(fill="both", expand=True, padx=0, pady=0)

        container = tk.Frame(border_frame, bg=COLORS["bg3"], bd=0)
        container.pack(fill="both", expand=True, padx=1, pady=1)
        container.bind("<Button-1>", self._start_drag)
        container.bind("<B1-Motion>", self._do_drag)
        container.bind("<ButtonRelease-1>", self._stop_drag)

        # 顶部栏
        top_bar = tk.Frame(container, bg=COLORS["bg3"], height=32)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)
        top_bar.bind("<Button-1>", self._start_drag)
        top_bar.bind("<B1-Motion>", self._do_drag)
        top_bar.bind("<ButtonRelease-1>", self._stop_drag)

        tk.Label(top_bar, text="⚡ DeepSeek", font=("Microsoft YaHei", 9, "bold"),
                 fg=COLORS["accent"], bg=COLORS["bg3"]).pack(side="left", padx=10, pady=6)

        close_btn = tk.Label(top_bar, text="✕", font=("Segoe UI", 9),
                             fg=COLORS["text3"], bg=COLORS["bg3"], cursor="hand2")
        close_btn.pack(side="right", padx=10, pady=6)
        close_btn.bind("<Button-1>", lambda e: self._on_close())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=COLORS["danger"]))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=COLORS["text3"]))

        # 表单区域
        form = tk.Frame(container, bg=COLORS["bg3"])
        form.pack(fill="x", padx=24, pady=(4, 0))

        # 手机号
        tk.Label(form, text="手机号", font=("Microsoft YaHei", 8),
                 fg=COLORS["text2"], bg=COLORS["bg3"], anchor="w").pack(fill="x", pady=(0, 4))
        mobile_outer = tk.Frame(form, bg=COLORS["border"], bd=0)
        mobile_outer.pack(fill="x")
        mobile_inner = tk.Frame(mobile_outer, bg=COLORS["input_bg"], bd=0)
        mobile_inner.pack(fill="x", padx=1, pady=1)
        self.mobile_entry = tk.Entry(mobile_inner, font=("Microsoft YaHei", 9),
                                     bg=COLORS["input_bg"], fg=COLORS["text3"],
                                     insertbackground=COLORS["text"], relief="flat", bd=0)
        self.mobile_entry.pack(fill="x", ipady=7, padx=10, pady=2)
        self.mobile_entry.insert(0, "请输入手机号")
        self._mobile_outer = mobile_outer

        # 间距
        tk.Frame(form, bg=COLORS["bg3"], height=10).pack(fill="x")

        # 密码
        tk.Label(form, text="密码", font=("Microsoft YaHei", 8),
                 fg=COLORS["text2"], bg=COLORS["bg3"], anchor="w").pack(fill="x", pady=(0, 4))
        pwd_outer = tk.Frame(form, bg=COLORS["border"], bd=0)
        pwd_outer.pack(fill="x")
        pwd_inner = tk.Frame(pwd_outer, bg=COLORS["input_bg"], bd=0)
        pwd_inner.pack(fill="x", padx=1, pady=1)
        self.pwd_entry = tk.Entry(pwd_inner, font=("Microsoft YaHei", 9),
                                  bg=COLORS["input_bg"], fg=COLORS["text3"],
                                  insertbackground=COLORS["text"], relief="flat", bd=0, show="")
        self.pwd_entry.pack(side="left", fill="x", expand=True, ipady=7, padx=10, pady=2)
        self.pwd_entry.insert(0, "请输入密码")
        self._pwd_outer = pwd_outer

        self.toggle_btn = tk.Label(pwd_inner, text="👁", font=("Segoe UI", 9),
                                   fg=COLORS["text3"], bg=COLORS["input_bg"], cursor="hand2")
        self.toggle_btn.pack(side="right", padx=(0, 8))
        self.toggle_btn.bind("<Button-1>", lambda e: self._toggle_password())
        self.toggle_btn.bind("<Enter>", lambda e: self.toggle_btn.configure(fg=COLORS["accent"]))
        self.toggle_btn.bind("<Leave>", lambda e: self.toggle_btn.configure(fg=COLORS["text3"]))

        # 状态提示
        self.status_label = tk.Label(form, text="", font=("Microsoft YaHei", 7),
                                     fg=COLORS["danger"], bg=COLORS["bg3"], anchor="w")
        self.status_label.pack(fill="x", pady=(8, 0))

        # 登录按钮
        self.login_btn = tk.Button(form, text="登 录", font=("Microsoft YaHei", 9, "bold"),
                                   bg=COLORS["accent"], fg=COLORS["btn_fg"], relief="flat", bd=0,
                                   activebackground=COLORS["accent2"], activeforeground=COLORS["btn_fg"],
                                   cursor="hand2", command=self._do_login, highlightthickness=0)
        self.login_btn.pack(fill="x", ipady=7, pady=(12, 0))

        # 绑定事件
        self.mobile_entry.bind("<FocusIn>", lambda e: self._on_focus_in("mobile"))
        self.mobile_entry.bind("<FocusOut>", lambda e: self._on_focus_out("mobile"))
        self.pwd_entry.bind("<FocusIn>", lambda e: self._on_focus_in("password"))
        self.pwd_entry.bind("<FocusOut>", lambda e: self._on_focus_out("password"))
        self.mobile_entry.bind("<Return>", lambda e: self.pwd_entry.focus_set())
        self.pwd_entry.bind("<Return>", lambda e: self._do_login())

    def _on_focus_in(self, field):
        if field == "mobile":
            self._mobile_outer.configure(bg=COLORS["accent"])
            if self._mobile_placeholder:
                self.mobile_entry.delete(0, "end")
                self.mobile_entry.configure(fg=COLORS["text"])
                self._mobile_placeholder = False
        else:
            self._pwd_outer.configure(bg=COLORS["accent"])
            if self._pwd_placeholder:
                self.pwd_entry.delete(0, "end")
                self.pwd_entry.configure(fg=COLORS["text"], show="*")
                self._pwd_placeholder = False

    def _on_focus_out(self, field):
        if field == "mobile":
            self._mobile_outer.configure(bg=COLORS["border"])
            if not self.mobile_entry.get():
                self.mobile_entry.insert(0, "请输入手机号")
                self.mobile_entry.configure(fg=COLORS["text3"])
                self._mobile_placeholder = True
        else:
            self._pwd_outer.configure(bg=COLORS["border"])
            if not self.pwd_entry.get():
                self.pwd_entry.configure(show="")
                self.pwd_entry.insert(0, "请输入密码")
                self.pwd_entry.configure(fg=COLORS["text3"])
                self._pwd_placeholder = True

    def _get_mobile(self):
        val = self.mobile_entry.get().strip()
        return "" if self._mobile_placeholder else val

    def _get_password(self):
        val = self.pwd_entry.get().strip()
        return "" if self._pwd_placeholder else val

    def _on_close(self):
        if self.quit_callback:
            self.quit_callback()
        else:
            self.win.destroy()

    def _toggle_password(self):
        self._pwd_visible = not self._pwd_visible
        if self._pwd_placeholder:
            return
        self.pwd_entry.configure(show="" if self._pwd_visible else "*")
        self.toggle_btn.configure(text="👁‍🗨" if self._pwd_visible else "👁")

    def _start_drag(self, event):
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _do_drag(self, event):
        dx = event.x_root - self._drag_data["x"]
        dy = event.y_root - self._drag_data["y"]
        x = self.win.winfo_x() + dx
        y = self.win.winfo_y() + dy
        self.win.geometry(f"+{int(x)}+{int(y)}")
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _stop_drag(self, event):
        pass

    def _do_login(self):
        mobile = self._get_mobile()
        pwd = self._get_password()
        if not mobile or not pwd:
            self.status_label.configure(text="请输入手机号和密码")
            return
        self.login_btn.configure(state="disabled", text="登录中...")
        self.status_label.configure(text="正在登录...", fg=COLORS["warning"])
        def _work():
            token, err = api_login_manual(mobile, pwd)
            self.win.after(0, lambda: self._on_result(token, err))
        threading.Thread(target=_work, daemon=True).start()

    def _on_result(self, token, err):
        self.login_btn.configure(state="normal", text="登 录")
        if token:
            self.win.destroy()
            self.callback(token)
        else:
            self.status_label.configure(text=f"登录失败: {err}", fg=COLORS["danger"])

class DeepSeekFloatingWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DeepSeek Token Monitor")
        self.root.configure(bg="black")
        self.root.overrideredirect(True)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.82)

        self.expanded = False
        self._drag_data = {"x": 0, "y": 0}
        self._auth_token = None
        self._last_fetch_time = None
        self._fetching = False
        self._auth_ongoing = False
        self._balance = 0
        self._monthly_usage = 0

        win_w, win_h = 340, 130
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - win_w - 40
        y = screen_h - win_h - 80
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")

        self.monitor = TokenMonitor()
        self.monitor.add_listener(self._on_data_changed)

        self._build_compact()

        # 启动时隐藏主窗口，直接显示登录页
        self.root.withdraw()
        self.root.after(100, self._start_auth)
        self.root.after(1000, self._refresh_status)

    def _frost_frame(self, parent, **kw):
        kw.setdefault("bg", COLORS["bg2"])
        kw.setdefault("bd", 0)
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("highlightcolor", COLORS["border"])
        kw.setdefault("highlightbackground", COLORS["border"])
        return tk.Frame(parent, **kw)

    def _bind_drag_recursive(self, widget, exclude=None):
        """递归绑定拖拽事件到所有子组件，排除交互按钮"""
        if exclude and widget in exclude:
            return
        # 不覆盖已有 Button-1 绑定的交互组件（cursor=hand2 的）
        try:
            cursor = str(widget.cget("cursor"))
        except Exception:
            cursor = ""
        if cursor != "hand2":
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)
            widget.bind("<ButtonRelease-1>", self._stop_drag)
        for child in widget.winfo_children():
            self._bind_drag_recursive(child, exclude)

    def _build_compact(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.container = self._frost_frame(self.root, bg=COLORS["bg2"],
                                            highlightthickness=1,
                                            highlightcolor=COLORS["border"],
                                            highlightbackground=COLORS["border"])
        self.container.pack(fill="both", expand=True)

        top_bar = tk.Frame(self.container, bg=COLORS["bg2"])
        top_bar.pack(fill="x")

        icon_label = tk.Label(top_bar, text="⚡", font=("Segoe UI", 10),
                             fg=COLORS["accent"], bg=COLORS["bg2"])
        icon_label.pack(side="left", padx=(10, 2), pady=6)

        title_label = tk.Label(top_bar, text="DeepSeek", font=("Microsoft YaHei", 9, "bold"),
                               fg=COLORS["accent"], bg=COLORS["bg2"])
        title_label.pack(side="left", pady=6)

        subtitle_label = tk.Label(top_bar, text="Token", font=("Microsoft YaHei", 8),
                                 fg=COLORS["text3"], bg=COLORS["bg2"])
        subtitle_label.pack(side="left", pady=6)

        spacer = tk.Label(top_bar, text="", bg=COLORS["bg2"])
        spacer.pack(side="left", fill="x", expand=True)

        btn_frame = tk.Frame(top_bar, bg=COLORS["bg2"])
        btn_frame.pack(side="right", padx=(0, 6), pady=4)

        self._expand_btn = tk.Label(btn_frame, text="▦", font=("Microsoft YaHei", 9),
                                    fg=COLORS["text3"], bg=COLORS["bg2"], cursor="hand2")
        self._expand_btn.pack(side="right", padx=4)
        self._expand_btn.bind("<Button-1>", lambda e: self._toggle_expand())
        self._expand_btn.bind("<Enter>", lambda e: self._expand_btn.configure(fg=COLORS["accent"]))
        self._expand_btn.bind("<Leave>", lambda e: self._expand_btn.configure(fg=COLORS["text3"]))

        self._theme_btn = tk.Label(btn_frame, text="◐", font=("Microsoft YaHei", 9),
                                   fg=COLORS["text3"], bg=COLORS["bg2"], cursor="hand2")
        self._theme_btn.pack(side="right", padx=4)
        self._theme_btn.bind("<Button-1>", lambda e: self._toggle_theme())
        self._theme_btn.bind("<Enter>", lambda e: self._theme_btn.configure(fg=COLORS["accent"]))
        self._theme_btn.bind("<Leave>", lambda e: self._theme_btn.configure(fg=COLORS["text3"]))

        self._hide_btn = tk.Label(btn_frame, text="✕", font=("Microsoft YaHei", 9),
                                  fg=COLORS["text3"], bg=COLORS["bg2"], cursor="hand2")
        self._hide_btn.pack(side="right", padx=4)
        self._hide_btn.bind("<Button-1>", lambda e: self._quit_app())
        self._hide_btn.bind("<Enter>", lambda e: self._hide_btn.configure(fg=COLORS["danger"]))
        self._hide_btn.bind("<Leave>", lambda e: self._hide_btn.configure(fg=COLORS["text3"]))

        content = tk.Frame(self.container, bg=COLORS["bg2"])
        content.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.summary_frame = tk.Frame(content, bg=COLORS["bg2"])
        self.summary_frame.pack(fill="x")

        self.total_label = tk.Label(self.summary_frame, text="等待登录...",
                                    font=("Microsoft YaHei", 10, "bold"),
                                    fg=COLORS["text"], bg=COLORS["bg2"])
        self.total_label.pack(anchor="w", pady=(2, 1))

        stats_row = tk.Frame(self.summary_frame, bg=COLORS["bg2"])
        stats_row.pack(fill="x", pady=(2, 0))

        self.cached_label = tk.Label(stats_row, text="缓存: -",
                                     font=("Microsoft YaHei", 8), fg=COLORS["success"], bg=COLORS["bg2"])
        self.cached_label.pack(side="left", padx=(0, 10))

        self.uncached_label = tk.Label(stats_row, text="未命中: -",
                                       font=("Microsoft YaHei", 8), fg=COLORS["danger"], bg=COLORS["bg2"])
        self.uncached_label.pack(side="left", padx=(0, 10))

        self.hit_rate_label = tk.Label(stats_row, text="命中率: -",
                                       font=("Microsoft YaHei", 8), fg=COLORS["warning"], bg=COLORS["bg2"])
        self.hit_rate_label.pack(side="left")

        progress_frame = tk.Frame(self.summary_frame, bg=COLORS["bg2"])
        progress_frame.pack(fill="x", pady=(5, 2))

        self.progress_bg = tk.Frame(progress_frame, bg=COLORS["bg4"], height=4, width=300)
        self.progress_bg.pack(fill="x")
        self.progress_bg.pack_propagate(False)

        self.progress_fill = tk.Frame(self.progress_bg, bg=COLORS["success"], height=4, width=0)
        self.progress_fill.pack(side="left")

        self.status_label = tk.Label(content, text="", font=("Microsoft YaHei", 7),
                                     fg=COLORS["text3"], bg=COLORS["bg2"])
        self.status_label.pack(anchor="w", pady=(1, 0))

        self.root.geometry("340x130")

        # 递归绑定拖拽到所有非交互组件
        self._bind_drag_recursive(self.container)

    def _build_expanded(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.container = self._frost_frame(self.root, bg=COLORS["bg2"],
                                            highlightthickness=1,
                                            highlightcolor=COLORS["border"],
                                            highlightbackground=COLORS["border"])
        self.container.pack(fill="both", expand=True)

        top_bar = tk.Frame(self.container, bg=COLORS["bg2"])
        top_bar.pack(fill="x")

        icon_label = tk.Label(top_bar, text="⚡", font=("Segoe UI", 11),
                             fg=COLORS["accent"], bg=COLORS["bg2"])
        icon_label.pack(side="left", padx=(10, 2), pady=7)

        title_label = tk.Label(top_bar, text="DeepSeek", font=("Microsoft YaHei", 10, "bold"),
                               fg=COLORS["accent"], bg=COLORS["bg2"])
        title_label.pack(side="left", pady=7)

        subtitle_label = tk.Label(top_bar, text="Token 监控", font=("Microsoft YaHei", 9),
                                 fg=COLORS["text3"], bg=COLORS["bg2"])
        subtitle_label.pack(side="left", padx=(2, 10), pady=7)

        spacer = tk.Label(top_bar, text="", bg=COLORS["bg2"])
        spacer.pack(side="left", fill="x", expand=True)

        btn_frame = tk.Frame(top_bar, bg=COLORS["bg2"])
        btn_frame.pack(side="right", padx=(0, 6), pady=4)

        self._expand_btn = tk.Label(btn_frame, text="▤", font=("Microsoft YaHei", 9),
                                    fg=COLORS["text3"], bg=COLORS["bg2"], cursor="hand2")
        self._expand_btn.pack(side="right", padx=4)
        self._expand_btn.bind("<Button-1>", lambda e: self._toggle_expand())
        self._expand_btn.bind("<Enter>", lambda e: self._expand_btn.configure(fg=COLORS["accent"]))
        self._expand_btn.bind("<Leave>", lambda e: self._expand_btn.configure(fg=COLORS["text3"]))

        self._theme_btn = tk.Label(btn_frame, text="◐", font=("Microsoft YaHei", 9),
                                   fg=COLORS["text3"], bg=COLORS["bg2"], cursor="hand2")
        self._theme_btn.pack(side="right", padx=4)
        self._theme_btn.bind("<Button-1>", lambda e: self._toggle_theme())
        self._theme_btn.bind("<Enter>", lambda e: self._theme_btn.configure(fg=COLORS["accent"]))
        self._theme_btn.bind("<Leave>", lambda e: self._theme_btn.configure(fg=COLORS["text3"]))

        self._hide_btn = tk.Label(btn_frame, text="✕", font=("Microsoft YaHei", 9),
                                  fg=COLORS["text3"], bg=COLORS["bg2"], cursor="hand2")
        self._hide_btn.pack(side="right", padx=4)
        self._hide_btn.bind("<Button-1>", lambda e: self._quit_app())
        self._hide_btn.bind("<Enter>", lambda e: self._hide_btn.configure(fg=COLORS["danger"]))
        self._hide_btn.bind("<Leave>", lambda e: self._hide_btn.configure(fg=COLORS["text3"]))

        self.main_content = tk.Frame(self.container, bg=COLORS["bg2"])
        self.main_content.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self._build_balance_row(self.main_content)
        self._build_stats_cards(self.main_content)
        self._build_table_area()

        self.status_label = tk.Label(self.main_content, text="", font=("Microsoft YaHei", 7),
                                     fg=COLORS["text3"], bg=COLORS["bg2"])
        self.status_label.pack(anchor="w", pady=(2, 0))

        self.root.geometry("520x300")

        # 递归绑定拖拽到所有非交互组件
        self._bind_drag_recursive(self.container)

    def _get_today_tokens(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        records = self.monitor.get_records()
        for r in records:
            if r.date == today_str:
                return r.total
        return 0

    def _build_balance_row(self, parent):
        balance_frame = tk.Frame(parent, bg=COLORS["accent_light"], bd=0,
                                 highlightthickness=1,
                                 highlightcolor=COLORS["accent"],
                                 highlightbackground=COLORS["accent"])
        balance_frame.pack(fill="x", pady=(4, 6))

        today_tokens = self._get_today_tokens()
        bal_text = f"余额: ¥{_format_num(self._balance)} | 本月消费: ¥{_format_num(self._monthly_usage)} | 今日消耗: {_format_num(today_tokens)} tokens"
        self.balance_label = tk.Label(balance_frame, text=bal_text,
                                      font=("Microsoft YaHei", 9, "bold"),
                                      fg=COLORS["accent"], bg=COLORS["accent_light"])
        self.balance_label.pack(anchor="center", padx=10, pady=5)

    def _build_stats_cards(self, parent):
        card_frame = tk.Frame(parent, bg=COLORS["bg2"])
        card_frame.pack(fill="x", pady=(0, 6))

        stats = self.monitor.get_stats()

        cards = [
            ("总消耗", _format_num(stats["total_all"]), COLORS["accent"], "total"),
            ("缓存命中", _format_num(stats["total_cached"]), COLORS["success"], "cached"),
            ("缓存未命中", _format_num(stats["total_uncached"]), COLORS["danger"], "uncached"),
            ("命中率", f"{stats['hit_rate']:.1f}%", COLORS["warning"], "hit_rate"),
        ]

        self.stat_labels = {}
        for title, value, color, key in cards:
            card = tk.Frame(card_frame, bg=COLORS["card"], bd=0, highlightthickness=2,
                            highlightcolor=COLORS["card_border"],
                            highlightbackground=COLORS["card_border"])
            card.pack(side="left", fill="x", expand=True, padx=3)
            inner = tk.Frame(card, bg=COLORS["bg3"])
            inner.pack(fill="both", expand=True, padx=2, pady=2)
            tk.Label(inner, text=title, font=("Microsoft YaHei", 7),
                     fg=COLORS["text3"], bg=COLORS["bg3"]).pack(pady=(5, 0))
            lbl = tk.Label(inner, text=value, font=("Microsoft YaHei", 11, "bold"),
                           fg=color, bg=COLORS["bg3"])
            lbl.pack(pady=(0, 5))
            self.stat_labels[key] = (lbl, color)

    def _build_table_area(self):
        if hasattr(self, "table_section"):
            self.table_section.destroy()

        self.table_section = tk.Frame(self.main_content, bg=COLORS["bg2"])
        self.table_section.pack(fill="both", expand=True, pady=(0, 0))

        header_frame = tk.Frame(self.table_section, bg=COLORS["bg2"])
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="最近记录", font=("Microsoft YaHei", 8, "bold"),
                 fg=COLORS["text"], bg=COLORS["bg2"]).pack(side="left", pady=(0, 2))

        tree_frame = tk.Frame(self.table_section, bg=COLORS["bg2"])
        tree_frame.pack(fill="both", expand=True)

        cols = ("日期", "缓存命中", "未命中", "总计", "命中率")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Frost.Treeview", background=COLORS["bg3"], foreground=COLORS["text"],
                       fieldbackground=COLORS["bg3"], borderwidth=0, rowheight=24,
                       font=("Microsoft YaHei", 8))
        style.map("Frost.Treeview", background=[("selected", COLORS["accent_light"])],
                  foreground=[("selected", COLORS["accent"])])
        style.configure("Frost.Treeview.Heading", background=COLORS["bg4"], foreground=COLORS["accent"],
                       fieldbackground=COLORS["bg4"], borderwidth=0,
                       font=("Microsoft YaHei", 8, "bold"))
        style.configure("Frost.Vertical.TScrollbar", background=COLORS["border"],
                       troughcolor=COLORS["bg3"], bordercolor=COLORS["bg3"],
                       arrowcolor=COLORS["text3"], relief="flat", width=10, borderwidth=0)
        style.map("Frost.Vertical.TScrollbar",
                  background=[("active", COLORS["border2"]), ("pressed", COLORS["border2"])])
        style.layout("Frost.Vertical.TScrollbar",
                     [("Frost.Vertical.TScrollbar.trough",
                       {"children": [("Frost.Vertical.TScrollbar.thumb", {"sticky": "ns"})],
                        "sticky": "ns"})])

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=6,
                           style="Frost.Treeview")
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=90, anchor="center", minwidth=70)

        records = self.monitor.get_records()
        recent = records[-12:] if len(records) > 12 else records
        for r in reversed(recent):
            self.tree.insert("", "end", values=(
                r.date, _format_num(r.cached), _format_num(r.uncached),
                _format_num(r.total), f"{r.hit_rate:.1f}%"
            ))

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview,
                           style="Frost.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _toggle_expand(self):
        # 记录当前窗口的右下角坐标
        old_x = self.root.winfo_x()
        old_y = self.root.winfo_y()
        old_w = self.root.winfo_width()
        old_h = self.root.winfo_height()
        right = old_x + old_w
        bottom = old_y + old_h

        self.expanded = not self.expanded
        if self.expanded:
            new_w, new_h = 520, 300
            self._build_expanded()
        else:
            new_w, new_h = 340, 130
            self._build_compact()

        # 保持右下角不动，向左上方展开/收缩
        new_x = right - new_w
        new_y = bottom - new_h
        self.root.geometry(f"{new_w}x{new_h}+{int(new_x)}+{int(new_y)}")
        self._update_display()

    def _toggle_theme(self):
        """切换暗色/亮色主题"""
        current = get_current_theme()
        new_theme = "light" if current == "dark" else "dark"
        set_theme(new_theme)
        # 重建当前视图
        if self.expanded:
            self._build_expanded()
        else:
            self._build_compact()
        self._update_display()

    def _start_drag(self, event):
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _do_drag(self, event):
        dx = event.x_root - self._drag_data["x"]
        dy = event.y_root - self._drag_data["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{int(x)}+{int(y)}")
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _stop_drag(self, event):
        pass

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _start_auth(self):
        self._set_status("请登录...", COLORS["warning"])
        self._show_manual_login()

    def _do_login(self):
        if self._auth_ongoing:
            return
        self._auth_ongoing = True
        self._set_status("登录已过期，请重新登录", COLORS["danger"])
        self._show_manual_login()

    def _on_login_success(self, token):
        self._auth_token = token
        self._auth_ongoing = False
        # 确保主窗口可见
        self.root.deiconify()
        self._set_status("登录成功", COLORS["success"])
        self.root.after(500, self._do_fetch)

    def _show_manual_login(self):
        self._auth_ongoing = False
        self._set_status("", COLORS["danger"])
        ManualLoginWindow(self.root, self._on_manual_success, quit_callback=self._quit_app)

    def _on_manual_success(self, token):
        self._auth_token = token
        # 登录成功后显示主窗口
        self.root.deiconify()
        self._set_status("登录成功", COLORS["success"])
        self.root.after(500, self._do_fetch)

    def _do_fetch(self):
        if not self._auth_token or self._fetching:
            return
        self._fetching = True
        self._set_status("获取数据中...", COLORS["warning"])
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            data, err = api_fetch_usage(self._auth_token)
            if err == "token_expired":
                self._auth_token = None
                self.root.after(0, self._do_login)
                return
            if not err:
                records = parse_usage_response(data)
                if records:
                    self.monitor.set_records(records)

            summary_data, summary_err = api_fetch_summary(self._auth_token)
            if summary_err == "token_expired":
                self._auth_token = None
                self.root.after(0, self._do_login)
                return
            if not summary_err and summary_data:
                info = parse_summary_response(summary_data)
                self._balance = info.get("balance", 0)
                self._monthly_usage = info.get("monthly_usage", 0)
                self.monitor.set_extra_info(info)

            self._last_fetch_time = datetime.now()
            self.root.after(0, lambda: self._set_status(
                f"更新于 {self._last_fetch_time.strftime('%H:%M:%S')}", COLORS["text3"]))
            self.root.after(0, self._update_display)
        finally:
            self._fetching = False
        self.root.after(60000, self._do_fetch)

    def _set_status(self, text, color=None):
        if hasattr(self, "status_label"):
            self.status_label.configure(text=text)
            if color:
                self.status_label.configure(fg=color)

    def _refresh_status(self):
        if self._last_fetch_time:
            elapsed = int((datetime.now() - self._last_fetch_time).total_seconds())
            if elapsed < 60:
                self._set_status(f"更新于 {self._last_fetch_time.strftime('%H:%M:%S')}", COLORS["text3"])
        self.root.after(5000, self._refresh_status)

    def _on_data_changed(self):
        self.root.after(0, self._update_display)

    def _update_display(self):
        if self.expanded:
            today_tokens = self._get_today_tokens()
            bal_text = f"余额: ¥{_format_num(self._balance)} | 本月消费: ¥{_format_num(self._monthly_usage)} | 今日消耗: {_format_num(today_tokens)} tokens"
            if hasattr(self, "balance_label"):
                self.balance_label.configure(text=bal_text)
            stats = self.monitor.get_stats()
            if hasattr(self, "stat_labels"):
                vals = {
                    "total": _format_num(stats["total_all"]),
                    "cached": _format_num(stats["total_cached"]),
                    "uncached": _format_num(stats["total_uncached"]),
                    "hit_rate": f"{stats['hit_rate']:.1f}%",
                }
                for key, (lbl, color) in self.stat_labels.items():
                    lbl.configure(text=vals.get(key, "-"))
            self._build_table_area()
            return

        stats = self.monitor.get_stats()
        if stats["count"] > 0:
            today_tokens = self._get_today_tokens()
            self.total_label.configure(text=f"本月总消耗: {_format_num(stats['total_all'])} tokens | 今日消耗: {_format_num(today_tokens)} tokens")
            self.cached_label.configure(text=f"缓存: {_format_num(stats['total_cached'])}")
            self.uncached_label.configure(text=f"未命中: {_format_num(stats['total_uncached'])}")
            self.hit_rate_label.configure(text=f"命中率: {stats['hit_rate']:.1f}%")

            pct = stats["hit_rate"] / 100
            self.progress_fill.configure(width=int(300 * pct))
            if pct > 0.6:
                self.progress_fill.configure(bg=COLORS["success"])
            elif pct > 0.3:
                self.progress_fill.configure(bg=COLORS["warning"])
            else:
                self.progress_fill.configure(bg=COLORS["danger"])
        else:
            self.total_label.configure(text="等待数据...")
            self.cached_label.configure(text="缓存: -")
            self.uncached_label.configure(text="未命中: -")
            self.hit_rate_label.configure(text="命中率: -")
            self.progress_fill.configure(width=0)

    def _quit_app(self):
        try:
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def run(self):
        self.root.mainloop()

def main():
    widget = DeepSeekFloatingWidget()
    if HAS_KEYBOARD:
        def _show():
            widget.root.after(0, widget._show_window)
        try:
            _kb.add_hotkey("ctrl+shift+d", _show)
        except Exception:
            pass
    widget.run()

if __name__ == "__main__":
    main()
