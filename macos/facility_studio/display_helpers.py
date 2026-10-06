"""Display formatting and label placement; never changes engineering states."""


def duct_dimensions(d):
    if d['shape'] == '方管':
        return f"方管 {d['w_mm']:.0f} × {d['h_mm']:.0f} mm"
    return f"圓管 ID {d['diameter_m'] * 1000:.1f} mm"


def annotate_states(ax, groups, fontsize=9):
    """Place exact point labels greedily in screen space after axis layout."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.transforms import Bbox

    renderer = ax.figure.canvas.get_renderer()
    bounds = ax.get_window_extent(renderer)
    occupied = []
    font = FontProperties(size=fontsize)
    candidates = [(8, 12), (8, -24), (-65, 12), (-65, -24),
                  (12, 30), (-65, 30), (12, -44), (-65, -44),
                  (35, 55), (-100, 55), (35, -64), (-100, -64)]
    for (temperature, moisture), names in groups.items():
        label = '/'.join(names)
        width, height, _ = renderer.get_text_width_height_descent(label, font, False)
        x, y = ax.transData.transform((temperature, moisture))
        best = None
        for dx, dy in candidates:
            px = min(max(x + dx, bounds.x0 + 4), bounds.x1 - width - 4)
            py = min(max(y + dy, bounds.y0 + 4), bounds.y1 - height - 4)
            box = Bbox.from_bounds(px - 3, py - 3, width + 6, height + 8)
            score = sum(box.overlaps(other) for other in occupied) * 10000 + (px - x) ** 2 + (py - y) ** 2
            if best is None or score < best[0]:
                best = score, px, py, box
        _, px, py, box = best
        occupied.append(box)
        ax.annotate(label, (temperature, moisture),
                    xytext=((px - x) * 72 / ax.figure.dpi, (py - y) * 72 / ax.figure.dpi),
                    textcoords='offset points', fontsize=fontsize,
                    va='bottom', ha='left',
                    bbox=dict(facecolor='white', alpha=.85, edgecolor='none', pad=1.2),
                    arrowprops=dict(arrowstyle='-', color='#718096', lw=.5))
