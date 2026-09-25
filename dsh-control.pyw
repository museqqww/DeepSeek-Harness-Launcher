# -*- coding: utf-8 -*-
"""DSH 服务控制器 —— 启动/关闭/开机自启/打开网页/浏览器设定
UI 配色取自 DeepSeek Harness 前端设计 token（dsh-web-frontend/dist）
"""

import json
import os
import re
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox, filedialog

# 自定位：脚本放在哪个目录，就管理哪个目录里的 dsh 服务。
# 这样整个文件夹拷到别的电脑、别的盘符都不用改代码。
try:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:  # 极端情况（如被打包）退回当前工作目录
    APP_DIR = os.getcwd()
SCRIPT_FILE = os.path.join(APP_DIR, "dsh-control.pyw")
LOG_FILE = os.path.join(APP_DIR, "dsh-web.log")
CONFIG_FILE = os.path.join(APP_DIR, "dsh-control-config.json")
ICON_FILE = os.path.join(APP_DIR, "dsh-icon.ico")
ICON_URL = "https://www.deepseek.com/favicon.ico"
PORT = 3080
CREATE_NO_WINDOW = 0x08000000

STARTUP_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup",
)
AUTOSTART_VBS = os.path.join(STARTUP_DIR, "DSH-Autostart.vbs")
SHORTCUT_NAME = "DeepSeek Harness 控制器"

# ---- DeepSeek Harness 浅色配色（--dsh-boot-bg:#fff / --dsh-boot-brand:#0f1115）----
BG = "#FFFFFF"
CARD = "#F7F8FA"
BORDER = "#E1E4E8"
TEXT = "#0F1115"
TEXT_DIM = "#6B7280"
ACCENT = "#4D6BFE"
ACCENT_H = "#3D5BEE"
OK = "#30A46C"
OFF = "#9AA0A6"
LINK = "#3B5BDB"
BTN = "#FFFFFF"
BTN_H = "#F0F1F4"
DIS_FG = "#B0B4BC"
DIS_BG = "#F2F3F5"
DIS_ACCENT = "#C7D2FE"

FONT = ("Microsoft YaHei", 10)
FONT_SM = ("Microsoft YaHei", 8)
FONT_BOLD = ("Microsoft YaHei", 10, "bold")
FONT_TITLE = ("Microsoft YaHei", 13, "bold")
MONO = ("Consolas", 9)

CANDIDATE_BROWSERS = [
    ("Google Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ("Google Chrome (x86)", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ("Microsoft Edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ("Microsoft Edge (x64)", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ("Mozilla Firefox", r"C:\Program Files\Mozilla Firefox\firefox.exe"),
]

URL_RE = re.compile(r"http://127\.0\.0\.1:\d+/\?token=\S+")


# ---------------- 配置 ----------------

def load_config():
    cfg = {"browser": "", "autostart": False}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        messagebox.showerror("保存失败", str(e))
        return False


# ---------------- 服务控制 ----------------

def get_pid():
    try:
        out = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10,
            encoding="gbk", errors="ignore",
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        return None
    for line in out.stdout.splitlines():
        if (":%d" % PORT) in line and "LISTENING" in line.upper():
            parts = line.split()
            if parts and parts[-1].isdigit():
                return parts[-1]
    return None


def read_url():
    if not os.path.exists(LOG_FILE):
        return None
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except Exception:
        return None
    m = URL_RE.search(txt)
    return m.group(0).strip() if m else None


def launch_service():
    """启动 dsh web 服务。成功返回 Popen 句柄（供调用方判断进程是否存活），
    端口已被占用时返回 None。"""
    if get_pid():
        return None
    try:
        fh = open(LOG_FILE, "w", encoding="utf-8")
    except Exception as e:
        messagebox.showerror("无法写日志", str(e))
        return None
    try:
        return subprocess.Popen(
            ["cmd", "/c", r"node_modules\.bin\dsh.cmd", "web", "--no-open"],
            cwd=APP_DIR,
            stdout=fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as e:
        messagebox.showerror("启动失败", str(e))
        return None


def kill_service(pid):
    """/T 连同子进程树一起杀（netstat 看到的监听 PID 是 node，
    它上面可能还挂着 cmd 包装进程、下面可能有子进程）。"""
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, creationflags=CREATE_NO_WINDOW,
        )
        return True
    except Exception:
        return False


# ---------------- 开机自启 ----------------

VBS_TEMPLATE = """Set ws = CreateObject("WScript.Shell")
ws.CurrentDirectory = "%s"
ws.Run "cmd /c node_modules\\.bin\\dsh.cmd web --no-open > dsh-web.log 2>&1", 0, False
"""


def is_autostart_on():
    return os.path.exists(AUTOSTART_VBS)


def set_autostart(enabled):
    try:
        if enabled:
            os.makedirs(STARTUP_DIR, exist_ok=True)
            with open(AUTOSTART_VBS, "w", encoding="ascii") as f:
                f.write(VBS_TEMPLATE % APP_DIR.replace("\\", "\\\\"))
        else:
            if os.path.exists(AUTOSTART_VBS):
                os.remove(AUTOSTART_VBS)
        return True
    except Exception as e:
        messagebox.showerror("设置失败", str(e))
        return False


# ---------------- 浏览器 ----------------

def detect_browsers():
    found = []
    for name, path in CANDIDATE_BROWSERS:
        if os.path.exists(path):
            found.append((name, path))
    return found


def open_in_browser(browser_path, url):
    if browser_path and os.path.exists(browser_path):
        try:
            subprocess.Popen([browser_path, url], creationflags=CREATE_NO_WINDOW)
            return True
        except Exception:
            pass
    webbrowser.open(url)
    return True


# ---------------- 图标（可选） ----------------

def ensure_icon(timeout=10):
    """图标文件不存在时，从 DeepSeek 官网下载 favicon。
    仓库不内置官方图标（避免直接分发第三方商标素材），需要时现取。
    失败也不影响功能，只是窗口/快捷方式用默认图标。"""
    if os.path.exists(ICON_FILE):
        return True, ICON_FILE
    try:
        import urllib.request
        data = urllib.request.urlopen(ICON_URL, timeout=timeout).read()
        if not data:
            return False, "下载为空"
        with open(ICON_FILE, "wb") as f:
            f.write(data)
        return True, ICON_FILE
    except Exception as e:
        return False, str(e)


# ---------------- 开始菜单快捷方式（换机后一键重建） ----------------

def make_shortcut():
    """在当前电脑的开始菜单生成/重建带 DeepSeek 图标的快捷方式。
    pythonw.exe 路径按当前解释器推导，不写死用户名。"""
    exe = sys.executable or ""
    if exe.lower().endswith("python.exe"):
        exe = os.path.join(os.path.dirname(exe), "pythonw.exe")
    start_menu = os.path.join(
        os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")

    ensure_icon()  # 尽力补图标；失败也只是用默认图标

    try:
        # 优先用随包放在同目录的 pylnk3.py（零依赖、只吃标准库），
        # 这样换电脑后把整个文件夹拷过去就能用，不用再装任何库。
        if APP_DIR not in sys.path:
            sys.path.insert(0, APP_DIR)
        from pylnk3 import for_file
        lnk = os.path.join(start_menu, SHORTCUT_NAME + ".lnk")
        for_file(exe, lnk_name=lnk,
                 arguments='"%s"' % SCRIPT_FILE,
                 description="DeepSeek Harness 服务控制器",
                 icon_file=ICON_FILE, icon_index=0,
                 work_dir=APP_DIR, window_mode="Normal")
        return True, lnk
    except ImportError:
        # 没有 pylnk3 → 退化成 .url 快捷方式（同样带图标、可双击打开）
        try:
            from urllib.parse import quote
            url_file = os.path.join(start_menu, SHORTCUT_NAME + ".url")
            with open(url_file, "w", encoding="utf-8") as f:
                f.write("[InternetShortcut]\r\n")
                f.write("URL=file:///%s\r\n"
                        % quote(SCRIPT_FILE.replace("\\", "/")))
                f.write("IconIndex=0\r\n")
                f.write("IconFile=%s\r\n" % ICON_FILE)
            return True, url_file
        except Exception as e:
            return False, str(e)
    except Exception as e:
        return False, str(e)


# ---------------- GUI ----------------

class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.detected = detect_browsers()
        self.wait_ticks = 0
        self.current_url = None
        self.starting = False
        self.proc = None          # 本次控制器启动的服务进程句柄

        root.title("DSH 服务控制器")
        root.geometry("600x600")
        root.resizable(False, False)
        root.configure(bg=BG)

        if os.path.exists(ICON_FILE):
            try:
                root.iconbitmap(ICON_FILE)
            except Exception:
                pass

        self._init_ttk_style()
        self._build_header()
        self._build_status()
        self._build_actions()
        self._build_settings()
        self._build_footer()

        self.refresh()
        self.poll()

    def _init_ttk_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("TCombobox",
                     fieldbackground=CARD, background=CARD,
                     foreground=TEXT, arrowcolor=TEXT,
                     bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD,
                     insertcolor=TEXT, padding=4)
        st.map("TCombobox",
               fieldbackground=[("readonly", CARD)],
               foreground=[("readonly", TEXT)],
               background=[("readonly", CARD)])

    def _card(self, title):
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="x", padx=16, pady=5)
        tk.Label(wrap, text=title, font=FONT_SM, fg=TEXT_DIM, bg=BG).pack(
            anchor="w", pady=(0, 4))
        body = tk.Frame(wrap, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        body.pack(fill="x")
        inner = tk.Frame(body, bg=CARD)
        inner.pack(fill="x", padx=14, pady=12)
        return inner

    def _btn(self, parent, text, cmd, primary=False, width=12):
        b = tk.Button(parent, text=text, font=FONT, width=width,
                      command=cmd, cursor="hand2",
                      bg=ACCENT if primary else BTN,
                      fg="#FFFFFF" if primary else TEXT,
                      activebackground=ACCENT_H if primary else BTN_H,
                      activeforeground="#FFFFFF" if primary else TEXT,
                      disabledforeground="#FFFFFF" if primary else DIS_FG,
                      relief="flat", bd=0, highlightthickness=0,
                      padx=8, pady=7)
        b._primary = primary
        return b

    def _set_enabled(self, btn, enabled):
        """置灰/恢复按钮（tk 不支持 disabledbackground，需手动改 bg）"""
        primary = getattr(btn, "_primary", False)
        if enabled:
            btn.config(state="normal",
                       bg=ACCENT if primary else BTN,
                       fg="#FFFFFF" if primary else TEXT,
                       cursor="hand2")
        else:
            btn.config(state="disabled",
                       bg=DIS_ACCENT if primary else DIS_BG,
                       fg="#FFFFFF" if primary else DIS_FG,
                       cursor="arrow")

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(hdr, text="DSH 服务控制器", font=FONT_TITLE,
                 fg=TEXT, bg=BG).pack(side="left")
        tk.Label(hdr, text="DeepSeek Harness", font=FONT_SM,
                 fg=TEXT_DIM, bg=BG).pack(side="right", pady=(6, 0))

    def _build_status(self):
        box = self._card("服务状态")

        self.status_var = tk.StringVar(value="检测中…")
        self.status_label = tk.Label(box, textvariable=self.status_var,
                                     font=FONT_TITLE, fg=TEXT, bg=CARD)
        self.status_label.pack(anchor="w")

        self.pid_var = tk.StringVar(value="PID: -")
        tk.Label(box, textvariable=self.pid_var, font=FONT_SM,
                 fg=TEXT_DIM, bg=CARD).pack(anchor="w", pady=(3, 0))

        sep = tk.Frame(box, bg=BORDER, height=1)
        sep.pack(fill="x", pady=10)

        tk.Label(box, text="访问地址", font=FONT_SM, fg=TEXT_DIM,
                 bg=CARD).pack(anchor="w")
        self.url_var = tk.StringVar(value="（未获取）")
        tk.Label(box, textvariable=self.url_var, font=MONO,
                 fg=LINK, bg=CARD, wraplength=520,
                 justify="left").pack(anchor="w", pady=(3, 0))

    def _build_actions(self):
        box = self._card("操作")

        grid = tk.Frame(box, bg=CARD)
        grid.pack(fill="x")

        self.btn_start = self._btn(grid, "打开服务", self.on_start)
        self.btn_start.grid(row=0, column=0, padx=(0, 8))
        self.btn_stop = self._btn(grid, "关闭服务", self.on_stop)
        self.btn_stop.grid(row=0, column=1, padx=(0, 8))
        self.btn_web = self._btn(grid, "打开网页", self.on_open_web,
                                 primary=True, width=14)
        self.btn_web.grid(row=0, column=2)

        tk.Label(box,
                 text="· “打开网页”会先嗅探服务：已运行 → 直接打开；"
                      "未运行 → 先启动再打开。不会重启或关闭服务。\n"
                      "· 三个按钮随时可点：状态不对时会弹提示，不会静默无反应。",
                 font=FONT_SM, fg=TEXT_DIM, bg=CARD,
                 wraplength=520, justify="left").pack(anchor="w", pady=(10, 0))

    def _build_settings(self):
        box = self._card("设置（自动保存）")

        tk.Label(box, text="浏览器", font=FONT, fg=TEXT, bg=CARD).grid(
            row=0, column=0, sticky="w")
        self.browser_var = tk.StringVar()
        values = ["%s  (%s)" % (n, p) for n, p in self.detected]
        self.browser_combo = ttk.Combobox(box, textvariable=self.browser_var,
                                          values=values, width=40,
                                          state="readonly")
        self.browser_combo.grid(row=0, column=1, columnspan=2,
                                sticky="w", padx=(10, 0))

        cur = self.cfg.get("browser", "")
        if cur:
            self.browser_var.set(cur)
        elif self.detected:
            self.browser_var.set("%s  (%s)" % (self.detected[0][0],
                                               self.detected[0][1]))

        tk.Button(box, text="浏览…", font=FONT_SM, width=8,
                  command=self.on_pick_browser, cursor="hand2",
                  bg=BTN, fg=TEXT, activebackground=BTN_H,
                  activeforeground=TEXT, relief="flat", bd=0,
                  highlightthickness=0, pady=5).grid(
            row=0, column=3, padx=(8, 0))

        sep = tk.Frame(box, bg=BORDER, height=1)
        sep.grid(row=1, column=0, columnspan=4, sticky="ew", pady=12)

        self.auto_var = tk.BooleanVar(value=is_autostart_on())
        tk.Checkbutton(box, text="开机自动启动服务（长期加载）",
                       font=FONT, variable=self.auto_var,
                       command=self.on_toggle_autostart,
                       bg=CARD, fg=TEXT, selectcolor=BG,
                       activebackground=CARD, activeforeground=TEXT,
                       highlightthickness=0, bd=0).grid(
            row=2, column=0, columnspan=4, sticky="w")

    def _build_footer(self):
        frm = tk.Frame(self.root, bg=BG)
        frm.pack(fill="x", padx=16, pady=(10, 16))
        self._btn(frm, "保存设置", self.on_save, width=11).pack(side="left")
        self._btn(frm, "重建快捷方式", self.on_mkshortcut, width=13).pack(
            side="left", padx=(8, 0))
        self.tip_var = tk.StringVar(value="")
        tk.Label(frm, textvariable=self.tip_var, font=FONT_SM,
                 fg=OK, bg=BG).pack(side="left", padx=(12, 0))

    # --- 逻辑 ---
    def browser_path(self):
        raw = self.browser_var.get().strip()
        m = re.search(r"\((.+?)\)\s*$", raw)
        if m:
            return m.group(1)
        return raw

    def refresh(self):
        pid = get_pid()
        if pid:
            self.status_var.set("● 服务运行中")
            self.status_label.config(fg=OK)
            self.pid_var.set("PID: %s    端口: %d" % (pid, PORT))
            # 日志优先：服务重启后 token 会变，内存里缓存的旧 token 会失效
            url = read_url() or self.current_url
            if url:
                self.current_url = url
                self.url_var.set(url)
            else:
                self.url_var.set("（读取中或日志无记录）")
        else:
            self.status_var.set("○ 服务已停止")
            self.status_label.config(fg=OFF)
            self.pid_var.set("PID: -")
            self.url_var.set("（未运行）")
            self.current_url = None
        return pid

    def poll(self):
        pid = self.refresh()
        # 按钮始终可点击（仅在“启动中”的短暂过程里置灰），
        # 无效操作会弹出明确提示，避免看起来“点了没反应”。
        busy = self.starting
        self._set_enabled(self.btn_start, not busy)
        self._set_enabled(self.btn_stop, not busy)
        self._set_enabled(self.btn_web, not busy)
        if busy:
            self.status_var.set("正在启动… %d 秒" % self.wait_ticks)
        self.root.after(2500, self.poll)

    def on_start(self):
        if self.starting:
            return
        if get_pid():
            messagebox.showinfo("提示", "服务已在运行中。")
            return
        proc = launch_service()
        if proc:
            self.proc = proc
            self.starting = True
            self.current_url = None
            self.wait_ticks = 0
            self.status_var.set("正在启动… 0 秒")
            self.tip_var.set("服务启动中，就绪后状态会自动变绿")
            self.root.after(1500, lambda: self._wait_ready(False))

    def on_stop(self):
        if self.starting:
            messagebox.showinfo("提示", "服务正在启动中，请稍候再操作。")
            return
        pid = get_pid()
        if not pid:
            messagebox.showinfo("提示", "服务当前未运行。")
            return
        if kill_service(pid):
            self.proc = None
            self.status_var.set("○ 服务已停止")
            self.tip_var.set("服务已关闭")
            self.root.after(800, self.refresh)

    def on_open_web(self):
        if self.starting:
            messagebox.showinfo("提示", "服务正在启动中，就绪后会自动打开网页。")
            return
        pid = get_pid()
        if pid:
            url = read_url() or self.current_url
            if url:
                self.current_url = url
                open_in_browser(self.browser_path(), url)
                self.tip_var.set("已在浏览器中打开")
            else:
                messagebox.showwarning(
                    "无法获取链接",
                    "服务正在运行，但读取不到访问链接。\n\n"
                    "说明：token 只在服务启动那一刻生成并写入日志，\n"
                    "若启动时的日志已丢失（例如重复启动被覆盖），无法找回。\n\n"
                    "恢复方法：点“关闭服务”，再点“打开服务”，即可重新拿到链接。",
                )
            return
        proc = launch_service()
        if proc:
            self.proc = proc
            self.starting = True
            self.current_url = None
            self.wait_ticks = 0
            self.status_var.set("正在启动… 0 秒")
            self.tip_var.set("启动中，就绪后自动打开网页")
            self.root.after(1500, lambda: self._wait_ready(True))

    def _wait_ready(self, open_browser):
        """等待服务就绪。open_browser=True 时就绪后自动打开网页。
        就绪判定：日志里出现带 token 的 URL（服务真正可访问的标志）。
        ⚠️ 失败判定不能用「端口还没监听」——dsh 启动要好几秒才绑定 3080，
        那段时间 get_pid() 本来就是 None，会造成“正在启动却被判失败”。
        只认「我们启动的进程本身已经退出」。"""
        self.wait_ticks += 1
        url = read_url()
        if url:
            self.starting = False
            self.current_url = url
            self.status_var.set("● 服务运行中")
            if open_browser:
                open_in_browser(self.browser_path(), url)
                self.tip_var.set("已打开网页")
            else:
                self.tip_var.set("服务已就绪，可点「打开网页」")
            return
        proc_dead = self.proc is not None and self.proc.poll() is not None
        if proc_dead and not get_pid() and self.wait_ticks >= 8:
            self.starting = False
            tail = ""
            try:
                with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    tail = f.read()[-500:]
            except Exception:
                pass
            self.status_var.set("○ 启动失败")
            messagebox.showerror(
                "启动失败",
                "服务进程已退出且未生成访问链接。\n\n"
                "dsh-web.log 末尾内容：\n%s" % (tail or "（日志为空）"),
            )
            return
        if self.wait_ticks > 90:
            self.starting = False
            self.status_var.set("○ 启动超时")
            messagebox.showerror("超时", "服务启动超过 90 秒，请查看 dsh-web.log。")
            return
        self.root.after(1000, lambda: self._wait_ready(open_browser))

    def on_pick_browser(self):
        path = filedialog.askopenfilename(
            title="选择浏览器程序",
            filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")],
        )
        if path:
            self.browser_var.set(path)
            self.cfg["browser"] = path
            save_config(self.cfg)
            self.tip_var.set("浏览器已保存")

    def on_toggle_autostart(self):
        ok = set_autostart(self.auto_var.get())
        if ok:
            self.cfg["autostart"] = self.auto_var.get()
            save_config(self.cfg)
            self.tip_var.set("已%s开机自启" % ("开启" if self.auto_var.get() else "关闭"))

    def on_save(self):
        self.cfg["browser"] = self.browser_path()
        self.cfg["autostart"] = self.auto_var.get()
        if save_config(self.cfg):
            self.tip_var.set("设置已保存")

    def on_mkshortcut(self):
        """换电脑/换目录后，重建开始菜单快捷方式（图标 + 正确的 pythonw 路径）"""
        ok, info = make_shortcut()
        if ok:
            self.tip_var.set("快捷方式已重建")
            messagebox.showinfo("快捷方式已重建",
                                "开始菜单已生成：\n%s\n\n"
                                "开始菜单里搜“DeepSeek”即可找到。"
                                % info)
        else:
            messagebox.showerror("创建失败", str(info))


def main():
    # 命令行用法：python dsh-control.pyw --mkshortcut
    # 换电脑后跑一次，自动在新电脑的开始菜单重建快捷方式（含图标）
    if "--mkicon" in [a.lower() for a in sys.argv[1:]]:
        ok, info = ensure_icon()
        print("图标就绪：" + info if ok else "图标获取失败：" + str(info))
        return

    if "--mkshortcut" in [a.lower() for a in sys.argv[1:]]:
        ok, info = make_shortcut()
        title = "快捷方式已重建" if ok else "创建失败"
        msg = info if ok else str(info)
        try:
            root = tk.Tk()
            root.withdraw()
            if ok:
                messagebox.showinfo(title, "已创建开始菜单快捷方式：\n" + msg)
            else:
                messagebox.showerror(title, msg)
            root.destroy()
        except Exception:
            print(title, ":", msg)
        return

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
