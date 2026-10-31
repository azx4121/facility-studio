"""Wrap action controls to their actual client width, including translated text."""

from .localized_tk import ttk
from . import i18n


class FlowToolbar(ttk.Frame):
    def __init__(self, parent, **options):
        super().__init__(parent, **options)
        self._job = None
        self._layout_key = None
        self._bound = set()
        # Child requisitions must not force the workbench wider than its client.
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.bind("<Configure>", self._schedule, add="+")
        self.bind("<Map>", self._schedule, add="+")
        self.bind("<<ThemeChanged>>", self._schedule, add="+")
        self.bind("<Destroy>", self._destroy, add="+")
        i18n.subscribe(self)

    def refresh_language(self):
        if self.winfo_exists():
            self._layout_key = None
            self._schedule()

    def _destroy(self, event):
        if event.widget is self and self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _schedule(self, event=None):
        if event is not None and event.widget is self:
            if self._job is not None:
                self.after_cancel(self._job)
                self._job = None
            self._arrange()
        elif self._job is None:
            self._job = self.after_idle(self._arrange)

    def _arrange(self):
        self._job = None
        # A parent's requested width can briefly exceed the resized client.
        # Keep actions inside the actual top-level client during that turn too.
        window = self.winfo_toplevel()
        available = window.winfo_rootx() + window.winfo_width() - self.winfo_rootx()
        width = min(self.winfo_width(), available)
        children = self.winfo_children()
        if width < 20 or not children:
            return
        sizes = tuple((str(child), child.winfo_reqwidth(), child.winfo_reqheight())
                      for child in children)
        key = (width, sizes)
        if key == self._layout_key:
            return
        self._layout_key = key
        x, y, row_height = 4, 3, 0
        for child, (_, requested, height) in zip(children, sizes):
            if str(child) not in self._bound:
                child.bind("<Configure>", self._schedule, add="+")
                self._bound.add(str(child))
            manager = child.winfo_manager()
            if manager == "pack":
                child.pack_forget()
            elif manager == "grid":
                child.grid_forget()
            control_width = min(requested, max(1, width - 8))
            if x > 4 and x + control_width + 4 > width:
                y += row_height + 6
                x, row_height = 4, 0
            child.place(x=x, y=y, width=control_width, height=height)
            x += control_width + 8
            row_height = max(row_height, height)
        height = y + row_height + 3
        if int(self.cget("height")) != height:
            self.configure(height=height)
