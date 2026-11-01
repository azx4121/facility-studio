"""Shared, native ttk dashboard components. No third party UI dependency."""

import math
import sys
try:
    from tkinter import font as tkfont
except ImportError:
    tkfont = None
from .localized_tk import tk, ttk


def enable_high_dpi():
    """Call before creating Tk on Windows; safely tolerate an existing manifest."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        # E_ACCESSDENIED means awareness was already set by the executable.
        status = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        if status in (0, -2147024891):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def format_number(value, decimals=2):
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    try:
        if not math.isfinite(float(value)):
            return "—"
        return f"{value:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


class Theme:
    BG = "#EAF0FA"
    CARD = "#F8FBFF"
    BORDER = "#DCE1E9"
    NAV = "#D5DFE8"
    PRIMARY = "#0066CC"
    TEXT = "#1D1D1F"
    MUTED = "#62626A"
    SUCCESS = "#16A34A"
    WARNING = "#D97706"
    DANGER = "#DC2626"
    # Input fields: white face and a boundary with >= 3:1 contrast against BG and CARD
    # (WCAG 2.1 SC 1.4.11), so fields stay visible on every surface.
    FIELD = "#FFFFFF"
    FIELD_BORDER = "#7B8698"
    FIELD_DISABLED = "#E2E8F0"
    FIELD_DISABLED_BORDER = "#B4BDC9"
    BUTTON_HOVER = "#DCE6F2"
    BUTTON_PRESSED = "#C9D6E6"
    TONES = {
        "success": ("#326646", "#F0F6F2"),
        "warning": ("#8A5800", "#FFF7E7"),
        "danger": ("#B42332", "#FFF0F1"),
        "neutral": (MUTED, "#EEF1F5"),
    }
    family = "Microsoft JhengHei UI"
    mono = "Consolas"
    scale = 1.0

    @classmethod
    def px(cls, value):
        return round(value * cls.scale)

    @classmethod
    def apply(cls, root):
        from .platform_support import normalize_tk_scaling

        normalize_tk_scaling(root)
        cls.scale = max(1.0, float(root.winfo_fpixels("1i")) / 96.0)
        families = set(tkfont.families(root))
        cls.family = next((n for n in ("Microsoft JhengHei UI", "Microsoft JhengHei",
                         "PingFang TC", "Noto Sans CJK TC", "Segoe UI") if n in families), "TkDefaultFont")
        cls.mono = next((n for n in ("Consolas", "Menlo", "DejaVu Sans Mono",
                       "Courier New") if n in families), "TkFixedFont")
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        root.configure(background=cls.BG)
        style.configure(".", font=(cls.family, 10), background=cls.BG, foreground=cls.TEXT)
        style.configure("TFrame", background=cls.BG)
        style.configure("TLabel", background=cls.BG, foreground=cls.TEXT)
        style.configure("TButton", padding=(12, 8), background=cls.CARD,
                        foreground=cls.TEXT, bordercolor="#E2E8F0", borderwidth=1)
        style.map("TButton", background=[("active", "#E2E8F0")])
        style.configure("Nav.TButton", background=cls.NAV, foreground=cls.TEXT,
                        anchor="w", padding=(12, 6), borderwidth=0,
                        font=(cls.family, 10))
        style.map("Nav.TButton", background=[("active", "#E0E6EF")],
                  foreground=[("active", cls.TEXT)])
        style.configure("Nav.Active.TButton", background="#DCEBFC",
                        foreground="#004C99", anchor="w", padding=(12, 6),
                        borderwidth=0, font=(cls.family, 10, "bold"))
        style.map("Nav.Active.TButton", background=[("active", "#CFDFF5")],
                  foreground=[("active", "#004C99")])
        for prefix in ("Primary", "Simple.Primary"):
            name = prefix + ".TButton"
            style.configure(name, background=cls.PRIMARY, foreground="white",
                            bordercolor=cls.PRIMARY, font=(cls.family, 10, "bold"))
            style.map(name, background=[("disabled", "#94A3B8"), ("active", "#0055AA")],
                      foreground=[("disabled", "#F1F5F9"), ("active", "white")])
        for name in ("TEntry", "TCombobox"):
            style.configure(name, padding=6, fieldbackground=cls.CARD,
                            bordercolor=cls.BORDER, lightcolor=cls.BORDER,
                            darkcolor=cls.BORDER, font=(cls.mono, 11))
            style.map(name, bordercolor=[("focus", cls.PRIMARY)],
                      lightcolor=[("focus", cls.PRIMARY)], darkcolor=[("focus", cls.PRIMARY)])
        style.map("TCombobox", fieldbackground=[("disabled", cls.BG), ("readonly", cls.CARD)],
                  foreground=[("disabled", cls.MUTED), ("readonly", cls.TEXT)])
        for name in ("Invalid.TEntry", "Simple.Invalid.TEntry", "Invalid.TCombobox"):
            style.configure(name, fieldbackground="#FEF2F2", bordercolor=cls.DANGER,
                            lightcolor=cls.DANGER, darkcolor=cls.DANGER)
            style.map(name, fieldbackground=[("readonly", "#FEF2F2")],
                      bordercolor=[("focus", cls.DANGER)], lightcolor=[("focus", cls.DANGER)],
                      darkcolor=[("focus", cls.DANGER)])
        for name in ("Card.TFrame", "Simple.Card.TFrame"):
            style.configure(name, background=cls.CARD, bordercolor=cls.BORDER,
                            relief="solid", borderwidth=1)
        style.configure("Form.Row.TFrame", background=cls.CARD, borderwidth=0,
                        relief="flat")
        for name in ("Card.TLabel", "Simple.Card.TLabel", "Simple.Hint.TLabel"):
            style.configure(name, background=cls.CARD)
        style.configure("Simple.Hint.TLabel", foreground=cls.MUTED, font=(cls.family, 9))
        style.configure("Simple.Muted.TLabel", foreground=cls.MUTED)
        style.configure("Simple.Normal.TLabel", foreground=cls.TEXT)
        style.configure("Simple.Title.TLabel", font=(cls.family, 14, "bold"))
        style.configure("Simple.Header.TLabel", font=(cls.family, 11, "bold"))
        style.configure("Simple.Value.TLabel", background=cls.CARD,
                        foreground=cls.PRIMARY, font=(cls.mono, 20, "bold"))
        style.configure("Simple.Brand.TLabel", background=cls.NAV,
                        foreground=cls.TEXT, font=(cls.family, 14, "bold"))
        style.configure("Simple.SideHint.TLabel", background=cls.NAV, foreground="#475569")
        style.configure("Unit.TLabel", background=cls.CARD, foreground=cls.MUTED,
                        font=(cls.mono, 10))
        for name, color in (("Simple.Good", cls.SUCCESS), ("Simple.Error", cls.DANGER),
                            ("Good", cls.SUCCESS), ("Error", cls.DANGER), ("Warn", cls.WARNING)):
            style.configure(name + ".TLabel", foreground=color)
        style.configure("Dashboard.Treeview", background=cls.CARD, fieldbackground=cls.CARD,
                        foreground=cls.TEXT, rowheight=cls.px(34), font=(cls.mono, 10),
                        bordercolor=cls.BORDER, borderwidth=1)
        style.configure("Dashboard.Treeview.Heading", background="#E2E8F0",
                        foreground=cls.TEXT, font=(cls.family, 10, "bold"), padding=(8, 8))
        style.map("Dashboard.Treeview", background=[("selected", "#DBEAFE")],
                  foreground=[("selected", "#0F172A")])
        style.configure("TLabelframe", background=cls.CARD, bordercolor=cls.BORDER)
        style.configure("TLabelframe.Label", background=cls.CARD, font=(cls.family, 11, "bold"))
        style.configure("Title.TLabel", font=(cls.family, 16, "bold"), foreground=cls.TEXT)
        style.configure("Accent.TButton", background=cls.PRIMARY, foreground="white")
        style.map("Accent.TButton", background=[("active", "#0055AA")])
        # Flat surfaces, but input fields keep a white face and a visible boundary;
        # the focused field is outlined in the primary colour.
        for name in ("TEntry", "TCombobox"):
            style.configure(name, background=cls.BG, fieldbackground=cls.FIELD,
                            foreground=cls.TEXT, insertcolor=cls.TEXT,
                            borderwidth=1, relief="solid", bordercolor=cls.FIELD_BORDER,
                            lightcolor=cls.FIELD, darkcolor=cls.FIELD, arrowcolor=cls.TEXT)
            style.map(name,
                      bordercolor=[("disabled", cls.FIELD_DISABLED_BORDER), ("focus", cls.PRIMARY)],
                      lightcolor=[("disabled", cls.FIELD_DISABLED), ("focus", cls.PRIMARY)],
                      darkcolor=[("disabled", cls.FIELD_DISABLED), ("focus", cls.PRIMARY)],
                      fieldbackground=[("disabled", cls.FIELD_DISABLED)],
                      foreground=[("disabled", cls.MUTED)])
        style.map("TCombobox", fieldbackground=[("disabled", cls.FIELD_DISABLED), ("readonly", cls.FIELD)],
                  foreground=[("disabled", cls.MUTED), ("readonly", cls.TEXT)])
        style.configure("Simple.Card.TFrame", background=cls.BG, borderwidth=0, relief="flat")
        style.configure("Form.Row.TFrame", background=cls.BG, borderwidth=0)
        for name in ("Simple.Card.TLabel", "Simple.Hint.TLabel", "Unit.TLabel"):
            style.configure(name, background=cls.BG)
        style.configure("TCheckbutton", background=cls.BG)
        style.configure("TLabelframe", background=cls.BG, borderwidth=0, relief="flat")
        style.configure("TLabelframe.Label", background=cls.BG)
        # Buttons keep a visible outline on the flat surface; hover and press are distinct.
        style.configure("TButton", borderwidth=1, relief="solid", bordercolor=cls.FIELD_BORDER,
                        lightcolor=cls.CARD, darkcolor=cls.CARD)
        style.map("TButton", background=[("disabled", cls.FIELD_DISABLED), ("pressed", cls.BUTTON_PRESSED),
                                         ("active", cls.BUTTON_HOVER)],
                  foreground=[("disabled", cls.MUTED)],
                  bordercolor=[("disabled", cls.FIELD_DISABLED_BORDER), ("focus", cls.PRIMARY)])
        for name in ("Treeview.Heading", "Dashboard.Treeview.Heading"):
            style.configure(name, background="#DEE7F3", borderwidth=0, relief="flat",
                            lightcolor="#DEE7F3", darkcolor="#DEE7F3")
        return style


def set_entry_valid(widget, valid=True):
    if isinstance(widget, ttk.Combobox):
        widget.configure(style="TCombobox" if valid else "Invalid.TCombobox")
    elif isinstance(widget, ttk.Entry):
        widget.configure(style="TEntry" if valid else "Simple.Invalid.TEntry")


class ScrollableFrame(ttk.Frame):
    """Local scrolling, without replacing global mouse wheel bindings."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background=Theme.BG, highlightthickness=0,
                                width=360, height=360)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.body = ttk.Frame(self.canvas, padding=(16, 14))
        self.body.columnconfigure(0, weight=1)
        self.item = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self._scroll_bounds = None
        self._body_width = None
        self.body.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._fit_body)
        self._wheel_tag = "FacilityScroll" + str(self).replace(".", "_")
        self.bind_class(self._wheel_tag, "<MouseWheel>", self._wheel)
        self.bind_class(self._wheel_tag, "<Button-4>", self._wheel)
        self.bind_class(self._wheel_tag, "<Button-5>", self._wheel)
        self.bind("<Map>", self._attach, add="+")
        # KPI cards are rebuilt after calculation. A Frame's Map binding does
        # not see those newly created descendants, but their toplevel does.
        self._map_window = self.winfo_toplevel()
        self._map_binding = self._map_window.bind("<Map>", self._descendant_mapped, add="+")
        self.bind("<Destroy>", self._destroy, add="+")

    def _sync_scroll_region(self, event=None):
        bounds = self.canvas.bbox("all")
        if bounds != self._scroll_bounds:
            self._scroll_bounds = bounds
            self.canvas.configure(scrollregion=bounds or (0, 0, 0, 0))

    def _fit_body(self, event):
        if event.width != self._body_width:
            self._body_width = event.width
            self.canvas.itemconfigure(self.item, width=event.width)

    def _attach_widget(self, widget):
        if not hasattr(widget, "winfo_class"):
            return
        # Check the native widget class too: external callers may create a
        # standard Tk Text/Treeview rather than our localized subclass.
        if widget.winfo_class() not in ("TCombobox", "Treeview", "Text"):
            tags = widget.bindtags()
            if self._wheel_tag not in tags:
                widget.bindtags((tags[0], self._wheel_tag, *tags[1:]))

    def _descendant_mapped(self, event):
        if not hasattr(event.widget, "winfo_class"):
            return
        if event.widget is self or str(event.widget).startswith(str(self) + "."):
            self._attach_widget(event.widget)

    def _attach(self, event=None):
        def visit(widget):
            self._attach_widget(widget)
            for child in widget.winfo_children():
                visit(child)
        visit(self)

    def _wheel(self, event):
        delta = getattr(event, "delta", 0)
        if not delta and getattr(event, "num", 0) not in (4, 5):
            return
        if self.canvas.yview() == (0.0, 1.0):
            return
        amount = -1 if getattr(event, "num", 0) == 4 or delta > 0 else 1
        if sys.platform == "win32" and abs(delta) >= 120:
            amount *= max(1, abs(delta) // 120) * 3
        self.canvas.yview_scroll(amount, "units")
        return "break"

    def _destroy(self, event):
        if event.widget is self:
            try:
                self._map_window.unbind("<Map>", self._map_binding)
            except tk.TclError:
                pass
            for event_name in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.unbind_class(self._wheel_tag, event_name)


class InlineBanner(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.label = tk.Label(self, anchor="w", justify="left", padx=12, pady=9,
                              font=(Theme.family, 10), wraplength=420)
        self.label.pack(fill="both", expand=True)
        self.bind("<Configure>", lambda e: self.label.configure(wraplength=max(120, e.width - 24)))
        self.show("準備計算", "neutral")

    def show(self, text, tone="neutral"):
        fg, bg = Theme.TONES.get(tone, Theme.TONES["neutral"])
        self.label.configure(text=text, foreground=fg, background=bg)


class GlassCard(tk.Frame):
    """Opaque text on a softly layered card, preserving native text contrast."""
    def __init__(self, parent, compact=False):
        super().__init__(parent, bg=Theme.BG)
        self.glass = tk.Canvas(self, bg=Theme.BG, highlightthickness=0)
        self.glass.place(x=0, y=0, relwidth=1, relheight=1)
        self.content = tk.Frame(self, bg=Theme.CARD)
        self.content.pack(fill="both", expand=True, padx=10 if compact else 12, pady=3 if compact else 16)
        self.bind("<Configure>", self.redraw)

    def redraw(self, event=None):
        w,h=self.winfo_width(),self.winfo_height()
        if w<20 or h<20:return
        c=self.glass;c.delete("all")
        def rounded(x1,y1,x2,y2,r,fill,outline):
            return c.create_polygon(x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,x2-r,y2,
                                    x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1,
                                    smooth=True,splinesteps=12,fill=fill,outline=outline)
        rounded(2,3,w-2,h-1,14,"#E4E9F1","#E4E9F1")
        rounded(1,1,w-3,h-4,14,Theme.CARD,"#DFE5EE")
        start,end=(239,247,255),(243,238,250)
        for y in range(3,max(4,h-5),2):
            f=y/max(1,h-5)
            color='#'+''.join(f'{round(a+(b-a)*f):02x}' for a,b in zip(start,end))
            edge=min(y-1,h-5-y,14)
            inset=14-math.sqrt(max(0,14**2-(14-edge)**2))
            c.create_line(3+inset,y,w-5-inset,y,fill=color,width=2)
        c.create_line(14,2,w-16,2,fill="#FFFFFF",width=2)


class KPIFrame(ttk.Frame):
    def __init__(self, parent, compact=False, **kwargs):
        super().__init__(parent, **kwargs)
        self.compact = compact
        self.cards = []
        self.boxes = []
        self._columns = None
        self.bind("<Configure>", self._layout)

    def set_cards(self, cards):
        cards = [dict(card) for card in cards]
        if cards == self.cards and len(self.boxes) == len(cards):
            return
        self.cards = cards
        for box in self.boxes:
            box.destroy()
        self.boxes = []
        for card in self.cards:
            box = GlassCard(self, self.compact)
            content = box.content
            title = tk.Label(content, text=card.get("title", ""), bg=Theme.CARD, fg=Theme.MUTED,
                             anchor="w", justify="left", font=(Theme.family, 9 if self.compact else 10))
            title.pack(anchor="w")
            main = tk.Frame(content, bg=Theme.CARD)
            main.pack(fill="x", pady=(2, 1) if self.compact else (8, 9))
            value = card.get("value", "—")
            unit = card.get("unit", "")
            if self.compact and isinstance(value, str) and not unit:
                import re
                match = re.fullmatch(r"([-+]?[\d,]+(?:\.\d+)?)\s+(.+)", value)
                if match:
                    value, unit = match.groups()
            label = tk.Label(main, text=format_number(value) if not isinstance(value, str) else value,
                             bg=Theme.CARD, fg=Theme.TEXT, anchor="w", justify="left",
                             font=(Theme.mono, 12 if self.compact else 20, "bold"), wraplength=220)
            label.pack(anchor="w")
            if unit or not self.compact:
                tk.Label(main, text=unit, bg=Theme.CARD, fg=Theme.MUTED,
                         font=(Theme.mono, 8 if self.compact else 10)).pack(anchor="w")
            fg, bg = Theme.TONES.get(card.get("tone", "neutral"), Theme.TONES["neutral"])
            if not self.compact:
                tk.Label(content, text=card.get("status", "需求初估"), bg=bg, fg=fg,
                         padx=8, pady=3, font=(Theme.family, 9)).pack(anchor="w")
            # Title and value wrap to the card, so a long translated title is never cut off.
            box.bind("<Configure>", lambda e, w=label, t=title: [x.configure(wraplength=max(100, e.width - 34)) for x in (w, t)], add="+")
            self.boxes.append(box)
        self._columns = None
        self._layout()

    def _layout(self, event=None):
        width = event.width if event is not None else self.winfo_width()
        columns = (2 if width >= 300 else 1) if self.compact else (3 if width >= Theme.px(840) else 2 if width >= Theme.px(470) else 1)
        if self._columns == columns:
            return
        self._columns = columns
        for index in range(3):
            self.columnconfigure(index, weight=1 if index < columns else 0,
                                 uniform="kpi" if index < columns else "", minsize=0)
        for index, box in enumerate(self.boxes):
            box.grid(row=index // columns, column=index % columns, sticky="nsew", padx=3 if self.compact else 5, pady=3 if self.compact else 5)


class ResultTable(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(self, columns=("label", "value", "unit", "status"),
                                 show="headings", height=10, style="Dashboard.Treeview")
        for key, text, width, anchor in (("label", "設計項目", 200, "w"),
                                         ("value", "計算需求值", 145, "e"),
                                         ("unit", "單位", 90, "w"),
                                         ("status", "狀態／說明", 210, "w")):
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, minwidth=65, anchor=anchor)
        self.tree.tag_configure("even", background=Theme.CARD)
        self.tree.tag_configure("odd", background=Theme.BG)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(self, command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

    def set_rows(self, rows):
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(rows):
            if isinstance(row, dict):
                row = [row.get(k, "") for k in ("label", "value", "unit", "status")]
            values = list(row)
            while len(values) < 4:
                values.append("")
            if isinstance(values[1], (float, int)):
                values[1] = format_number(values[1])
            self.tree.insert("", "end", values=values[:4], tags=("odd" if index % 2 else "even",))
