"""Defer TkAgg's idle rasterization while its application view is hidden."""

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as NativeCanvas


class FigureCanvasTkAgg(NativeCanvas):
    def __init__(self, *args, visible, **kwargs):
        self._visible = visible
        self._render_pending = False
        super().__init__(*args, **kwargs)
        self.get_tk_widget().bind("<Map>", self._mapped, add="+")

    def draw_idle(self):
        if not self._visible():
            self._render_pending = True
            return
        self._render_pending = False
        return super().draw_idle()

    def _mapped(self, event):
        if self._render_pending:
            self.draw_idle()

    def draw_pending(self):
        if self._render_pending:
            self.draw_idle()
