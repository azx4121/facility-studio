"""Independent field calculators. All functions accept explicit engineering units."""

import math
from .errors import ValidationError
from .utils import (
    number,
    sat_pa,
    MW_RATIO,
    state_trh,
    state_tw,
    dewpoint,
    enthalpy,
    CFM_TO_CMH,
    US_RT_KW,
    JRT_KW,
    G,
    duct_selection,
    water_selection,
)
from .engine import wetbulb

UNITS = {
    "風量": {"CMH": 1.0, "CFM": CFM_TO_CMH, "L/s": 3.6, "m³/s": 3600.0},
    "水量": {
        "LPM": 1.0,
        "m³/h": 1000 / 60,
        "L/s": 60.0,
        "US GPM": 3.785411784,
        "UK GPM": 4.54609,
    },
    "壓力": {
        "Pa": 1.0,
        "kPa": 1000.0,
        "bar": 100000.0,
        "psi": 6894.757293168,
        "kgf/cm²": 98066.5,
        "mmAq": G,
        "mH₂O": 1000 * G,
        "Torr": 101325 / 760,
    },
    "冷熱功率": {
        "kW": 1.0,
        "W": 0.001,
        "kcal/h": 4.1868 / 3600,
        "BTU(IT)/h": 1055.05585262 / 3600000,
        "US RT": US_RT_KW,
        "日本冷凍噸": JRT_KW,
    },
    "長度": {"mm": 1.0, "cm": 10.0, "m": 1000.0, "inch": 25.4, "ft": 304.8},
    "溫度差（升溫／降溫）": {"K": 1.0, "°C差": 1.0, "°F差": 5 / 9},
    "閥門流量係數（Kv／Cv）": {"Kv": 1.0, "Cv(US)": 0.865},
    "溫度": {"°C": 1.0, "°F": 1.0, "K": 1.0},
}

UNIT_ALIASES = {"溫差": "溫度差（升溫／降溫）", "Kv/Cv": "閥門流量係數（Kv／Cv）"}
UNIT_HELP = {
    "溫度差（升溫／降溫）": "換算升溫／降溫的幅度。例如冰水12→7°C，溫差5°C＝5K＝9°F差；不加32或273.15。若要換算某個溫度，請選『溫度』。",
    "閥門流量係數（Kv／Cv）": "Kv／Cv表示閥門通流能力，通常查閥門型錄。Kv：水在壓差1bar下的m³/h；Cv(US)：水在壓差1psi下的US GPM。Kv≈0.865×Cv(US)，不是管徑或壓力。",
    "溫度": "換算溫度本身，例如25°C＝77°F＝298.15K；若要換算升溫或降溫的幅度，請選『溫度差（升溫／降溫）』。",
    "壓力": "只換算單位，保持原來的表壓／絕對壓基準；表壓轉絕對壓需另外加當地大氣壓。",
}


def convert_all(category, value, unit):
    category = UNIT_ALIASES.get(category, category)
    x = number(value, "value")
    if category not in UNITS or unit not in UNITS[category]:
        raise ValidationError("不支援的換算單位", "unit")
    if category == "溫度":
        c = (x - 32) * 5 / 9 if unit == "°F" else x - 273.15 if unit == "K" else x
        if c < -273.15:
            raise ValidationError("溫度不可低於絕對零度", "value")
        return {"°C": c, "°F": c * 9 / 5 + 32, "K": c + 273.15}
    base = x * UNITS[category][unit]
    return {u: base / factor for u, factor in UNITS[category].items()}


PSY_MODES = ["乾球＋RH", "乾球＋濕球", "乾球＋露點", "焓＋含濕比"]


def psychrometric(mode, first, second, pressure=101.325):
    p = number(pressure, "pressure", 60, 120)
    if mode not in PSY_MODES:
        raise ValidationError("不支援的空氣狀態組合", "mode")
    x = number(first, "first")
    y = number(second, "second")
    if mode != "焓＋含濕比":
        x = number(x, "first", -60, 90)
    if mode == "乾球＋RH":
        s = state_trh(x, number(y, "second", 0, 100), p)
    elif mode == "乾球＋露點":
        y = number(y, "second", -100, 90)
        if y > x + 1e-7:
            raise ValidationError("露點不能高於乾球", "second")
        y = min(y, x)
        # Dew/frost point can be colder than the dry-bulb operating range.
        # Use the saturation-pressure correlation directly instead of treating
        # the dew point as a separate supported air state.
        pw = sat_pa(y)
        if pw >= p * 1000:
            raise ValidationError("露點水蒸氣分壓不得達到總壓", "second")
        w = MW_RATIO * pw / (p * 1000 - pw)
        s = state_tw(x, w, p)
    elif mode == "焓＋含濕比":
        w = number(y, "second", 0, 0.5 * 1000) / 1000
        s = state_tw((x - 2501 * w) / (1.006 + 1.86 * w), w, p)
    else:
        state_trh(x, 0, p)
        lower = wetbulb(x, 0, p)
        if y > x + 1e-7 or y < lower - 1e-7:
            raise ValidationError("濕球必須介於零濕度濕球下限與乾球之間", "second")
        lo, hi = 0.0, 100.0
        for _ in range(75):
            mid = (lo + hi) / 2
            if wetbulb(x, mid, p) > y:
                hi = mid
            else:
                lo = mid
        s = state_trh(x, (lo + hi) / 2, p)
    return dict(
        s,
        dewpoint_c=dewpoint(s["w"], p) if s["w"] > 0 else None,
        wetbulb_c=wetbulb(s["t"], s["rh"], p),
        pressure_kpa=p,
    )


def mix_air(t1, rh1, flow1, t2, rh2, flow2, pressure=101.325):
    p = number(pressure, "pressure", 60, 120)
    a = state_trh(number(t1, "t1", -60, 90), number(rh1, "rh1", 0, 100), p)
    b = state_trh(number(t2, "t2", -60, 90), number(rh2, "rh2", 0, 100), p)
    m1 = number(flow1, "flow1", 0) / 3600 / a["v_da"]
    m2 = number(flow2, "flow2", 0) / 3600 / b["v_da"]
    m = m1 + m2
    if m <= 0:
        raise ValidationError("兩股風量不可同時為零", "flow1")
    w = (m1 * a["w"] + m2 * b["w"]) / m
    h = (m1 * a["h"] + m2 * b["h"]) / m
    s = state_tw((h - 2501 * w) / (1.006 + 1.86 * w), w, p)
    return dict(
        state=s,
        mass_da_kg_s=m,
        flow_out_cmh=m * s["v_da"] * 3600,
        mass1_da_kg_s=m1,
        mass2_da_kg_s=m2,
        basis="各股輸入 CMH 以各自狀態為基準；乾空氣質量守恆",
    )


def air_process(t1, rh1, t2, rh2, flow, pressure=101.325):
    p = number(pressure, "pressure", 60, 120)
    a = state_trh(number(t1, "t1", -60, 90), number(rh1, "rh1", 0, 100), p)
    b = state_trh(number(t2, "t2", -60, 90), number(rh2, "rh2", 0, 100), p)
    m = number(flow, "flow", 0) / 3600 / a["v_da"]
    return dict(
        inlet=a,
        outlet=b,
        mass_da_kg_s=m,
        net_air_kw=m * (b["h"] - a["h"]),
        net_moisture_kg_h=m * (b["w"] - a["w"]) * 3600,
        basis="正值為加入空氣；此為兩點淨變化，不能代替分段冷量與再熱容量",
    )


def water_heat(solve, first, second, rho=1000.0, cp=4.1868):
    rho = number(rho, "rho", 100, 2000)
    cp = number(cp, "cp", 0.1, 10)
    a = number(first, "first", 0)
    b = number(second, "second", 0)
    factor = rho * cp / 60000
    if solve == "熱量 kW":
        flow, dt = a, b
        kw = flow * dt * factor
    elif solve == "流量 LPM":
        kw, dt = a, b
        if dt <= 0:
            raise ValidationError("反算流量時溫差必須大於零", "second")
        flow = kw / (factor * dt)
    elif solve == "溫差 K":
        kw, flow = a, b
        if flow <= 0:
            raise ValidationError("反算溫差時流量必須大於零", "second")
        dt = kw / (factor * flow)
    else:
        raise ValidationError("未知反算目標", "solve")
    return dict(
        kw=kw,
        lpm=flow,
        delta_t=dt,
        us_rt=kw / US_RT_KW,
        formula="Q[kW]=LPM/60000 × ρ[kg/m³] × cp[kJ/(kg·K)] × ΔT[K]",
    )


def pipe_velocity(flow_lpm, inner_diameter_mm):
    q = number(flow_lpm, "flow", 0) / 60000
    d = number(inner_diameter_mm, "diameter", 0.01, 10000) / 1000
    return dict(
        velocity_mps=q / (math.pi * d * d / 4),
        area_m2=math.pi * d * d / 4,
        formula="v=Q/(πD內²/4)；名目 DN／英吋不能代替實際內徑",
    )


def valve(solve, first, second, specific_gravity=1.0):
    a = number(first, "first", 0)
    b = number(second, "second", 0)
    sg = number(specific_gravity, "sg", 0.01, 20)
    if solve == "Kv":
        q, dp = a, b
        if dp <= 0:
            raise ValidationError("反算 Kv 時壓差需大於零", "second")
        kv = q / math.sqrt(dp / sg)
    elif solve == "流量 m³/h":
        kv, dp = a, b
        q = kv * math.sqrt(dp / sg)
    elif solve == "壓差 bar":
        q, kv = a, b
        if kv <= 0:
            raise ValidationError("Kv 必須大於零", "second")
        dp = sg * (q / kv) ** 2
    else:
        raise ValidationError("未知反算目標", "solve")
    return dict(
        kv=kv,
        cv_us=kv / 0.865,
        flow_m3h=q,
        drop_bar=dp,
        formula="q[m³/h]=Kv√(Δp[bar]/SG)；僅不可壓縮液體、非汽化／阻塞流初估",
    )


def energy_cost(power_kw, hours_per_day, days, load_fraction, rate):
    kw = number(power_kw, "power", 0)
    hours = number(hours_per_day, "hours", 0, 24)
    days = number(days, "days", 0, 366)
    load = number(load_fraction, "load", 0, 1)
    rate = number(rate, "rate", 0)
    kwh = kw * hours * days * load
    return dict(
        kwh=kwh,
        cost=kwh * rate,
        formula="電量=輸入kW×每日小時×天數×平均負載比例；費用=電量×自填單價，不含需量／時間電價",
    )
