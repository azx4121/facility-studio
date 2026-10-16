"""100 distinct synthetic cleanrooms, both seasons, Facility Studio V5.6.0.

Run Windows/macOS source in separate processes. No EXE/DMG/Tk GUI is executed.
Generate and freeze the manifest before calculating; all original cases remain.
Only explicitly witnessed engineering limits count as expected rejections.
"""
import argparse
import copy
import hashlib
import gzip
import json
import math
import platform
import random
import statistics
import sys
import tempfile
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--platform', choices=['windows', 'macos'], required=True)
parser.add_argument('--manifest', type=Path, required=True)
parser.add_argument('--generate', action='store_true')
parser.add_argument('--output', type=Path)
parser.add_argument('--repeat', type=int, default=20)
parser.add_argument('--seed', type=int, default=55820261011,
                    help='Synthetic input seed; default reproduces the original recipes')
args = parser.parse_args()
sys.path.insert(0, str(args.source / args.platform))
from facility_studio import api as api
from facility_studio.field_state import main_inactive
from facility_studio.inactive_acceptance import payload
from facility_studio.services import independent_domains
from facility_studio.data import WIRE_DB, NFB_SIZES
from types import SimpleNamespace

SEED = args.seed
MAIN_COMMIT = None  # Local test before the GitHub commit; module hashes are recorded separately.
TREE = None
assert api.VERSION == '5.6.0', api.VERSION

def peak_memory_mib():
    """Peak resident process memory; platform APIs report different units."""
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                        ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t)]

        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,
                                               ctypes.POINTER(ProcessMemoryCounters),
                                               wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(),
                                         ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.PeakWorkingSetSize / (1024 * 1024)
    import resource
    maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return maximum / (1024 * 1024 if sys.platform == 'darwin' else 1024)

def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()

def saturation(t):
    """Reference saturation pressure in Pa, independently evaluated."""
    k = t + 273.15
    coefficients = ([-5674.5359/k, 6.3925247, -.009677843*k,
                     6.2215701e-7*k**2, 2.0747825e-9*k**3,
                     -9.484024e-13*k**4, 4.1635019*math.log(k)]
                    if t <= .01 else
                    [-5800.2206/k, 1.3914993, -.048640239*k,
                     4.1764768e-5*k**2, -1.4452093e-8*k**3,
                     6.5459673*math.log(k)])
    return math.exp(math.fsum(coefficients))

def reference_state(t, rh, p):
    vapor = saturation(t) * rh / 100
    w = .621945 * vapor / (p*1000 - vapor)
    v = .287042 * (t + 273.15) * (1 + w/.621945) / p
    return dict(t=t, w=w, h=1.006*t + w*(2501+1.86*t), v_da=v,
                rho_moist=(1+w)/v)

def reference_rh(t, w, p):
    return 100 * p*1000*w/(.621945+w)/saturation(t)

def reference_dewpoint(w, p):
    vapor = p*1000*w/(.621945+w)
    lo, hi = -90.0, 90.0
    for _ in range(110):
        mid = (lo+hi)/2
        if saturation(mid) < vapor:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2

def reference_design(project):
    """Independent room/exhaust/heat budget, not application result values."""
    i = project['inputs']; n = lambda k: float(i[k])
    room = reference_state(n('ra_t'), n('ra_rh'), n('atm_kpa'))
    people = n('ppl_A') + n('ppl_B')
    zones = {}
    for z, keys in [('A', ['en_gap_L','en_gap_W','en_door_A','en_door_F']),
                    ('B', ['gap_B_L','gap_B_W','door_B_A','door_B_F'])]:
        area = n('en_L_'+z)*n('en_W_'+z); volume = area*n('en_H_'+z)
        circulation = (volume*n('en_ach_'+z) if i['mode_'+z]=='ACH'
                       else area*n('face_'+z)*n('coverage_'+z)*3600)
        speed = n('leak_cd')*math.sqrt(2*n('en_p_'+z)/room['rho_moist'])
        gl, gw, da, df = map(n, keys)
        leak = speed*(gl*gw*3600+da*df*n('door_open_seconds')) if area else 0
        zones[z] = dict(area=area, volume=volume, cmh=circulation, leak=leak)
    area = sum(x['area'] for x in zones.values())
    circulation = sum(x['cmh'] for x in zones.values())
    ffu = math.ceil(circulation/n('ffu_cmh')-1e-12)
    lighting_qty = math.ceil(n('light_lux')*area/(n('light_lm')*n('light_u')*n('light_m'))-1e-12)
    gross = n('eq_kw')*n('eq_rt')/100
    pcw = n('pcw_n')*n('pcw_lpm')/60000*n('water_rho')*n('water_cp')*n('pcw_dt')
    net = gross - pcw - gross*n('exh_ratio')/100
    internal = net+people*n('people_sensible_w')/1000+lighting_qty*n('light_w')/1000+n('oven_kw')+n('fan_room_kw')+ffu*n('ffu_w')/1000
    factor = .001 if i['u_unit']=='W/(m²·K)' else 4.1868/3600
    summer_qs = internal+n('en_wall')*n('wall_u')*(n('oa_t')-n('ra_t'))*factor+n('en_floor')*n('floor_u')*(n('floor_adj_t')-n('ra_t'))*factor+n('solar_kw')
    winter_qs = internal*n('winter_gain_ratio')/100+n('en_wall')*n('wall_u')*(n('ow_t')-n('ra_t'))*factor+n('en_floor')*n('floor_u')*(n('winter_floor_adj_t')-n('ra_t'))*factor+n('winter_solar_kw')
    moist = people*n('people_latent_w')/1000/2501
    if i['latent_mode']=='已知產濕量 kg/h':
        moist += n('process_moisture_kg_h')/3600
    elif i['latent_mode']=='已知潛熱 kW':
        moist += n('process_latent_kw')/2501
    nominal_exhaust = sum(n(k+'_q')*(1 if i['u_'+k]=='CMH' else 1.69901079552)
                          for k in ['gex','sex','aex','vex','hex'])
    exhaust = nominal_exhaust*(1+n('exhaust_margin_pct')/100)
    pv = n('pv_q')*{'SLPM':1,'SCFM':28.316846592,'CMH':1000/60}[i['u_pv']]/1000*60*n('gas_std_kpa')/n('atm_kpa')*(n('ra_t')+273.15)/(n('gas_std_t')+273.15)*n('pv_room_fraction')
    minimum = max(sum(x['leak'] for x in zones.values())+n('prd_q')+exhaust+pv,
                  people*n('oa_per_person'))
    minw = reference_state(n('chw2_in')+n('coil_approach'),100,n('atm_kpa'))['w']
    min_mass = (n('en_manual_oa') or minimum)/room['v_da']/3600
    need_mass = moist/(room['w']-minw) if room['w'] > minw else math.inf
    mass = min_mass if n('en_manual_oa') else max(min_mass,need_mass*1.05)
    # Independent reference for schema-12 topology. Legacy recipes without an
    # explicit topology retain their original independent circulation model.
    oa_cmh = mass * room['v_da'] * 3600
    plenum = i.get('ffu_topology') == 'MAU入靜壓箱經FFU送風'
    add_oa = plenum and i.get('ffu_airflow_basis') == '室內基本循環（另加OA）'
    ffu_total = circulation + oa_cmh if add_oa else circulation
    dcc_return = circulation if (not plenum or add_oa) else circulation - oa_cmh
    if math.isfinite(ffu_total):
        final_ffu = math.ceil(ffu_total/n('ffu_cmh'))
        extra_fan_kw = (final_ffu - ffu) * n('ffu_w') / 1000
        ffu = final_ffu
        internal += extra_fan_kw
        summer_qs += extra_fan_kw
        winter_qs += extra_fan_kw * n('winter_gain_ratio') / 100
    else:
        ffu_total = dcc_return = None  # Incompatible ADP is rejected before sizing.
    return dict(room=room,zones=zones,circulation=circulation,ffu=ffu,
                ffu_total=ffu_total,dcc_return=dcc_return,
                lighting_qty=lighting_qty,internal=internal,pcw_kw=pcw,
                summer_qs=summer_qs,winter_qs=winter_qs,moisture=moist,
                nominal_exhaust_cmh=nominal_exhaust,exhaust_cmh=exhaust,
                minimum_oa_cmh=minimum,min_w=minw,min_mass=min_mass,
                necessary_mass=need_mass,mass=mass)

def expected_constraint(project, ref):
    """Witness only known incompatible design inputs before application run."""
    i=project['inputs']; n=lambda k:float(i[k]); p=n('atm_kpa')
    def reject(prefix, field, witness):
        return dict(kind='engineering_rejection',prefix=prefix,field=field,witness=witness)
    if n('en_manual_oa') and n('en_manual_oa') < ref['minimum_oa_cmh']-1e-6:
        return reject('指定外氣 ', 'en_manual_oa',dict(specified_cmh=n('en_manual_oa'),minimum_cmh=ref['minimum_oa_cmh']))
    if ref['moisture'] and ref['min_w'] >= ref['room']['w']:
        return reject('可達含濕量不足以處理室內產濕', 'chw2_in',dict(minimum_w=ref['min_w'],room_w=ref['room']['w']))
    if n('en_manual_oa') and ref['min_mass']+1e-9 < ref['necessary_mass']:
        return reject('指定外氣不足以在二段 ADP 下維持室內濕度', 'en_manual_oa',dict(specified_mass=ref['min_mass'],required_mass=ref['necessary_mass']))
    enter=reference_state(n('oa_t'),n('oa_rh'),p)
    ts=n('mau_supply_t'); ws=ref['room']['w']-ref['moisture']/ref['mass']
    s1=enter
    if i['pre_mode']=='自動旁通因子估算':
        adp=reference_state(n('chw1_in')+n('adp_approach'),100,p)
        t1=min(enter['t'],max(n('pre_t'),adp['t']))
        if t1 < enter['t']-1e-8:
            if enter['w'] <= adp['w']:
                s1=dict(t=t1,w=enter['w'],h=1.006*t1+enter['w']*(2501+1.86*t1))
            else:
                hv=2501+1.86*t1
                denominator=enter['h']-adp['h']-(enter['w']-adp['w'])*hv
                bf=(1.006*t1+adp['w']*hv-adp['h'])/denominator
                bf=min(1,max(0,bf))
                w=bf*enter['w']+(1-bf)*adp['w']; h=bf*enter['h']+(1-bf)*adp['h']
                t=(h-2501*w)/(1.006+1.86*w)
                rh=reference_rh(t,w,p)
                if rh > 100+1e-6:
                    return reject('空氣狀態超飽和：','pre_t',dict(stage='summer C1',temperature=t,rh=rh))
                s1=dict(t=t,w=w,h=h)
    wc=min(s1['w'],ws)
    tc=min(reference_dewpoint(wc,p),s1['t'],ts) if wc < s1['w']-1e-10 else min(s1['t'],ts)
    summer_heat=ref['mass']*(1.006+1.86*wc)*(ts-tc)
    summer_humid=ref['mass']*(ws-wc)
    if summer_heat>1e-6 and i['allow_reheat']=='0':
        return reject('此工況需要加熱／再熱','allow_reheat',dict(season='summer',heat_kw=summer_heat))
    if summer_humid>1e-9 and i['allow_humidify']=='0':
        return reject('此工況需要加濕','allow_humidify',dict(season='summer',humid_kg_s=summer_humid))
    winter_w=ref['room']['w']-ref['moisture']*n('winter_moisture_ratio')/100/ref['mass']
    winter_t=max(ts,n('ra_t')-ref['winter_qs']/(ref['mass']*(1.006+1.86*winter_w)))
    winter_enter=reference_state(n('ow_t'),n('ow_rh'),p)
    winter_wc=min(winter_enter['w'],winter_w)
    winter_tc=(min(reference_dewpoint(winter_wc,p),winter_enter['t'],winter_t)
               if winter_wc < winter_enter['w']-1e-10 else min(winter_enter['t'],winter_t))
    winter_heat=ref['mass']*(1.006+1.86*winter_wc)*(winter_t-winter_tc)
    if winter_heat>1e-6 and i['allow_reheat']=='0':
        return reject('此工況需要加熱／再熱','allow_reheat',dict(season='winter',heat_kw=winter_heat))
    if ref['mass']*(winter_w-winter_wc)>1e-9 and i['allow_humidify']=='0':
        return reject('此工況需要加濕','allow_humidify',dict(season='winter',humid_kg_s=ref['mass']*(winter_w-winter_wc)))
    return dict(kind='calculation',witness='No independently identified input incompatibility')

FAMILIES=['一般潔淨區','高潔淨循環','高覆蓋送風','高製程顯熱','濕製程產濕',
          '低濕度控制','高溫高濕外氣','寒冷冬季控制','強排氣與頻繁開門','大型無塵室']

def generate_cases():
    rng=random.Random(SEED); cases=[]
    for g,family in enumerate(FAMILIES):
        for j in range(10):
            number=g*10+j+1
            p=api.default_project(); i=p['inputs']
            length=round(10+g*3+j*2+rng.uniform(0,1),2)
            width=round(8+g+j*.8+rng.uniform(0,1),2)
            height=round(3+(j%4)*.35,2)
            room_t=round(22+(j%5)*.5,2); room_rh=45+(j%5)*2.5
            climate=(30+j*.65,50+(j%4)*5,4+(j%4)*2,45+(j%5)*7)
            ach=35+j*3; klass='Class 10,000'; heat_density=.20+j*.015
            if g==1: ach=120+j*12;klass='Class 100'
            if g==2: ach=350+j*15;klass='Class 10'
            if g==3: ach=80+j*10;heat_density=.8+j*.22;klass='Class 1,000'
            if g==4: ach=65+j*7;klass='Class 1,000'
            if g==5: room_rh=[20,25,28,30,32,34,36,38,40,42][j];ach=65+j*6;klass='Class 1,000'
            if g==6: climate=(35+j*.6,75+(j%4)*5,5+j*.3,60+(j%3)*10);ach=80+j*6;klass='Class 1,000'
            if g==7: climate=(29+j*.5,55+(j%3)*5,-20+j*2.5,35+(j%4)*15);ach=70+j*6;klass='Class 1,000'
            if g==8: ach=80+j*8;heat_density=.5+j*.06;klass='Class 1,000'
            if g==9:
                length=80+j*12; width=25+j*2.8; height=4+(j%3)*.5
                ach=60+j*10;heat_density=.25+j*.07;klass='Class 1,000'
            area=length*width; side_area=round(area*(.05+.01*(j%4)),2)
            updates=dict(project_name=f'CR{number:03d} {family} {j+1}',
                sys_type='MAU+FFU+DCC (全外氣/無塵室)',atm_kpa=[101.325,100,98,94,88][j%5],
                oa_t=climate[0],oa_rh=climate[1],ow_t=climate[2],ow_rh=climate[3],
                ra_t=room_t,ra_rh=room_rh,mau_supply_t=room_t if g in (7,8) else room_t-.5,
                en_L_A=length,en_W_A=width,en_H_A=height,en_ach_A=ach,c_a=klass,
                en_L_B=round(side_area/5,3),en_W_B=5,en_H_B=3.0,en_ach_B=25+j*2,c_b='Class 10,000',
                mode_A='截面風速' if g==2 else 'ACH',mode_B='ACH',
                face_A=.25+j*.02,coverage_A=.72+j*.025,
                en_p_A=10+j*2 if g!=8 else 25+j*4,en_p_B=5+j,
                en_gap_L=8+j*2,en_gap_W=.002+(j%3)*.001,en_door_A=2.4,
                en_door_F=2+j*2 if g!=8 else 15+j*5,gap_B_L=6+j,
                gap_B_W=.002,door_B_A=1.9,door_B_F=1+j,
                door_open_seconds=4+j%5,leak_cd=.60+(j%4)*.03,
                ppl_A=max(2,math.ceil(area/(40-j*1.5))),ppl_B=1+j%4,
                oa_per_person=18+(j%5)*3,prd_q=100+(j%5)*100,en_manual_oa=0,
                ffu_cmh=800+(j%5)*150,ffu_w=65+j*7,sf=10+j%4*5,
                en_dcc_rt=3+(j%4)*2,dccw_in=18+(j%3)*.5,dccw_dp_margin=1,
                dt_dccw=2.0+(j%3)*.25,dcc_air_approach=.75,
                dcc_airflow_mode='沿用 FFU 循環',dcc_airflow_cmh=0,
                pre_mode='停用／旁通' if j%3==2 else '自動旁通因子估算',
                chw1_in=12,adp_approach=1,pre_t=28+(j%3),pre_rh=70,
                chw1_dt=4,chw2_in=5+(j%3)*.5,coil_approach=.8,dt_chw=4,
                allow_reheat=1,allow_humidify=1,
                eq_kw=round(area*heat_density,3),eq_rt=80+(j%5)*5,exh_ratio=5+j%4*5,
                pcw_n=0,pcw_lpm=0,pcw_dt=4,oven_kw=round(area*.01,3),
                latent_mode='沒有額外產濕',process_moisture_kg_h=0,
                people_sensible_w=70+(j%3)*5,people_latent_w=45+(j%4)*5,
                light_lux=300+(j%5)*100,light_lm=5000,light_w=40+(j%3)*5,
                light_u=.7,light_m=.8,u_unit='W/(m²·K)',
                en_wall=round(2*(length+width)*height*.4,3),wall_u=.5+(j%3)*.2,
                en_floor=round(area+side_area,3),floor_u=.3+(j%3)*.1,
                floor_adj_t=room_t+1,winter_floor_adj_t=room_t-1,
                solar_kw=round(area*.003,3),fan_room_kw=round(area*.008,3),
                winter_gain_ratio=65+(j%5)*7,winter_moisture_ratio=70+(j%4)*10,winter_solar_kw=0,
                winter_model='室內熱濕平衡（定風量）',
                gex_q=round(area*(1.5+(j%3)*.5),3),sex_q=0,aex_q=0,vex_q=0,hex_q=0,
                exhaust_margin_pct=5+j%4*5,pv_q=10+j*5,pv_room_fraction=.5,
                gas1_q=0,gas2_q=0,gas3_q=0,upw_q=0,
                e_up_eq=round(area*heat_density*(80+(j%5)*5)/100,3),e_up_oven=round(area*.01,3),
                e_np_fan=round(area*.03,3),e_np_heat=0,e_np_humid=0,
                e_np_exh=round(area*.02,3),e_np_pump=round(area*.01,3),
                e_volt='3Φ4W 380/220V',e_pf=.9,e_length_m=20+j*8,e_drop_limit_pct=3,
                duct_shape='圓管' if j%2 else '方管',water_velocity_max=1.5+(j%4)*.25)
            if g==3 and j>=5:
                updates.update(dcc_airflow_mode='獨立 DCC 循環',dcc_airflow_cmh=round(area*15,3))
            if g==4:
                updates.update(latent_mode='已知產濕量 kg/h',process_moisture_kg_h=10+j*12,
                               sex_q=round(area*2,3),aex_q=round(area*.7,3),exh_ratio=15)
                count=max(1,math.ceil(area/150))
                actual=updates['eq_kw']*updates['eq_rt']/100
                updates.update(pcw_n=count,pcw_lpm=round(actual*.2*60000/(count*1000*4.1868*4),6))
            if g==5:
                updates.update(chw2_in=1.2,coil_approach=.5,pre_mode='停用／旁通',
                               dccw_in=13,dt_dccw=2,latent_mode='已知產濕量 kg/h',
                               process_moisture_kg_h=3+j*2)
            if g==6:
                updates.update(pre_mode='自動旁通因子估算' if j<5 else '停用／旁通',
                               pre_t=22+j*.35,chw1_in=14,adp_approach=1)
            if g==7:
                if j==7: updates['allow_humidify']=0
                if j>=8: updates['allow_reheat']=0
            if g==8:
                updates.update(gex_q=round(area*6,3),sex_q=round(area*3,3),vex_q=round(area*2,3),
                               pre_mode='停用／旁通')
                if j<3: updates['en_manual_oa']=[50,200,500][j]
            if g==9:
                updates.update(pre_mode='停用／旁通',gex_q=round(area*3.5,3),
                               latent_mode='已知產濕量 kg/h',process_moisture_kg_h=20+j*12)
                if j==8: updates.update(chw_link='獨立輸入',chw_q=3)
                if j==9: updates.update(dccw_in=room_t+.5)
            i.update({k:format(v,'.12g') if isinstance(v,(float,int)) else v for k,v in updates.items()})
            for item in p['provenance'].values():
                item.update(source='使用者輸入',note='合成無塵室測試設定；不是現場量測或設備認證')
            for key,conf in p['pressure_drop'].items():
                conf.update(length_m=str(30+j*13+g*8),estimate_mode='詳細計算' if j%2 else '簡易估算',
                            equipment_known='尚無資料（不含設備）' if j==9 else '已知設備壓差',
                            equipment_drop='3' if key in ('MCHW','CHW','DCCW','PCW','HW') else '350',
                            static_m=str(5+j),sum_k=str(3+j*.5),fitting_mode='直接 K 值',
                            efficiency=format(.60+(j%5)*.04,'.3f'))
            ref=reference_design(p); expectation=expected_constraint(p,ref)
            # Non-finite reference mass is solely an incompatible-ADP witness.
            if math.isinf(ref['necessary_mass']):
                ref['necessary_mass']=None; ref['mass']=None
            cases.append(dict(id=f'CR{number:03d}',family=family,project=p,
                              physical_input_sha256=digest({k:v for k,v in i.items() if k!='project_name'}),
                              reference=ref,expectation=expectation))
    assert len(cases)==100 and len({c['physical_input_sha256'] for c in cases})==100
    return cases

if args.generate:
    assert args.manifest.suffix != '.gz', 'Generate a .json manifest, then optionally gzip the frozen bytes'
    assert not args.manifest.exists(), 'Refuse to replace a frozen manifest'
    cases=generate_cases()
    data=dict(version=api.VERSION,main_commit=MAIN_COMMIT,tree=TREE,seed=SEED,
              scope='100 synthetic MAU+FFU+DCC cleanroom projects; summer and winter',
              generated_utc=datetime.now(timezone.utc).isoformat(),cases=cases)
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    args.manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),
                             encoding='utf-8', newline='\n')
    print(json.dumps(dict(scenarios=100,families=Counter(c['family'] for c in cases),
                          expected=Counter(c['expectation']['kind'] for c in cases),
                          manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest()),ensure_ascii=False))
    sys.exit(0)

assert args.output and args.repeat>=1
manifest_bytes=args.manifest.read_bytes()
if args.manifest.suffix == '.gz':
    manifest_bytes = gzip.decompress(manifest_bytes)
manifest=json.loads(manifest_bytes)
cases=copy.deepcopy(manifest['cases'])
# Preserve the original manifest. Migrate old projects before mutating inactive fields.
# Expectations change only for the newly structured C1 diagnostic.
# The frozen physical inputs and original manifest bytes remain untouched.
for case in cases:
    if case['expectation'].get('prefix') == '空氣狀態超飽和：':
        case['expectation']['field'] = 'pre_t'
assert len(cases)==100 and len({c['physical_input_sha256'] for c in cases})==100
checks=[]; results=[]; timings=[]; call_count=0; isolated_calls=0; domain_calls=0

def electrical_limit_witness(p):
    i=p['inputs']
    # These frozen recipes use standard ambient/conductor ranges and 60 C
    # terminals. Even the largest eight parallel runs cannot protect >2000 A:
    # table ampacity is 8*300=2400 A, while the next breaker is 2500 A.
    assert i['e_temp']=='35℃ 以下 (標準)' and i['e_pipe']=='3根以下 (標準)' and i['e_terminal_c']=='60'
    upper_ampacity=8*max(min(x['PVC_A'],x['XLPE_A']) for x in WIRE_DB if x['size_mm2']>=50)
    upper_protection=max(x for x in NFB_SIZES if x<=upper_ampacity)
    kw=float(i['e_up_eq'])+float(i['e_up_oven'])
    current=kw*1000/(math.sqrt(3)*380*float(i['e_pf']))
    if current>upper_protection+1e-9:
        return dict(panel='UP',demand_kw=kw,current_a=current,
                    table_ampacity_max_a=upper_ampacity,protectable_current_max_a=upper_protection,
                    next_breaker_a=min(x for x in NFB_SIZES if x>upper_protection))
    return None

def check(name,ok,detail=None):
    item=dict(name=name,passed=bool(ok))
    if detail is not None: item['detail']=detail
    checks.append(item)
    if not ok: raise AssertionError(name+': '+str(detail))

def close(name,actual,expected,tol=1e-7):
    check(name,math.isclose(actual,expected,rel_tol=tol,abs_tol=tol),dict(actual=actual,expected=expected))

def finite(x,path='result'):
    if isinstance(x,float):
        if not math.isfinite(x): raise AssertionError('Non-finite '+path)
    elif isinstance(x,dict):
        for key,value in x.items(): finite(value,path+'.'+str(key))
    elif isinstance(x,(list,tuple)):
        for j,value in enumerate(x): finite(value,path+f'[{j}]')

def execute(p):
    global call_count,isolated_calls
    start=time.perf_counter()
    try:
        call_count+=1
        r=api.calculate(p); report=str(api.report(r))
        return dict(kind='calculation',full_project_status='calculated',result=r,report=report)
    except api.ValidationError as e:
        witness=electrical_limit_witness(p)
        if str(e).startswith('UP 沒有符合載流、保護上限及壓降的候選電纜') and witness:
            isolated_calls+=1
            r=api.calculate(p,isolate_utilities=True)
            return dict(kind='calculation',full_project_status='partial_hvac_only',
                        result=r,report=None,
                        report_scope='HVAC-only result; desktop prohibits a complete project report while electrical inputs fail',
                        full_project_error=dict(error_type=type(e).__name__,message=str(e),field_name=e.field_name),
                        electrical_limit_witness=witness)
        return dict(kind='engineering_rejection',error_type=type(e).__name__,
                    message=str(e),field_name=e.field_name,code=e.code)
    finally:
        timings.append(time.perf_counter()-start)

def engineering_checks(r,case,text):
    i=r['effective_inputs']; n=lambda k:float(i[k]); ref=case['reference']; p=n('atm_kpa')
    for z in 'AB':
        for k in ['area','volume','cmh','leak']: close(z+'/'+k,r['zones'][z][k],ref['zones'][z][k])
    close('circulation',r['circulation_cmh'],ref['circulation'])
    close('FFU minimum count',r['counts']['FFU'],ref['ffu'])
    close('lighting minimum count',r['light']['qty'],ref['lighting_qty'])
    close('room sensible demand',r['qs'],ref['summer_qs'])
    close('room generated moisture',r['moisture'],ref['moisture'])
    close('room latent reference',r['ql'],ref['moisture']*2501)
    close('minimum compensating OA',r['minimum_oa_cmh'],ref['minimum_oa_cmh'])
    close('adopted dry-air mass',r['oa_mass'],ref['mass'])
    close('room referenced OA',r['oa_room_cmh'],ref['mass']*ref['room']['v_da']*3600)
    check('OA meets compensation',r['oa_room_cmh']+1e-7>=ref['minimum_oa_cmh'])
    close('additional relief',r['extra_relief_cmh'],max(0,r['oa_room_cmh']-ref['minimum_oa_cmh']))
    room=r['room']
    for s in [room,r['oa'],r['winter_oa']]:
        independent=reference_state(s['t'],s['rh'],p)
        for k in ['w','h','v_da','rho_moist']: close('psychrometric '+k,s[k],independent[k])
    for season in ['summer','winter']:
        ch=r[season]; m=ch['mass']
        close(season+'/mass',m,ref['mass'])
        for tag in ['c1','c2']:
            c=ch[tag]; a,b=c['inlet'],c['outlet']
            h=lambda s:1.006*s['t']+s['w']*(2501+1.86*s['t'])
            close(season+'/'+tag+'/energy',c['air_kw'],m*(h(a)-h(b)))
            close(season+'/'+tag+'/condensate',c['condensate_kg_s'],m*(a['w']-b['w']))
            close(season+'/'+tag+'/liquid energy',c['liquid_kw'],c['condensate_kg_s']*4.1868*b['t'])
            close(season+'/'+tag+'/water-side energy',c['water_kw'],c['air_kw']-c['liquid_kw'])
            check(season+'/'+tag+'/no invented heat or humidity',c['air_kw']>=0 and c['condensate_kg_s']>=0)
        h=lambda s:1.006*s['t']+s['w']*(2501+1.86*s['t'])
        close(season+'/total air energy',m*(h(ch['supply'])-h(ch['enter'])),
              -ch['c1']['air_kw']-ch['c2']['air_kw']+ch['reheat_kw']+ch['humid_air_kw'])
        close(season+'/total moisture',m*(ch['supply']['w']-ch['enter']['w']),
              ch['humid_kg_h']/3600-ch['c1']['condensate_kg_s']-ch['c2']['condensate_kg_s'])
        for point in [ch['enter'],ch['c1']['outlet'],ch['c2']['outlet'],ch['heat_state'],ch['supply']]:
            check(season+'/RH physical',0<=point['rh']<=100+1e-7)
            close(season+'/state RH',point['rh'],reference_rh(point['t'],point['w'],p),1e-6)
    sm=r['summer']; wm=r['winter']; wr=r['winter_room']
    close('summer room moisture',sm['mass']*(room['w']-sm['supply']['w']),ref['moisture'])
    close('summer room sensible',sm['mass']*(1.006+1.86*sm['supply']['w'])*(room['t']-sm['supply']['t'])+r['dcc_kw'],ref['summer_qs'])
    close('winter room sensible',wr['sensible_kw'],ref['winter_qs'])
    close('winter room moisture',wm['mass']*(room['w']-wm['supply']['w']),ref['moisture']*n('winter_moisture_ratio')/100)
    close('winter room balance',wm['mass']*(1.006+1.86*wm['supply']['w'])*(room['t']-wm['supply']['t'])+wr['dcc_kw'],ref['winter_qs'])
    close('winter C1 bypass',wm['c1']['air_kw'],0)
    close('DCC both seasons design',r['dcc_design_kw'],max(r['dcc_kw'],wr['dcc_kw']))
    close('DCC minimum count',r['counts']['DCC'],math.ceil(r['dcc_design_kw']*(1+n('sf')/100)/r['rt_kw']/n('en_dcc_rt')-1e-12))
    flow=ref.get('dcc_return',ref['circulation']) if i['dcc_airflow_mode']=='沿用 FFU 循環' else n('dcc_airflow_cmh')
    dcc_limit=max(0,flow)/3600/ref['room']['v_da']*(1.006+1.86*room['w'])*max(0,room['t']-n('dccw_in')-n('dcc_air_approach'))
    expected_air_pass=flow>0 and r['dcc_design_kw']<=dcc_limit+1e-6
    air_item=next(x for x in r['quality']['items'] if x['name']=='DCC 循環風量與能力')
    check('DCC insufficient airflow retained',air_item['status']==('通過' if expected_air_pass else '未達'))
    for key,w in r['water'].items():
        fluid=w['fluid_properties']
        if w['linked']:
            close(key+'/linked water',w['lpm']/60000*fluid['rho']*fluid['cp']*w['delta_t'],w['load_kw'])
        if w['lpm']:
            close(key+'/water velocity',w['velocity_mps'],w['lpm']/60000/w['runs']/(math.pi*(w['id_mm']/1000)**2/4))
            check(key+'/velocity upper bound',w['velocity_mps']<=n('water_velocity_max')+1e-8)
            check(key+'/parallel range',1<=w['runs']<=32)
        if not w['linked'] and w['capacity_kw']+1e-6<w['load_kw']:
            item=next(x for x in r['quality']['items'] if x['name']==key+' 獨立水量')
            check(key+'/undersized independent water flagged',item['status']=='未達')
    for key,d in r['ducts'].items():
        check(key+'/duct velocity',d['velocity_mps']<=n('v_'+key.lower())+1e-8)
    for key,d in r['pressure'].items():
        close(key+'/pressure sum',d['total_pa'],math.fsum(d[x] for x in ['friction_pa','local_pa','equipment_pa','static_pa']))
        close(key+'/head',d['head_m'],d['total_pa']/(d['rho']*9.80665))
        close(key+'/shaft',d['shaft_kw'],d['flow_m3s']*d['total_pa']/(1000*d['efficiency']))
        close(key+'/static ignored',d['static_pa'],0)
        if d['flow_m3s'] and not d['equipment_included']:
            item=next(x for x in r['quality']['items'] if x['name']==key+' 設備阻力')
            check(key+'/unknown equipment not treated as complete',item['status']=='待資料')
    for key,e in r['electric'].items():
        close(key+'/electrical current',e['current_a'],e['kw']*1000/(math.sqrt(3)*e['voltage']*n('e_pf')))
        if e['selected']:
            c=e['selected'];check(key+'/protection range',e['design_current_a']<=c['nfb_candidate_a']+1e-8<=c['iz_a']+1e-8)
    failed=any(x['status']=='未達' for x in r['quality']['items'])
    if failed: check('engineering failures not presented as passed',r['quality']['status']=='未達條件')
    if text is not None:
        check('report includes engineering status',r['quality']['status'] in text)
        check('report retains warnings',all(x['detail'] in text for x in r['quality']['items'] if x['status']!='通過'))
    finite(r);check('all calculated values finite',True)

class TextSink:
    def __init__(self): self.text=''
    def config(self,**kw): self.text=kw.get('text',self.text)
    def set(self,value): self.text=value

class GridSink:
    def __init__(self): self.rows={}
    def item(self,key,**kw): self.rows[key]=kw['values']

def partial_view_probe(r):
    # Exercise the actual text-rendering method without opening a Tk window.
    from facility_studio.main_view import MainView
    holder=SimpleNamespace(result=r,summary=TextSink(),psy_label=TextSink(),
        topology=TextSink(),latent_text=TextSink(),grid=GridSink(),
        result_labels={j:TextSink() for j in range(1,7)})
    MainView.render_results(holder)
    return dict(summary=holder.summary.text,psychrometric=holder.psy_label.text,
                topology=holder.topology.text,latent=holder.latent_text.text,
                pages={str(k):v.text for k,v in holder.result_labels.items()},
                pressure_rows=holder.grid.rows)

def partial_report_probe(r):
    # This robustness probe is outside the permitted desktop export path.
    # It is explicitly reported as a guard gap, never silently counted as safe.
    try:
        text=str(api.report(r))
        return dict(defensive_api_pass=False,unexpected_report_emitted=True,
                    report=text,scope='Direct report API with an isolated HVAC result')
    except api.ValidationError as e:
        return dict(defensive_api_pass=e.code == 'incomplete_result',error_type=type(e).__name__,message=str(e),code=e.code)
    except Exception as e:
        return dict(defensive_api_pass=False,error_type=type(e).__name__,message=str(e),
                    scope='Direct report API only; desktop prevents complete report export')

start_all=time.perf_counter()
for case in cases:
    start_case=time.perf_counter(); check_start=len(checks)
    row=dict(id=case['id'],family=case['family'],input_sha256=digest(case['project']),
             expectation=case['expectation'],software_pass=False)
    try:
        original=digest(case['project'])
        outcome=execute(case['project']); row['outcome']=outcome
        domain_calls+=1
        domains=independent_domains(case['project'])
        row['domain_results']=domains
        check(case['id']+'/gas domain remains usable',domains['gas']['error'] is None)
        if electrical_limit_witness(case['project']):
            check(case['id']+'/electric table limit rejected',domains['electric']['result'] is None and
                  domains['electric']['error'].startswith('UP 沒有符合載流、保護上限及壓降的候選電纜'))
        else:
            check(case['id']+'/electric domain remains usable',domains['electric']['error'] is None)
        check(case['id']+'/expected outcome',outcome['kind']==case['expectation']['kind'],
              dict(actual=outcome['kind'],expected=case['expectation']['kind']))
        if outcome['kind']=='engineering_rejection':
            expected=case['expectation']
            check(case['id']+'/specified rejection cause',outcome['message'].startswith(expected['prefix']),outcome)
            check(case['id']+'/structured rejection field',outcome['field_name']==expected['field'],outcome)
            check(case['id']+'/rejected HVAC not shown as usable',domains['hvac']['result'] is None and
                  domains['hvac']['error'].startswith(expected['prefix']))
        else:
            check(case['id']+'/HVAC preserved by desktop domain router',domains['hvac']['error'] is None)
            for key in ['room','zones','qs','ql','moisture','minimum_oa_cmh','oa_room_cmh',
                        'circulation_cmh','summer','winter','winter_room','dcc_design_kw','water','pressure']:
                check(case['id']+'/domain parity '+key,digest(domains['hvac']['result'][key])==digest(outcome['result'][key]))
            check(case['id']+'/full project table bound explicit',
                  (outcome['full_project_status']=='partial_hvac_only')==bool(electrical_limit_witness(case['project'])))
            engineering_checks(outcome['result'],case,outcome['report'])
            if outcome['full_project_status']=='partial_hvac_only':
                row['partial_text_render']=partial_view_probe(outcome['result'])
                check(case['id']+'/actual partial text rendering',bool(row['partial_text_render']['summary']))
                row['partial_report_api_probe']=partial_report_probe(outcome['result'])
                check(case['id']+'/complete report rejects partial result', row['partial_report_api_probe']['defensive_api_pass'])
            for index,value in enumerate(['','not-a-number','NaN','-999999','1e309']):
                mutated=api.migrate_project(copy.deepcopy(case['project']))
                for key in main_inactive(mutated['inputs']): mutated['inputs'][key]=value
                other=execute(mutated)
                check(case['id']+'/inactive batch '+str(index),other['kind']=='calculation' and
                      digest(payload(other['result']))==digest(payload(outcome['result'])) and
                      other['report']==outcome['report'])
                check(case['id']+'/draft preserved '+str(index),all(mutated['inputs'][key]==value for key in main_inactive(mutated['inputs'])))
            with tempfile.TemporaryDirectory() as td:
                fn=Path(td)/'cleanroom.json'
                fn.write_text(json.dumps(case['project'],ensure_ascii=False),
                              encoding='utf-8', newline='\n')
                reopened=api.read_project(fn)
                other=execute(reopened)
                check(case['id']+'/save reopen',digest(other)==digest(outcome))
        check(case['id']+'/inputs unchanged',digest(case['project'])==original)
        expected_digest=digest(outcome)
        for j in range(args.repeat-1):
            repeated=execute(case['project'])
            check(case['id']+'/repeat '+str(j+2),digest(repeated)==expected_digest)
        row.update(software_pass=True,outcome_sha256=expected_digest,
                   quality_status=outcome.get('result',{}).get('quality',{}).get('status'))
    except Exception as e:
        row.update(error_type=type(e).__name__,error_message=str(e),traceback=traceback.format_exc())
    row.update(check_count=len(checks)-check_start,seconds=time.perf_counter()-start_case)
    results.append(row)
    # Durable checkpoint after each original room; never wait without progress.
    args.output.parent.mkdir(parents=True,exist_ok=True)
    checkpoint=args.output.with_suffix('.checkpoint.json')
    checkpoint.write_text(json.dumps(dict(completed=len(results),failed=sum(not x['software_pass'] for x in results),last=row['id']),ensure_ascii=False),
                          encoding='utf-8', newline='\n')
    if len(results)%10==0: print(json.dumps(dict(completed=len(results),failed=sum(not x['software_pass'] for x in results)),ensure_ascii=False),flush=True)

elapsed=time.perf_counter()-start_all
summary=dict(version=api.VERSION,main_commit=MAIN_COMMIT,tree=TREE,
    source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((args.source/args.platform/'facility_studio').glob('*.py'))},
    source_platform=args.platform,host=platform.platform(),python=sys.version,
    finished_utc=datetime.now(timezone.utc).isoformat(),scenario_count=len(results),
    original_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    distinct_physical_input_count=len({c['physical_input_sha256'] for c in cases}),
    repeat_per_scenario=args.repeat,calculation_calls=call_count,
    isolated_hvac_calls=isolated_calls,desktop_domain_checks=domain_calls,
    total_main_calculate_calls=call_count+isolated_calls+domain_calls,
    full_project_calculation_scenarios=sum(x.get('outcome',{}).get('full_project_status')=='calculated' for x in results),
    partial_hvac_electrical_limit_scenarios=sum(x.get('outcome',{}).get('full_project_status')=='partial_hvac_only' for x in results),
    successful_calculation_scenarios=sum(x.get('outcome',{}).get('kind')=='calculation' for x in results),
    expected_engineering_rejections=sum(x.get('outcome',{}).get('kind')=='engineering_rejection' and x['software_pass'] for x in results),
    software_passed=sum(x['software_pass'] for x in results),software_failed=sum(not x['software_pass'] for x in results),
    checks=len(checks),failed_checks=sum(not x['passed'] for x in checks),
    quality_status_counts=dict(Counter(x.get('quality_status') for x in results if x.get('quality_status'))),
    partial_report_api_probe_count=sum('partial_report_api_probe' in x for x in results),
    partial_report_api_guard_failures=sum(not x['partial_report_api_probe']['defensive_api_pass'] for x in results if 'partial_report_api_probe' in x),
    seconds=elapsed,latency_ms=dict(median=statistics.median(timings)*1000,
    p95=sorted(timings)[min(len(timings)-1,int(len(timings)*.95))]*1000,max=max(timings)*1000),
    rss_peak_mib=peak_memory_mib(),
    scope=f'{platform.system()} headless {args.platform} source stress test; both seasons; no native binary or GUI execution')
args.output.write_text(json.dumps(dict(summary=summary,cases=results,checks=checks),ensure_ascii=False,indent=2,allow_nan=False),
                       encoding='utf-8', newline='\n')
print(json.dumps(summary,ensure_ascii=False),flush=True)
sys.exit(0 if summary['software_failed']==0 and summary['failed_checks']==0 and summary['partial_report_api_guard_failures']==0 else 1)
