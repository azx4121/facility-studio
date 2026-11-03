"""Numerical and headless rendering checks for the full psychrometric chart.

Run separately for each source tree. --gui adds actual Tk snapshot and viewport
checks when a display is available. Headless rendering is NOT native GUI proof.
"""
import argparse
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

parser = argparse.ArgumentParser()
parser.add_argument('--platform', choices=('windows', 'macos'), default='windows')
parser.add_argument('--output', type=Path)
parser.add_argument('--preview', type=Path)
parser.add_argument('--gui', action='store_true')
args = parser.parse_args()
root_path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_path / args.platform))
from facility_studio.air_chart import FullAirChart, full_chart_data
from facility_studio.quick_tools import psychrometric
from facility_studio.utils import sat_pa, MW_RATIO, state_tw

checks = 0

def check(value, message):
    global checks
    checks += 1
    if not value:
        raise AssertionError(message)


def state(t, rh, p=101.325):
    return psychrometric('乾球＋RH', t, rh, p)


def physical(data, t, w):
    pw = sat_pa(t)
    saturated = MW_RATIO * pw / (data['pressure_kpa']*1000 - pw)*1000 if pw < data['pressure_kpa']*1000 else math.inf
    return (data['t_min'] - 1e-8 <= t <= data['t_max'] + 1e-8 and
            -1e-7 <= w <= data['w_max_gkg'] + 1e-7 and w <= saturated + 1e-7)


cases = []
for p in (60, 80, 101.325, 120):
    for t, rh, bt, brh in ((25,50,18,90), (-60,100,-10,0), (0,100,0,100),
                           (90,10,75,90), (25,0,25,100)):
        a, b = state(t,rh,p), state(bt,brh,p)
        data = full_chart_data(a,b)
        for s in (a,b):
            check(physical(data, s['t'], s['w']*1000), 'A/B outside chart')
        check(len(data['curves']) == 10, 'Missing RH family')
        for key in ('curves','enthalpy_lines','wetbulb_lines','volume_lines','drybulb_lines','humidity_lines'):
            check(bool(data[key]), 'Empty line family '+key)
            for row in data[key]:
                pts = row['points']
                check(len(pts) >= 2, 'One-point line')
                for x,w in pts:
                    check(physical(data,x,w), f'Line outside physical domain: {key} {x} {w}')
                for x,w in pts[::max(1,len(pts)//7)] + pts[-1:]:
                    if key == 'curves':
                        actual = p*1000*w/(MW_RATIO*1000+w)/sat_pa(x)*100
                        check(abs(actual-row['rh']) < 1e-7, 'RH inversion')
                    elif key == 'enthalpy_lines':
                        actual = 1.006*x + w/1000*(2501+1.86*x)
                        check(abs(actual-row['value']) < 1e-7, 'h inversion')
                    elif key == 'volume_lines':
                        actual = .287042*(x+273.15)*(1+w/1000/MW_RATIO)/p
                        check(abs(actual-row['value']) < 1e-9, 'v inversion')
                    elif key == 'wetbulb_lines':
                        wb = row['value']; pw = sat_pa(wb)
                        ws = MW_RATIO*pw/(p*1000-pw)
                        if wb >= 0:
                            lhs=w/1000*(2501+1.86*x-4.186*wb)
                            rhs=(2501-2.326*wb)*ws-1.006*(x-wb)
                        else:
                            lhs=w/1000*(2830+1.86*x-2.1*wb)
                            rhs=(2830-.24*wb)*ws-1.006*(x-wb)
                        check(abs(lhs-rhs) < 1e-7 and x >= wb-1e-8, 'WB energy balance')
        cases.append(dict(pressure_kpa=p, a=[t,rh], b=[bt,brh],
                          bounds=[data['t_min'],data['t_max'],data['w_max_gkg']]))
# The top grid must not exceed the engine's 1 kg/kg humidity-ratio limit.
high_state=dict(state_tw(75,.99,60),pressure_kpa=60)
# Exercise the actual quick-tool engine before handing the fixed high-W
# state to the detailed chart; do not bypass wet-bulb calculation.
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_schema import defaults
high_inputs=dict(defaults('air'), temperature='75', rh=repr(high_state['rh']), atmosphere='60', compare='0')
high_result=calculate_tool('air', high_inputs)
check(abs(high_result['state']['w']-.99)<1e-12,'High-W quick tool result lost humidity')
check(high_result['state']['wetbulb_c']<75,'High-W quick tool wet bulb unavailable')
high_data=full_chart_data(high_result['state'])
check(high_data['w_max_gkg']==1000 and physical(high_data,75,990),'High-W range limit')
for invalid in (dict(state(25,50), pressure_kpa=50), dict(state(25,50), w=-1),
                dict(state(25,50), w=.5), dict(state(25,50), t=math.nan)):
    try:
        full_chart_data(invalid)
    except ValueError:
        check(True, 'Invalid rejected')
    else:
        check(False, 'Invalid state accepted')
try:
    full_chart_data(state(25,50),state(25,50,80))
except ValueError:
    check(True,'Different pressure rejected')
else:
    check(False,'Different pressure accepted')

class RecordingChart(FullAirChart):
    """Runs production draw methods but records Canvas primitives, without Tk."""
    def __init__(self, width=1440, height=900):
        self.width, self.height = width, height
        self.family='Noto Sans CJK TC'
        self.zoom=1.; self.pan_x=self.pan_y=0.;self._drag_origin=None
        self.state=None;self.comparison=None;self.plot_data=None
        self.items=[]
    def winfo_width(self): return self.width
    def winfo_height(self): return self.height
    def delete(self,*args): self.items.clear()
    def _add(self,kind,coords,options):
        self.items.append((kind,coords,options));return len(self.items)
    def create_line(self,*coords,**kw):return self._add('line',coords,kw)
    def create_text(self,*coords,**kw):return self._add('text',coords,kw)
    def create_oval(self,*coords,**kw):return self._add('oval',coords,kw)
    def create_rectangle(self,*coords,**kw):return self._add('rectangle',coords,kw)

# Very cold h/v intervals can be narrower than the regular sampling interval.
# Every dry-axis intercept strictly inside the chart must produce a line.
from facility_studio.air_chart import _ticks
for p in (60,80,101.325,120):
    d=full_chart_data(state(-60,0,p),state(90,0,p))
    for key,step,lo,hi,intercept in (
        ('enthalpy_lines',d['h_step'],1.006*-60,1.006*90+35/1000*(2501+1.86*90),lambda value:value/1.006),
        ('volume_lines',d['v_step'],.287042*213.15/p,.287042*363.15*(1+.035/MW_RATIO)/p,lambda value:value*p/.287042-273.15)):
        present={row['value'] for row in d[key]}
        for value in _ticks(lo,hi,step):
            if -60+1e-6 < intercept(value) < 90-1e-6:
                check(value in present,'Narrow cold line omitted')

chart=RecordingChart()
a,b=state(35,70),state(18,90)
chart.set_state(a,b)
initial_point=chart.point_xy
previous=(chart.state,chart.comparison,chart.plot_data)
try:
    chart.set_state(dict(a,w=.5),b)
except ValueError:
    check((chart.state,chart.comparison,chart.plot_data)==previous,'Invalid set_state changed snapshot')
else:
    check(False,'Invalid snapshot accepted')
check(len(chart.items)>400,'Detailed grid has sufficient geometry')
for tag in ('enthalpy_ruler','volume','wetbulb','humidity_tick','drybulb_tick','state_summary','snapshot_label'):
    check(any(tag in item[2].get('tags',()) for item in chart.items), 'Missing rendered '+tag)
a['t']=-50;b['w']=0
check(chart.state['t']==35 and chart.comparison['w']>0,'Snapshot mutated')
chart.zoom_at(2,*initial_point)
check(math.dist(chart.point_xy,initial_point)<1e-8,'Zoom anchor moved')
chart._start_pan(SimpleNamespace(x=200,y=200))
chart._pan(SimpleNamespace(x=240,y=230))
check(math.dist(chart.point_xy,(initial_point[0]+40,initial_point[1]+30))<1e-8,'Pan incorrect')
chart._end_pan(None)
check(chart._drag_origin is None,'Release did not end pan')
chart.fit_view()
check(chart.zoom==1 and math.dist(chart.point_xy,initial_point)<1e-8,'Fit did not reset')
for w,h in ((800,540),(1440,900),(1920,1080)):
    chart.width,chart.height=w,h;chart.redraw()
    scale,ox,oy=chart.view_transform()
    check(ox>=0 and oy>=0 and ox+1440*scale<=w+1e-8 and oy+900*scale<=h+1e-8,'Sheet cropped when fitted')
    for kind,coords,opts in chart.items:
        check(all(math.isfinite(x) for x in coords),'Nonfinite Canvas coordinates')
chart.width,chart.height=1440,900;chart.fit_view()
chart.mark_stale()
check(any(x[2].get('tags')=='stale_label' for x in chart.items),'No stale warning')
chart.set_state(state(0,100),state(0,100))
check(sum(x[2].get('tags') in ('state_point','comparison_point') for x in chart.items)==2,'Coincident state markers missing')
chart.set_state(state(35,70),state(18,90))

if args.preview:
    # Pillow rendering of the recorded production Canvas commands. Not a Tk
    # screenshot: records exact coordinates/colors/text, approximates fonts.
    from PIL import Image, ImageDraw, ImageFont
    image=Image.new('RGB',(1440,900),'white');draw=ImageDraw.Draw(image)
    for kind,coords,opts in chart.items:
        fill=opts.get('fill','#222');width=max(1,round(opts.get('width',1)))
        if kind=='line':
            pairs=list(zip(coords[::2],coords[1::2]))
            if not opts.get('dash'):
                draw.line(pairs,fill=fill,width=width)
            else:
                pattern=opts['dash'];phase=0;remaining=float(pattern[0])
                for first,last in zip(pairs,pairs[1:]):
                    length=math.dist(first,last)
                    if not length:continue
                    offset=0.
                    while offset<length-1e-10:
                        step=min(remaining,length-offset)
                        if phase%2==0:
                            a=tuple(first[i]+(last[i]-first[i])*offset/length for i in (0,1))
                            b=tuple(first[i]+(last[i]-first[i])*(offset+step)/length for i in (0,1))
                            draw.line([a,b],fill=fill,width=width)
                        offset+=step;remaining-=step
                        if remaining<1e-10:
                            phase=(phase+1)%len(pattern);remaining=float(pattern[phase])
        elif kind in ('rectangle','oval'):
            fn=draw.rectangle if kind=='rectangle' else draw.ellipse
            fn(coords,fill=fill,outline=opts.get('outline'),width=width)
        else:
            family,size,weight=opts['font'];size=abs(size)
            path='/usr/share/fonts/opentype/noto/NotoSansCJK-'+('Bold' if weight=='bold' else 'Regular')+'.ttc'
            font=ImageFont.truetype(path,size,index=3)
            text=opts['text'];box=draw.textbbox((0,0),text,font=font)
            tw,th=box[2]-box[0],box[3]-box[1]
            tile=Image.new('RGBA',(tw+6,th+6),(255,255,255,0));td=ImageDraw.Draw(tile)
            td.text((3-box[0],3-box[1]),text,font=font,fill=fill)
            if opts.get('angle'):tile=tile.rotate(opts['angle'],expand=True,resample=Image.Resampling.BICUBIC)
            tw,th=tile.size;anchor=opts.get('anchor','center')
            x,y=coords
            x-=0 if anchor in ('w','nw','sw') else tw if anchor in ('e','ne','se') else tw/2
            y-=0 if anchor in ('n','nw','ne') else th if anchor in ('s','sw','se') else th/2
            image.paste(tile,(round(x),round(y)),tile)
    args.preview.parent.mkdir(parents=True,exist_ok=True);image.save(args.preview)

if args.gui:
    import tkinter as tk
    root=tk.Tk();root.geometry('1200x800')
    live=FullAirChart(root);live.pack(fill='both',expand=True)
    a,b=state(35,70),state(18,90);live.set_state(a,b);root.update()
    initial=live.point_xy
    live.event_generate('<MouseWheel>',delta=120,x=600,y=400);root.update()
    check(live.zoom>1 and live.point_xy!=initial,'Actual wheel did not zoom')
    live.event_generate('<ButtonPress-1>',x=400,y=300)
    live.event_generate('<B1-Motion>',x=450,y=350);root.update()
    check(live.pan_x!=0,'Actual drag did not pan')
    live.fit_view();root.update();check(math.dist(live.point_xy,initial)<1e-8,'Actual fit failed')
    a['t']=-20;live.redraw();check(live.state['t']==35,'Actual snapshot mutated')
    live.mark_stale();check(bool(live.find_withtag('stale_label')),'Actual stale label missing')
    root.destroy()
    from facility_studio.simple_desktop import SimpleToolsApp
    root=tk.Tk();app=SimpleToolsApp(root);app.show_tool('air');root.update()
    page=app.pages['air'];page.variables['compare'].set('1');page.calculate();root.update()
    win=page.open_air_chart();root.update()
    snapshot=next(child for child in win.winfo_children() if isinstance(child,FullAirChart))
    original=dict(snapshot.state)
    page.variables['temperature'].set('not a temperature');page.calculate();root.update()
    check(page.result is None and page.open_air_chart() is None,'Invalid form opened stale chart')
    check(snapshot.state==original and bool(snapshot.find_withtag('snapshot_label')),'Open snapshot changed or lost label')
    page.variables['temperature'].set('30');page.calculate();root.update()
    second=page.open_air_chart();root.update()
    fresh=next(child for child in second.winfo_children() if isinstance(child,FullAirChart))
    check(fresh.state['t']==30 and snapshot.state==original,'Repeated open did not isolate snapshots')
    for key,value in high_inputs.items():page.variables[key].set(value)
    page.calculate();root.update()
    high_window=page.open_air_chart();root.update()
    high_chart=next(child for child in high_window.winfo_children() if isinstance(child,FullAirChart))
    check(abs(high_chart.state['w']-.99)<1e-12,'High-W actual window did not use fixed calculator result')
    high_window.destroy();second.destroy();win.destroy();root.destroy()

report=dict(status='passed',platform_source=args.platform,checks=checks,cases=cases,
            headless_canvas_render=True,actual_tk_gui=args.gui,native_binary_acceptance=False)
print(json.dumps(report,ensure_ascii=False,indent=2))
if args.output:
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
