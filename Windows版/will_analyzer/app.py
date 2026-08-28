# -*- coding: utf-8 -*-
"""意志图谱 —— 图形界面（重构版）。

tkinter + ttk 实现，包含欢迎页、答题页、校验页与结果报告页。

视觉原则：
- 温暖纸张底色 + 墨色正文 + 青绿结构色 + 琥珀高光 + 珊瑚警示 + 靛蓝反思
- 标题与意志名使用衬线字体，正文使用黑体
- 全宽内容、可纵向滚动、正文不因容器边界被截断
"""

import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox
from datetime import datetime

from will_analyzer.data.questions import (
    LIKERT_SCALE, LIKERT_QUESTIONS, CHOICE_QUESTIONS, VALIDATION_QUESTIONS,
)
from will_analyzer.data import dimensions as D
from will_analyzer.engine.scoring import score, extract_profile, set_choices, detect_tensions
from will_analyzer.engine.generator import generate


def _enable_dpi_awareness():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_enable_dpi_awareness()

# ---------------------------------------------------------------------------
# 配色：温暖纸张 + 结构化语义色
# ---------------------------------------------------------------------------
C = {
    "bg": "#f6f3ed",
    "surface": "#fffdf8",
    "surface_strong": "#ffffff",
    "ink": "#25231f",
    "soft": "#6e695f",
    "border": "#ded8cc",

    "teal": "#246b65",
    "teal_soft": "#dcece7",
    "teal_deep": "#174a46",

    "amber": "#b97928",
    "amber_soft": "#f3e2bd",

    "coral": "#bd5f4b",
    "coral_soft": "#f4ded7",

    "indigo": "#575d8f",
    "indigo_soft": "#e4e5f1",
}

# ---------------------------------------------------------------------------
# 字体
# ---------------------------------------------------------------------------
_SANS_CANDIDATES = ["Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI"]
_SERIF_CANDIDATES = ["Noto Serif SC", "Source Han Serif SC", "STZhongsong", "SimSun", "KaiTi"]
_families = None
_font_cache = {}


def _fam_set():
    global _families
    if _families is None:
        try:
            _families = set(tkfont.families())
        except Exception:
            _families = set()
    return _families


def _sans_family():
    for c in _SANS_CANDIDATES:
        if c in _fam_set():
            return c
    return "Microsoft YaHei UI"


def _serif_family():
    for c in _SERIF_CANDIDATES:
        if c in _fam_set():
            return c
    return "SimSun"


def F(size=11, weight="normal", serif=False):
    family = _serif_family() if serif else _sans_family()
    key = (family, size, weight)
    if key not in _font_cache:
        _font_cache[key] = tkfont.Font(family=family, size=size, weight=weight)
    return _font_cache[key]


def _desktop_dir():
    """返回真实的桌面目录（兼容 OneDrive 重定向）。"""
    try:
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 16, None, 0, buf)
        p = buf.value
        if p and os.path.isdir(p):
            return p
    except Exception:
        pass
    for p in (os.path.join(os.path.expanduser("~"), "Desktop"),
              os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")):
        if os.path.isdir(p):
            return p
    return os.path.expanduser("~")


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------
class WillApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("意志图谱 · 叙事型人格探索")
        self.geometry("1240x820")
        self.minsize(900, 640)
        self.configure(bg=C["bg"])

        self.answers = {}
        self.validation = {}
        self._setup_style()
        self._build_header()

        self.container = tk.Frame(self, bg=C["bg"])
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.pages = {}
        for Page in (WelcomePage, QuestionPage, ValidationPage, ResultPage):
            page = Page(self.container, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[Page.__name__] = page

        self.current_page_name = ""
        self.show_page("WelcomePage")

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TProgressbar", troughcolor=C["border"],
                        background=C["teal"], bordercolor=C["border"],
                        lightcolor=C["teal"], darkcolor=C["teal"])

    def _build_header(self):
        header = tk.Frame(self, bg=C["bg"])
        header.pack(fill="x")
        inner = tk.Frame(header, bg=C["bg"])
        inner.pack(fill="x", padx=48, pady=(22, 4))
        tk.Label(inner, text="意志图谱", font=F(15, "bold", serif=True),
                 bg=C["bg"], fg=C["teal_deep"]).pack(side="left")
        tk.Label(inner, text="叙事型人格探索", font=F(9),
                 bg=C["bg"], fg=C["soft"]).pack(side="left", padx=(12, 0))
        tk.Label(inner, text="本地模式 · 数据不出本机", font=F(9),
                 bg=C["bg"], fg=C["amber"]).pack(side="right")

    def show_page(self, name):
        self.current_page_name = name
        page = self.pages[name]
        page.on_show()
        page.tkraise()

    def start_test(self):
        self.answers = {}
        self.pages["QuestionPage"].reset()
        self.show_page("QuestionPage")

    def show_results(self):
        page = self.pages["ResultPage"]
        page.render(self.answers)
        self.show_page("ResultPage")


def _flat_button(parent, text, bg, fg, font, command=None, padx=22, pady=12,
                 state="normal", active_bg=None, active_fg=None):
    b = tk.Button(parent, text=text, font=font, bg=bg, fg=fg,
                  relief="flat", bd=0, highlightthickness=0,
                  activebackground=active_bg or bg, activeforeground=active_fg or fg,
                  cursor="hand2", padx=padx, pady=pady, command=command, state=state)
    return b


# ---------------------------------------------------------------------------
# 欢迎页
# ---------------------------------------------------------------------------
class WelcomePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._build()

    def _build(self):
        inner = tk.Frame(self, bg=C["bg"])
        inner.pack(fill="x", padx=80, pady=(64, 40))

        tk.Label(inner, text="叙事型人格探索", font=F(11, "bold"),
                 bg=C["bg"], fg=C["amber"]).pack(anchor="w")
        tk.Label(inner, text="看见你在选择背后\n反复保护的东西。",
                 font=F(34, "bold", serif=True), bg=C["bg"], fg=C["ink"],
                 justify="left").pack(anchor="w", pady=(14, 18))

        tk.Label(inner, text="每个人都有最难割舍的渴望、最不愿触碰的恐惧，"
                             "以及一套在漫长生活里反复使用的行为方式。",
                 font=F(13), bg=C["bg"], fg=C["soft"], justify="left",
                 wraplength=self._wrap()).pack(anchor="w")

        tk.Label(inner, text="「意志」不是某个具体目标，而是这些深层需求、恐惧与行动逻辑的精炼——"
                             "它折射出你的性格底色，也会随经历不断变化。",
                 font=F(12), bg=C["bg"], fg=C["ink"], justify="left",
                 wraplength=self._wrap()).pack(anchor="w", pady=(12, 0))

        # 四个特征卡
        features = [
            ("01", "核心需要", "你最想从世界获得什么"),
            ("02", "价值冲突", "两难时你最终保护什么"),
            ("03", "行动法则", "趋近 · 拒绝 · 冲突 · 复归"),
            ("04", "压力变体", "你的阴影与成长方向"),
        ]
        grid = tk.Frame(inner, bg=C["bg"])
        grid.pack(fill="x", pady=(34, 0))
        for i in range(4):
            grid.grid_columnconfigure(i, weight=1, uniform="feat")
        for i, (num, title, desc) in enumerate(features):
            card = tk.Frame(grid, bg=C["surface"], highlightbackground=C["border"],
                            highlightthickness=1)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0 if i == 3 else 8))
            tk.Label(card, text=num, font=F(9, "bold"), bg=C["surface"],
                     fg=C["amber"]).pack(anchor="w", padx=18, pady=(16, 2))
            tk.Label(card, text=title, font=F(12, "bold"), bg=C["surface"],
                     fg=C["teal_deep"]).pack(anchor="w", padx=18)
            tk.Label(card, text=desc, font=F(9), bg=C["surface"], fg=C["soft"],
                     justify="left", wraplength=150).pack(anchor="w", padx=18, pady=(4, 16))

        tk.Label(inner, text="它不是心理诊断，而是一套可解释、可修订的自我叙事。",
                 font=F(10), bg=C["bg"], fg=C["teal"]).pack(anchor="w", pady=(28, 20))

        _flat_button(inner, text="开始探索", bg=C["amber"], fg=C["surface_strong"],
                     font=F(13, "bold"), active_bg=C["teal_deep"],
                     command=self.app.start_test, padx=36, pady=14).pack(anchor="w")
        tk.Label(inner, text="52 题 · 约 12 分钟 · 可中途退出",
                 font=F(9), bg=C["bg"], fg=C["soft"]).pack(anchor="w", pady=(10, 0))

    def _wrap(self):
        return max(560, self.app.winfo_width() - 200)

    def on_show(self):
        pass


# ---------------------------------------------------------------------------
# 答题页
# ---------------------------------------------------------------------------
class QuestionPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.all_questions = LIKERT_QUESTIONS + CHOICE_QUESTIONS
        self.index = 0
        self._option_buttons = []
        self._build()
        self._bind_keys()

    def _build(self):
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=48, pady=(22, 0))
        self.stage = tk.Label(top, text="", font=F(10, "bold"), bg=C["bg"], fg=C["soft"])
        self.stage.pack(side="left")
        self.count = tk.Label(top, text="", font=F(11, "bold"), bg=C["bg"], fg=C["amber"])
        self.count.pack(side="right")

        self.progress = ttk.Progressbar(self, maximum=len(self.all_questions), value=0)
        self.progress.pack(fill="x", padx=48, pady=(10, 0))

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=48, pady=(16, 8))

        self.qnum = tk.Label(body, text="", font=F(10, "bold"), bg=C["bg"], fg=C["amber"])
        self.qnum.pack(anchor="w")
        self.qtext = tk.Label(body, text="", font=F(16, "bold"), bg=C["bg"], fg=C["ink"],
                              justify="left", anchor="w")
        self.qtext.pack(anchor="w", fill="x", pady=(14, 6))
        self.hint = tk.Label(body, text="", font=F(9), bg=C["bg"], fg=C["soft"],
                             justify="left", anchor="w")
        self.hint.pack(anchor="w", fill="x")
        self.option_area = tk.Frame(body, bg=C["bg"])
        self.option_area.pack(fill="both", expand=True, pady=(20, 0))

        bottom = tk.Frame(self, bg=C["bg"])
        bottom.pack(fill="x", padx=48, pady=(0, 30))
        self.key_hint = tk.Label(bottom, text="", font=F(9), bg=C["bg"], fg=C["soft"])
        self.key_hint.pack(anchor="center", pady=(0, 12))
        btns = tk.Frame(bottom, bg=C["bg"])
        btns.pack(fill="x")
        self.back_btn = _flat_button(btns, text="‹ 上一题", bg=C["surface"], fg=C["ink"],
                                     font=F(11), active_bg=C["amber_soft"],
                                     command=self.prev, padx=20, pady=10)
        self.back_btn.pack(side="left")
        self.next_btn = _flat_button(btns, text="下一题 ›", bg=C["teal"], fg=C["surface_strong"],
                                     font=F(12, "bold"), active_bg=C["teal_deep"],
                                     command=self.next, padx=28, pady=10)
        self.next_btn.pack(side="right")

    def reset(self):
        self.index = 0
        self.render()

    def on_show(self):
        self.render()

    def _current(self):
        return self.all_questions[self.index]

    def _wrap(self):
        return max(480, self.app.winfo_width() - 160)

    # ---- 键盘操作 ----
    def _bind_keys(self):
        root = self.app
        for n in range(1, 6):
            root.bind(str(n), lambda e, n=n: self._key_select(n))
            root.bind("<KP_%d>" % n, lambda e, n=n: self._key_select(n))
        for k in ("a", "A", "b", "B"):
            root.bind(k, lambda e, k=k: self._key_choose(k.upper()))
        for key in ("<Left>", "<Up>", "<KP_Left>", "<KP_Up>"):
            root.bind(key, self._key_prev)
        for key in ("<Right>", "<Down>", "<KP_Right>", "<KP_Down>"):
            root.bind(key, self._key_next)

    def _active(self):
        return getattr(self.app, "current_page_name", None) == "QuestionPage"

    def _key_select(self, n):
        if not self._active():
            return
        if self._current()["id"] <= 40:
            self._select(n)
        return "break"

    def _key_choose(self, key):
        if not self._active():
            return
        if self._current()["id"] > 40:
            self._choose(key)
        return "break"

    def _key_prev(self, event):
        if not self._active():
            return
        self.prev()
        return "break"

    def _key_next(self, event):
        if not self._active():
            return
        self.next()
        return "break"

    def render(self):
        q = self._current()
        total = len(self.all_questions)

        if q["id"] <= 40:
            self.stage.config(text="核心探索 · 日常倾向")
            self.hint.config(text="请按“过去一年通常怎样”作答，而不是理想中的自己。")
            self.key_hint.config(text="键盘：1–5 选择　·　←/↑ 上一题　·　→/↓ 下一题")
        else:
            self.stage.config(text="价值冲突 · 二选一")
            self.hint.config(text="没有对错。选择更接近自己的那一项，稍后可补充条件。")
            self.key_hint.config(text="键盘：A / B 选择　·　←/↑ 上一题　·　→/↓ 下一题")

        self.qnum.config(text="{:03d}".format(q["id"]))
        self.qtext.config(text=q["text"], wraplength=self._wrap())
        self.progress["value"] = self.index
        self.count.config(text="{}/{}".format(self.index + 1, total))
        self.back_btn.config(state="normal" if self.index > 0 else "disabled")
        self._build_options(q)

    def _build_options(self, q):
        for w in self.option_area.winfo_children():
            w.destroy()
        self._option_buttons = []
        cur = self.app.answers.get(q["id"])

        if q["id"] <= 40:
            for i, label in enumerate(LIKERT_SCALE, start=1):
                b = self._option_button("{}   {}".format(i, label))
                b.pack(fill="x", pady=6)
                b.config(command=lambda v=i: self._select(v))
                self._option_buttons.append(b)
                if cur == i:
                    self._style_selected(b)
        else:
            for key in ("A", "B"):
                b = self._option_button("{} · {}".format(key, q[key]), wraplength=self._wrap() - 60)
                b.pack(fill="x", pady=8)
                b.config(command=lambda k=key: self._choose(k))
                self._option_buttons.append(b)
                if cur == key:
                    self._style_selected(b)

    def _option_button(self, text, wraplength=0):
        b = tk.Button(self.option_area, text=text, font=F(11), anchor="w", justify="left",
                      bg=C["surface"], fg=C["ink"], relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=C["border"],
                      highlightcolor=C["teal"], activebackground=C["teal_soft"],
                      activeforeground=C["teal_deep"], cursor="hand2",
                      padx=20, pady=15)
        if wraplength:
            b.config(wraplength=wraplength)
        return b

    def _style_selected(self, b):
        b.config(bg=C["teal_soft"], fg=C["teal_deep"], highlightbackground=C["teal"],
                 font=F(11, "bold"), activebackground=C["teal_soft"])

    def _style_normal(self, b):
        b.config(bg=C["surface"], fg=C["ink"], highlightbackground=C["border"],
                 font=F(11), activebackground=C["teal_soft"])

    def _select(self, val):
        self.app.answers[self._current()["id"]] = val
        for i, b in enumerate(self._option_buttons, start=1):
            if i == val:
                self._style_selected(b)
            else:
                self._style_normal(b)

    def _choose(self, key):
        self.app.answers[self._current()["id"]] = key
        self.next()

    def next(self):
        if self.index < len(self.all_questions) - 1:
            self.index += 1
            self.render()
        else:
            self.app.pages["ValidationPage"].reset()
            self.app.show_page("ValidationPage")

    def prev(self):
        if self.index > 0:
            self.index -= 1
            self.render()


# ---------------------------------------------------------------------------
# 校验页
# ---------------------------------------------------------------------------
class ValidationPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.vars = {}
        self.texts = {}
        self._build()

    def _build(self):
        inner = tk.Frame(self, bg=C["bg"])
        inner.pack(fill="both", expand=True, padx=80, pady=(56, 24))

        tk.Label(inner, text="最后几步", font=F(20, "bold", serif=True),
                 bg=C["bg"], fg=C["teal_deep"]).pack(anchor="w")
        tk.Label(inner, text="以下问题不计分，用于判断结果的可靠性（可跳过）",
                 font=F(10), bg=C["bg"], fg=C["soft"]).pack(anchor="w", pady=(6, 28))

        self.vars["v1"] = tk.StringVar(value="")
        self._choice_card(inner, VALIDATION_QUESTIONS[0], "v1",
                          ("现实中的自己", "理想中的自己", "两者之间"))
        self.vars["v2"] = tk.StringVar(value="")
        self._choice_card(inner, VALIDATION_QUESTIONS[1], "v2", ("有", "没有", "不确定"))

        for i, name in enumerate(("v3", "v4"), start=2):
            card = tk.Frame(inner, bg=C["surface"], highlightbackground=C["border"],
                            highlightthickness=1)
            card.pack(fill="x", pady=(0, 14))
            tk.Label(card, text=VALIDATION_QUESTIONS[i], font=F(11), bg=C["surface"],
                     fg=C["ink"], justify="left", wraplength=self._wrap()).pack(
                anchor="w", padx=24, pady=(16, 6))
            entry = tk.Entry(card, font=F(11), relief="flat", bg=C["surface_strong"],
                             highlightthickness=1, highlightbackground=C["border"])
            entry.pack(fill="x", padx=24, pady=(0, 16), ipady=6)
            self.texts[name] = entry

        btns = tk.Frame(inner, bg=C["bg"])
        btns.pack(anchor="w", pady=(10, 0))
        _flat_button(btns, text="跳过", bg=C["surface"], fg=C["ink"], font=F(11),
                     active_bg=C["amber_soft"], command=self.app.show_results,
                     padx=20, pady=10).pack(side="left")
        _flat_button(btns, text="生成意志", bg=C["amber"], fg=C["surface_strong"],
                     font=F(12, "bold"), active_bg=C["teal_deep"],
                     command=self._finish, padx=28, pady=10).pack(side="left", padx=(12, 0))

    def _wrap(self):
        return max(560, self.app.winfo_width() - 240)

    def _choice_card(self, parent, question, key, options):
        card = tk.Frame(parent, bg=C["surface"], highlightbackground=C["border"],
                        highlightthickness=1)
        card.pack(fill="x", pady=(0, 14))
        tk.Label(card, text=question, font=F(11), bg=C["surface"], fg=C["ink"],
                 justify="left", wraplength=self._wrap()).pack(anchor="w", padx=24, pady=(16, 6))
        box = tk.Frame(card, bg=C["surface"])
        box.pack(anchor="w", padx=24, pady=(0, 16))
        for label in options:
            tk.Radiobutton(box, text=label, variable=self.vars[key], value=label,
                           bg=C["surface"], fg=C["ink"], activebackground=C["surface"],
                           selectcolor=C["teal_soft"], font=F(11), anchor="w").pack(
                side="left", padx=(0, 18))

    def reset(self):
        for v in self.vars.values():
            v.set("")
        for e in self.texts.values():
            e.delete(0, "end")

    def on_show(self):
        pass

    def _finish(self):
        self.app.validation = {
            "v1": self.vars["v1"].get(),
            "v2": self.vars["v2"].get(),
            "v3": self.texts["v3"].get().strip(),
            "v4": self.texts["v4"].get().strip(),
        }
        self.app.show_results()


# ---------------------------------------------------------------------------
# 结果报告页
# ---------------------------------------------------------------------------
class ResultPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self.will = None
        self.profile = None
        self.tensions = []
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=56, pady=(20, 8))
        tk.Label(top, text="你的意志图谱", font=F(18, "bold", serif=True),
                 bg=C["bg"], fg=C["ink"]).pack(side="left")
        _flat_button(top, text="重新测试", bg=C["surface"], fg=C["ink"], font=F(11),
                     active_bg=C["amber_soft"], command=self.app.start_test,
                     padx=20, pady=9).pack(side="right")
        _flat_button(top, text="导出报告", bg=C["amber"], fg=C["surface_strong"],
                     font=F(11, "bold"), active_bg=C["teal_deep"],
                     command=self.export, padx=22, pady=9).pack(side="right", padx=8)

        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg=C["bg"])
        self.body.bind("<Configure>",
                       lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self._bind_wheel()

    def _bind_wheel(self):
        def on_wheel(e):
            self.canvas.yview_scroll(int(-e.delta / 120), "units")
        self.canvas.bind_all("<MouseWheel>", on_wheel)

    def on_show(self):
        pass

    def _wrap(self):
        return max(560, self.app.winfo_width() - 180)

    def _col_wrap(self):
        return max(150, (self.app.winfo_width() - 220) // 3)

    # ---- 小组件 ----
    def _section_title(self, parent, text):
        tk.Label(parent, text=text, font=F(14, "bold", serif=True), bg=C["bg"],
                 fg=C["teal_deep"]).pack(anchor="w", padx=56, pady=(30, 10))

    def _card(self, parent, bg=C["surface"]):
        f = tk.Frame(parent, bg=bg, highlightbackground=C["border"], highlightthickness=1)
        f.pack(fill="x", padx=56, pady=5)
        return f

    def _card_label(self, card, text, fg=C["ink"], font=None, wrap=None, padx=26, pady=(18, 18)):
        tk.Label(card, text=text, font=font or F(10), bg=card["bg"], fg=fg,
                 justify="left", anchor="w", wraplength=wrap or self._wrap() - 60).pack(
            anchor="w", padx=padx, pady=pady)

    def _kv_card(self, parent, key, value, key_fg=C["teal_deep"], bg=C["surface"]):
        card = self._card(parent, bg=bg)
        tk.Label(card, text=key, font=F(11, "bold"), bg=bg, fg=key_fg,
                 justify="left", anchor="w").pack(anchor="w", padx=26, pady=(18, 2))
        tk.Label(card, text=value, font=F(10), bg=bg, fg=C["ink"],
                 justify="left", anchor="w", wraplength=self._wrap() - 60).pack(
            anchor="w", padx=26, pady=(0, 18))

    # ---- 渲染 ----
    def render(self, answers):
        for w in self.body.winfo_children():
            w.destroy()

        scores = score(answers)
        profile = extract_profile(scores)
        profile = set_choices(profile, answers)
        tensions = detect_tensions(profile)
        will = generate(profile)
        self.will = will
        self.profile = profile
        self.tensions = tensions

        self._hero(will)
        self._three_columns(profile, will)
        self._flow(will, tensions)
        self._rules(will)
        self._shadow_growth(will)
        self._values(will)
        self._action_rel(will)
        self._beliefs(profile)
        self._costs(will)
        self._tensions_list(tensions)
        self._disclaimer()

        tk.Frame(self.body, bg=C["bg"], height=40).pack()

    def _hero(self, will):
        hero = tk.Frame(self.body, bg=C["bg"])
        hero.pack(fill="x", padx=56, pady=(24, 6))
        tk.Label(hero, text="你的当前意志 · V1", font=F(10, "bold"),
                 bg=C["bg"], fg=C["amber"]).pack(anchor="w")
        tk.Label(hero, text="《{}》".format(will["name"]), font=F(26, "bold", serif=True),
                 bg=C["bg"], fg=C["teal_deep"], justify="left",
                 wraplength=self._wrap()).pack(anchor="w", pady=(12, 8))
        tk.Label(hero, text=will["sentence"], font=F(11), bg=C["bg"], fg=C["soft"],
                 justify="left", wraplength=self._wrap()).pack(anchor="w")

        btns = tk.Frame(hero, bg=C["bg"])
        btns.pack(anchor="w", pady=(18, 0))
        _flat_button(btns, text="查看形成依据", bg=C["surface"], fg=C["ink"], font=F(10),
                     active_bg=C["teal_soft"], command=self._show_evidence,
                     padx=16, pady=8).pack(side="left")
        _flat_button(btns, text="这句话不像我", bg=C["surface"], fg=C["ink"], font=F(10),
                     active_bg=C["amber_soft"], command=self._mark_disagree,
                     padx=16, pady=8).pack(side="left", padx=(10, 0))

    def _show_evidence(self):
        if not self.profile:
            return
        needs = [D.CORE_NEEDS[k]["label"] for k, _ in self.profile["needs"] if k in D.CORE_NEEDS]
        threats = [D.CORE_THREATS[k]["label"] for k, _ in self.profile["threats"] if k in D.CORE_THREATS]
        values = [D.VALUES[k]["label"] for k, _ in self.profile["values"] if k in D.VALUES]
        msg = "形成依据（基于你的作答，仅作倾向参考）：\n\n"
        msg += "核心需要：" + "、".join(needs) + "\n"
        msg += "核心威胁：" + "、".join(threats) + "\n"
        msg += "价值优先级：" + "、".join(values)
        messagebox.showinfo("形成依据", msg)

    def _mark_disagree(self):
        messagebox.showinfo("已记录", "你拥有对自己意志的解释权。\n\n"
                            "这套描述只是一帧快照，可以修改、质疑，也可以让它随经历变化。")

    def _three_columns(self, profile, will):
        self._section_title(self.body, "你在保护什么 · 什么会触发你 · 你通常怎样应对")

        grid = tk.Frame(self.body, bg=C["bg"])
        grid.pack(fill="x", padx=56)
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="col")

        needs = [D.CORE_NEEDS[k]["label"] for k, _ in profile["needs"] if k in D.CORE_NEEDS]
        need_txt = " · ".join(needs[:2]) or "——"
        threat = will.get("core_threat") or {}
        threat_txt = (threat.get("label", "——") + "\n" + threat.get("trigger", "")) if threat else "——"
        rel_txt = will["relationship"]["label"] if will.get("relationship") else ""
        act_txt = will["action"]["label"] if will.get("action") else ""
        resp_txt = " · ".join([x for x in (rel_txt, act_txt) if x]) or "——"

        cols = [
            (C["teal"], "保护", need_txt),
            (C["coral"], "触发", threat_txt),
            (C["indigo"], "应对", resp_txt),
        ]
        for i, (fg, title, text) in enumerate(cols):
            card = tk.Frame(grid, bg=C["surface"], highlightbackground=C["border"],
                            highlightthickness=1)
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else 8, 0 if i == 2 else 8))
            tk.Label(card, text=title, font=F(10, "bold"), bg=C["surface"], fg=fg).pack(
                anchor="w", padx=20, pady=(16, 4))
            tk.Label(card, text=text, font=F(10), bg=C["surface"], fg=C["ink"],
                     justify="left", wraplength=self._col_wrap()).pack(
                anchor="w", padx=20, pady=(0, 16))

    def _flow(self, will, tensions):
        self._section_title(self.body, "行为循环")
        items = []
        if will.get("core_threat"):
            items.append((C["coral"], C["coral_soft"], "触发",
                          will["core_threat"]["trigger"]))
        parts = []
        if will.get("relationship"):
            parts.append(will["relationship"]["desc"])
        if will.get("action"):
            parts.append(will["action"]["how"])
        if parts:
            items.append((C["teal"], C["teal_soft"], "应对", " ".join(parts)))
        items.append((C["amber"], C["amber_soft"], "代价", will["shadow"]))
        if tensions:
            items.append((C["indigo"], C["indigo_soft"], "张力", "；".join(tensions)))

        for idx, (fg, bg, title, text) in enumerate(items):
            card = self._card(self.body, bg=bg)
            tk.Label(card, text=title, font=F(11, "bold"), bg=bg, fg=fg).pack(
                anchor="w", padx=26, pady=(16, 2))
            tk.Label(card, text=text, font=F(10), bg=bg, fg=C["ink"],
                     justify="left", wraplength=self._wrap() - 60).pack(
                anchor="w", padx=26, pady=(0, 16))
            if idx < len(items) - 1:
                tk.Label(self.body, text="↓", font=F(12, "bold"), bg=C["bg"],
                         fg=C["soft"]).pack(pady=3)

    def _rules(self, will):
        self._section_title(self.body, "四条法则")
        rules = [
            ("趋近", "我主动追求什么", will["rules"]["approach"], C["teal"], C["teal_soft"]),
            ("拒绝", "无论收益多大，我绝不做什么", will["rules"]["refusal"], C["coral"], C["coral_soft"]),
            ("冲突", "珍视之物冲突时，哪个优先", will["rules"]["conflict"] or "——", C["amber"], C["amber_soft"]),
            ("复归", "迷失之后，通过什么找回自己", will["rules"]["recovery"], C["indigo"], C["indigo_soft"]),
        ]
        grid = tk.Frame(self.body, bg=C["bg"])
        grid.pack(fill="x", padx=56)
        grid.grid_columnconfigure(0, weight=1, uniform="r")
        grid.grid_columnconfigure(1, weight=1, uniform="r")
        for i, (title, sub, text, fg, bg) in enumerate(rules):
            card = tk.Frame(grid, bg=bg, highlightbackground=C["border"], highlightthickness=1)
            card.grid(row=i // 2, column=i % 2, sticky="nsew",
                      padx=(0 if i % 2 == 0 else 8, 0 if i % 2 == 1 else 8), pady=5)
            tk.Label(card, text=title, font=F(12, "bold"), bg=bg, fg=fg).pack(
                anchor="w", padx=24, pady=(18, 0))
            tk.Label(card, text=sub, font=F(9), bg=bg, fg=C["soft"]).pack(
                anchor="w", padx=24, pady=(0, 6))
            tk.Label(card, text=text, font=F(10), bg=bg, fg=C["ink"], justify="left",
                     wraplength=self._col_wrap() * 2 - 20).pack(
                anchor="w", padx=24, pady=(0, 18))

    def _shadow_growth(self, will):
        self._section_title(self.body, "阴影与成长方向")
        self._kv_card(self.body, "阴影", will["shadow"], key_fg=C["coral"], bg=C["coral_soft"])
        self._kv_card(self.body, "成长方向", will["growth"], key_fg=C["teal_deep"], bg=C["teal_soft"])

    def _values(self, will):
        if not will["values"]:
            return
        self._section_title(self.body, "价值优先级")
        for v in will["values"]:
            self._kv_card(self.body, v["label"], v["principle"], key_fg=C["amber"])

    def _action_rel(self, will):
        if will.get("action"):
            self._section_title(self.body, "行动模式")
            self._kv_card(self.body, will["action"]["label"],
                          "{} {}".format(will["action"]["desc"], will["action"]["how"]))
        if will.get("relationship"):
            self._section_title(self.body, "关系策略")
            self._kv_card(self.body, will["relationship"]["label"],
                          will["relationship"]["desc"])

    def _beliefs(self, profile):
        self._section_title(self.body, "世界假设")
        for bkey, info in profile["beliefs"].items():
            bdef = D.BELIEFS.get(bkey)
            if not bdef:
                continue
            if info["score"] >= 3.5:
                text = bdef["high"]
            elif info["score"] <= 2.5:
                text = bdef["low"]
            else:
                text = "你对此没有明显偏向，视具体情境而定。"
            self._kv_card(self.body, bdef["label"], text)

    def _costs(self, will):
        if not will["costs"]:
            return
        self._section_title(self.body, "边界与代价")
        for c in will["costs"]:
            self._kv_card(self.body, c["label"], c["desc"], key_fg=C["coral"])

    def _tensions_list(self, tensions):
        if not tensions:
            return
        self._section_title(self.body, "内在张力")
        for t in tensions:
            self._kv_card(self.body, "矛盾点", t, key_fg=C["indigo"], bg=C["indigo_soft"])

    def _disclaimer(self):
        self._section_title(self.body, "说明")
        card = self._card(self.body)
        self._card_label(card,
                         "本报告基于你的作答生成，是一套可解释、可修订的自我叙事模型，"
                         "用于整理你已感受到、却尚未清晰说出的部分。它不是医学诊断，"
                         "也不预设“不可改变的真相”。你的意志会随经历而变，"
                         "这份图谱只是此刻的一帧快照。",
                         fg=C["soft"])

    # ---- 导出 ----
    def export(self):
        if not self.will:
            return
        will = self.will
        lines = []
        lines.append("意志图谱 · 报告")
        lines.append("=" * 40)
        lines.append("")
        lines.append("意志名：《{}》".format(will["name"]))
        lines.append("意志句：{}".format(will["sentence"]))
        lines.append("")
        lines.append("【核心需要】")
        lines.append("{} · {}".format(will["core_need"]["label"], will["core_need"]["blurb"]))
        if will.get("core_threat"):
            lines.append("")
            lines.append("【核心威胁】{}".format(will["core_threat"]["label"]))
            lines.append("最不能接受：{}".format(will["core_threat"]["fear"]))
            lines.append("触发场景：{}".format(will["core_threat"]["trigger"]))
        lines.append("")
        lines.append("【四条规则】")
        lines.append("趋近：{}".format(will["rules"]["approach"]))
        lines.append("拒绝：{}".format(will["rules"]["refusal"]))
        lines.append("冲突：{}".format(will["rules"]["conflict"] or "——"))
        lines.append("复归：{}".format(will["rules"]["recovery"]))
        lines.append("")
        lines.append("【阴影】")
        lines.append(will["shadow"])
        lines.append("")
        lines.append("【成长方向】")
        lines.append(will["growth"])
        lines.append("")
        if will["values"]:
            lines.append("【价值优先级】")
            for v in will["values"]:
                lines.append("{}：{}".format(v["label"], v["principle"]))
            lines.append("")
        if will.get("action"):
            lines.append("【行动模式】{}：{}{}".format(
                will["action"]["label"], will["action"]["desc"], will["action"]["how"]))
            lines.append("")
        if will.get("relationship"):
            lines.append("【关系策略】{}：{}".format(
                will["relationship"]["label"], will["relationship"]["desc"]))
            lines.append("")
        if self.tensions:
            lines.append("【内在张力】")
            for t in self.tensions:
                lines.append("· " + t)
            lines.append("")
        lines.append("【说明】本报告是可解释、可修订的自我叙事模型，不是医学诊断。")

        filename = "意志图谱报告_{}.txt".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        path = os.path.join(_desktop_dir(), filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        messagebox.showinfo("已导出", "报告已保存到桌面：\n{}".format(path))
