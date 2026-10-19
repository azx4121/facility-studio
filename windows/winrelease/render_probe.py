"""Record native layout and actual canvas pixels without changing the image."""
from pathlib import Path


def capture(root, app, destination, name):
    from PIL import ImageGrab
    page = app.active_page()
    image = ImageGrab.grab()
    path = Path(destination).with_name(name)
    image.save(path)
    regions = {}
    for label, frame in (("inputs", page.input_scroll), ("results", page.output_scroll)):
        canvas = frame.canvas
        x, y = canvas.winfo_rootx(), canvas.winfo_rooty()
        bounds = (max(0, x), max(0, y), min(image.width, x+canvas.winfo_width()), min(image.height, y+canvas.winfo_height()))
        colors, dark_fraction = 0, 1.0
        if bounds[2] > bounds[0] and bounds[3] > bounds[1]:
            crop = image.crop(bounds).convert("RGB")
            histogram = crop.getcolors(crop.width*crop.height)
            colors = len(histogram)
            dark_fraction = sum(count for count, rgb in histogram if max(rgb) < 8) / (crop.width*crop.height)
        regions[label] = dict(canvas_mapped=bool(canvas.winfo_ismapped()), body_mapped=bool(frame.body.winfo_ismapped()),
                              bounds=bounds, distinct_colors=colors, dark_fraction=dark_fraction,
                              canvas_item_window=str(canvas.itemcget(frame.item,"window")),
                              visible=bool(canvas.winfo_ismapped() and frame.body.winfo_ismapped()
                                           and colors > 8 and dark_fraction < .15))
    return dict(file=path.name, tool=app.current, regions=regions, visible=all(r["visible"] for r in regions.values()))
