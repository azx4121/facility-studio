from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from facility_studio.desktop import DesktopApp
from facility_studio.ahu_desktop import AHUWindow

r = tk.Tk()
a = DesktopApp(r)
r.update()
print("main", a.result is not None)
c = AHUWindow(r, a)
r.update()
print("ahu", c.result is not None)
c.close(force=True)
r.destroy()
