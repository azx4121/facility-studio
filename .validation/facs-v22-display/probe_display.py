"""Measure advertised native Windows modes and attainable clients; no source changes."""
import ctypes as C
import json
from pathlib import Path
import sys
import time
import tkinter as tk
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'facs-v22-reviewed/native_diagnostics'))
from windows_display import NativeDisplay, RECT, describe

def main():
    output=Path(sys.argv[1]); output.parent.mkdir(parents=True,exist_ok=True)
    native=NativeDisplay()
    records=dict(before=native.metrics(),advertised_modes=[describe(m) for m in native.modes()],measurements=[])
    original=native.mode(0xffffffff)
    try:
        for wanted in ((1920,1080),(1024,768)):
            eligible=[m for m in native.modes() if (m.dmPelsWidth,m.dmPelsHeight)==wanted and m.dmBitsPerPel>=24]
            if not eligible:
                records['measurements'].append(dict(requested=wanted,error='not advertised'));continue
            mode=eligible[0]
            attempt=dict(requested=wanted,test_return=native.change(mode,test=True),windows=[])
            records['measurements'].append(attempt)
            if attempt['test_return']!=0:continue
            attempt['apply_return']=native.change(mode)
            time.sleep(.5);attempt['metrics']=native.metrics()
            if attempt['apply_return']!=0:continue
            for x,y in ((20,20),(0,0),(8,0)):
                root=tk.Tk()
                try:
                    root.geometry(f'1480x1000+{x}+{y}')
                    for _ in range(20):root.update();time.sleep(.02)
                    rectangle=RECT(); hwnd=native.api.GetAncestor(root.winfo_id(),2)
                    assert native.api.GetWindowRect(hwnd,C.byref(rectangle))
                    attempt['windows'].append(dict(anchor=[x,y],client=[root.winfo_width(),root.winfo_height()],
                        outer=[rectangle.left,rectangle.top,rectangle.right,rectangle.bottom],
                        screen=[root.winfo_screenwidth(),root.winfo_screenheight()],
                        scaling=root.tk.call('tk','scaling')))
                finally:root.destroy()
    finally:
        records['restore_return']=native.change(original); time.sleep(.5)
        records['restored']=native.metrics()
        output.write_text(json.dumps(records,indent=2),encoding='utf-8')
        print(json.dumps(records,indent=2))
    return 0 if records['restore_return']==0 and records['restored']['screen']==records['before']['screen'] else 1
if __name__=='__main__':raise SystemExit(main())
