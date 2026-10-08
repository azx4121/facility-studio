"""Wrap workbench actions within the available width without hiding controls."""

import math
from .localized_tk import ttk


class FlowToolbar(ttk.Frame):
    def __init__(self, parent, **options):
        super().__init__(parent, **options)
        self._job = None
        self._layout_key = None
        self._columns = 0
        self.bind("<Configure>", self._schedule, add="+")
        self.bind("<Map>", self._schedule, add="+")
        self.bind("<Destroy>", self._destroy, add="+")

    def _destroy(self, event):
        if event.widget is self and self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _schedule(self, event=None):
        if self._job is None:
            self._job = self.after_idle(self._arrange)

    def _arrange(self):
        self._job = None
        width = self.winfo_width()
        children = self.winfo_children()
        if width < 50 or not children:
            return
        columns = max(1, width // 24)
        widths = tuple(child.winfo_reqwidth() for child in children)
        key = (columns, widths)
        if key == self._layout_key:
            return
        self._layout_key = key
        for child in children:
            if child.winfo_manager() == "pack":
                child.pack_forget()
                child.bind("<Configure>", self._schedule, add="+")
        for column in range(max(columns, self._columns)):
            self.columnconfigure(
                column, minsize=24 if column < columns else 0,
                weight=1 if column < columns else 0,
                uniform="flow" if column < columns else "",
            )
        self._columns = columns
        row = column = 0
        for child, requested in zip(children, widths):
            span = min(columns, max(1, math.ceil((requested + 8) / 24)))
            if column + span > columns:
                row += 1
                column = 0
            child.grid(row=row, column=column, columnspan=span,
                       sticky="ew", padx=4, pady=3)
            column += span
