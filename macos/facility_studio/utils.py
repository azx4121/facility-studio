from .errors import InputError
from pathlib import Path
import hashlib
import json
import math
import os
import tempfile
from .data import (
    GAS_DESIGN_VELOCITY_MPS,
    HVAC_PIPES,
    NFB_SIZES,
    PIPE_DB,
    VOLTAGE_MAP,
    WIRE_DB,
)

VERSION = "1.1.1"
CFM_TO_CMH = 1.69901079552
GPM_TO_LPM = 3.785411784
US_RT_KW = 3.5168528420667
JRT_KW = 3320 * 4.1868 / 3600
CP_DA = 1.006
CP_V = 1.86
H_V0 = 2501.0
G = 9.80665
MW_RATIO = 0.621945
EXTRA_DEFAULTS = {
    "project_name": "廠務估算專案",
    "hvac_enabled": "1",
    "atm_kpa": "101.325",
    "coil_model": "需求工況（待選機）",
    "adp_approach": "1.0",
    "coil_bf": "0.10",
    "rh_mode": "精確設定值",
    "rh_tolerance": "2",
    "allow_reheat": "1",
    "allow_humidify": "1",
    "manual_supply_cmh": "0",
    "wall_u": "1.4",
    "floor_u": "3.25",
    "u_unit": "kcal/(h·m²·K)",
    "floor_adj_t": "35",
    "solar_kw": "0",
    "people_sensible_w": "75",
    "people_latent_w": "55",
    "fan_room_kw": "0",
    "gap_B_L": "0",
    "gap_B_W": "0.01",
    "door_B_A": "0",
    "door_B_F": "0",
    "door_open_seconds": "10",
    "leak_cd": "0.65",
    "oa_per_person": "24",
    "exhaust_margin_pct": "5",
    "pv_room_fraction": "1",
    "gas_std_t": "25",
    "gas_std_kpa": "101.325",
    "gas_temp": "25",
    "gas_z_ratio": "1",
    "gas_min_barg": "5",
    "pv_min_torr": "1",
    "water_rho": "1000",
    "water_cp": "4.1868",
    "water_mu": "0.001",
    "water_velocity_max": "2.0",
    "water_roughness_mm": "0.045",
    "water_selection": "流速上限",
    "chw_link": "獨立輸入",
    "dccw_in_c": "15",
    "dccw_dp_margin": "1",
    "v_aex": "10",
    "v_hex": "12",
    "duct_shape": "方管",
    "air_mu": "0.0000181",
    "air_rho": "1.2",
    "duct_roughness_mm": "0.09",
    "upw_v_mode": "最低維持流速",
    "e_terminal_c": "60",
    "e_ambient_c": "35",
    "e_loaded_conductors": "3",
    "e_length_m": "30",
    "e_drop_limit_pct": "3",
    "e_reactance_ohm_km": "0.08",
    "e_copper_rho20": "0.017241",
    "e_sort": "最少並聯組數",
    "e_basis": "TW 專案表初估（非完整合規）",
    "np_hvac_link": "獨立輸入",
    "e_up_largest_hp": "0",
    "e_np_largest_hp": "0",
}
TEMP_FACTORS = {
    60: [(35, 1), (40, 0.89), (45, 0.77), (50, 0.63), (55, 0.45)],
    75: [(35, 1), (40, 0.94), (45, 0.87), (50, 0.79), (55, 0.71)],
    90: [(35, 1), (40, 0.95), (45, 0.9), (50, 0.85), (55, 0.8)],
}
DERATE_TEMP = {
    "35℃ 以下 (標準)": 1,
    "36~40℃": 0.95,
    "41~45℃": 0.9,
    "46~50℃": 0.85,
    "51~55℃": 0.8,
}
DERATE_PIPES = {
    "3根以下 (標準)": 1,
    "4根": 0.9,
    "5~6根": 0.8,
    "7~9根": 0.7,
    "10~20根": 0.5,
    "21~30根": 0.45,
    "31~40根": 0.4,
    "41根以上": 0.35,
}
SYSTEMS = [
    "CHW (空調冰水)",
    "DCCW (乾盤管水)",
    "PCW (製程冷卻水)",
    "HW (熱水盤管水)",
    "GEX (一般排氣)",
    "SEX (酸性排氣)",
    "AEX (鹼性排氣)",
    "VEX (有機排氣)",
    "HEX (機台熱排)",
]
PD_DEFAULTS = {
    "length_m": "100",
    "elbows": "10",
    "tees": "4",
    "reducers": "2",
    "valves": "6",
    "equipment_drop": "12",
    "rate": "0.03",
    "unit": "mH2O",
    "mode": "Darcy 自動",
    "manual_id_mm": "0",
    "fitting_mode": "等效長 L/D",
    "sum_k": "0",
    "elbow_ld": "30",
    "tee_ld": "60",
    "reducer_ld": "15",
    "valve_ld": "40",
    "boundary": "閉式循環",
    "static_m": "0",
    "efficiency": "0.70",
}


def number(value, label="數值", low=None, high=None):
    try:
        x = float(str(value).strip())
    except (ValueError, TypeError):
        raise InputError(f"必須為有效數字", field_name=f"{label}") from None
    if not math.isfinite(x):
        raise InputError(f"不可為空白、NaN 或無限值", field_name=f"{label}")
    if low is not None and x < low:
        raise InputError(f"不可小於 {low}", field_name=f"{label}")
    if high is not None and x > high:
        raise InputError(f"不可大於 {high}", field_name=f"{label}")
    return x


parse_float = number


def integer(value, label="數量", low=0, high=1000000):
    x = number(value, label, low, high)
    if not x.is_integer():
        raise InputError(f"必須為整數", field_name=f"{label}")
    return int(x)


def flag(value, label="開關"):
    if str(value) not in ("0", "1"):
        raise InputError(f"必須為 0 或 1", field_name=f"{label}")
    return str(value) == "1"


def choice(value, allowed, label):
    if value not in allowed:
        raise InputError(f"不支援：{value}", field_name=f"{label}")
    return value


def fmt(value, dec=2):
    return "--" if value is None else f"{value:,.{dec}f}"


def to_cmh_strict(value, unit, label):
    return (
        number(value, label, 0, 1000000000.0)
        * {"CMH": 1, "CFM": CFM_TO_CMH}[choice(unit, ("CMH", "CFM"), label + "單位")]
    )


def to_lpm_strict(value, unit, label):
    return (
        number(value, label, 0, 100000000.0)
        * {"LPM": 1, "GPM": GPM_TO_LPM}[choice(unit, ("LPM", "GPM"), label + "單位")]
    )


def sat_pa(t):
    t = number(t, "乾球溫度", -100, 200)
    k = t + 273.15
    if t <= 0.01:
        ln = (
            -5674.5359 / k
            + 6.3925247
            - 0.009677843 * k
            + 6.2215701e-07 * k * k
            + 2.0747825e-09 * k**3
            - 9.484024e-13 * k**4
            + 4.1635019 * math.log(k)
        )
    else:
        ln = (
            -5800.2206 / k
            + 1.3914993
            - 0.048640239 * k
            + 4.1764768e-05 * k * k
            - 1.4452093e-08 * k**3
            + 6.5459673 * math.log(k)
        )
    return math.exp(ln)


def enthalpy(t, w):
    return CP_DA * t + w * (H_V0 + CP_V * t)


def state_tw(t, w, p):
    t = number(t, "空氣乾球", -60, 90)
    w = number(w, "含濕比", 0, 1)
    p = number(p, "大氣壓 kPa", 60, 120)
    pw = p * 1000 * w / (MW_RATIO + w)
    rh = 100 * pw / sat_pa(t)
    if rh > 100 + 1e-06:
        raise InputError(f"空氣狀態超飽和：{t:.4f}°C、{rh:.4f}%RH")
    vol = 0.287042 * (t + 273.15) * (1 + w / MW_RATIO) / p
    return {
        "t": t,
        "w": w,
        "x": w,
        "rh": min(100, rh),
        "h": enthalpy(t, w),
        "v_da": vol,
        "rho_moist": (1 + w) / vol,
    }


def state_trh(t, rh, p):
    rh = number(rh, "RH", 0, 100)
    pw = sat_pa(t) * rh / 100
    if pw >= p * 1000:
        raise InputError(f"水蒸氣分壓大於總壓，超出模型範圍")
    return state_tw(t, MW_RATIO * pw / (p * 1000 - pw), p)


def dewpoint(w, p):
    if w <= 0:
        return -100.0
    target = p * 1000 * w / (MW_RATIO + w)
    lo, hi = (-100.0, 100.0)
    for _ in range(80):
        mid = (lo + hi) / 2
        if sat_pa(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def project_hash(project):
    return hashlib.sha256(
        json.dumps(
            project, ensure_ascii=False, sort_keys=True, allow_nan=False
        ).encode()
    ).hexdigest()


def atomic_text(path, text):
    path = Path(path)
    if not path.parent.is_dir():
        raise InputError(f"儲存資料夾不存在")
    fd, tmp = tempfile.mkstemp(prefix=".facility_", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def duct_selection(cmh, velocity, ratio, shape="方管"):
    q = number(cmh, "風量", 0, 1000000000.0) / 3600
    vmax = number(velocity, "最大風速", 0.1, 60)
    ratio = number(ratio, "寬高比上限", 1, 4)
    choice(shape, ("方管", "圓管"), "風管形狀")
    if q == 0:
        return {
            "flow_cmh": 0,
            "shape": shape,
            "area_m2": 0,
            "diameter_m": 0,
            "velocity_mps": 0,
            "w_mm": 0,
            "h_mm": 0,
            "round_in": 0,
        }
    need = q / vmax
    d_in = max(2, math.ceil(math.sqrt(4 * need / math.pi) / 0.0254 / 2 - 1e-12) * 2)
    candidates = []
    lower = max(50, math.floor(math.sqrt(need / ratio) * 1000 / 50) * 50)
    upper = math.ceil(math.sqrt(need) * 1000 / 50) * 50
    for h in range(lower, upper + 51, 50):
        w = max(h, math.ceil(need * 1000000.0 / h / 50 - 1e-12) * 50)
        if w / h <= ratio + 1e-12:
            candidates.append((w * h, abs(w / h - ratio), w + h, w, h))
    if not candidates:
        raise InputError(f"找不到符合面積與寬高比的風管")
    _, _, _, w, h = min(candidates)
    if shape == "方管":
        area = w * h / 1000000.0
        diam = 2 * w * h / (w + h) / 1000
    else:
        diam = d_in * 0.0254
        area = math.pi * diam**2 / 4
    return {
        "flow_cmh": cmh,
        "shape": shape,
        "area_m2": area,
        "diameter_m": diam,
        "velocity_mps": q / area,
        "w_mm": w,
        "h_mm": h,
        "round_in": d_in,
        "ratio_actual": w / h,
        "velocity_limit_mps": vmax,
    }


def water_selection(lpm, vmax, mode="流速上限", manual_id=0):
    q = number(lpm, "水量", 0, 100000000.0) / 60000
    vmax = number(vmax, "水流速上限", 0.1, 10)
    choice(mode, ("流速上限", "原專案流量表"), "水管選型模式")
    if q == 0:
        return {
            "lpm": 0,
            "id_mm": 0,
            "runs": 0,
            "velocity_mps": 0,
            "area_m2": 0,
            "size": "無需求",
        }
    if manual_id > 0:
        d = number(manual_id, "實際內徑 mm", 1, 3000)
        runs = 1
        size = f"自訂 ID {d:g} mm"
    else:
        selected = None
        for n in range(1, 33):
            for pipe in HVAC_PIPES:
                area = math.pi * (pipe["id_mm"] / 1000) ** 2 / 4
                if q / n / area <= vmax + 1e-12 and (
                    mode != "原專案流量表" or lpm / n <= pipe["max_flow_lpm"]
                ):
                    selected = (n, pipe)
                    break
            if selected:
                break
        if selected is None:
            raise InputError(f"水管需求超過 32 組並聯範圍")
        runs, pipe = selected
        d = pipe["id_mm"]
        size = pipe["size"]
    area = math.pi * (d / 1000) ** 2 / 4
    if q / runs / area > vmax + 1e-10:
        raise InputError(f"指定實際內徑超過水流速上限")
    return {
        "lpm": lpm,
        "id_mm": d,
        "runs": runs,
        "velocity_mps": q / runs / area,
        "area_m2": area,
        "size": size,
    }


def darcy_factor(re, relative_roughness):
    if re <= 0:
        return 0.0
    if re < 2300:
        return 64 / re

    def turbulent(r):
        lo, hi = (0.002, 0.2)
        for _ in range(65):
            f = (lo + hi) / 2
            residual = 1 / math.sqrt(f) + 2 * math.log10(
                relative_roughness / 3.7 + 2.51 / (r * math.sqrt(f))
            )
            if residual > 0:
                lo = f
            else:
                hi = f
        return (lo + hi) / 2

    if re >= 4000:
        return turbulent(re)
    f2300 = 64 / 2300
    f4000 = turbulent(4000)
    return f2300 + (f4000 - f2300) * (re - 2300) / 1700


def pressure_result(
    config, q_m3s, diameter, area, runs, rho, mu, rough_mm, is_water=True
):
    c = config
    length = number(c["length_m"], "直管長度", 0, 100000)
    counts = [
        integer(c[k], k, 0, 100000) for k in ("elbows", "tees", "reducers", "valves")
    ]
    coeff = [
        number(c[k], k, 0, 10000)
        for k in ("elbow_ld", "tee_ld", "reducer_ld", "valve_ld")
    ]
    eq = number(c["equipment_drop"], "設備壓降", 0, 100000000.0)
    rate = number(c["rate"], "手動單位阻力率", 0, 100000000.0)
    unit = choice(c["unit"], ("Pa", "kPa", "mmAq", "mH2O"), "壓損單位")
    scale = {"Pa": 1, "kPa": 1000, "mmAq": G, "mH2O": 1000 * G}[unit]
    mode = choice(c["mode"], ("Darcy 自動", "手動阻力率"), "壓損模式")
    fitting = choice(c["fitting_mode"], ("等效長 L/D", "直接 K 值"), "管件模式")
    sum_k = number(c["sum_k"], "K 值加總", 0, 1000000.0)
    static = number(c["static_m"], "開式靜揚程", 0, 10000)
    boundary = choice(c["boundary"], ("閉式循環", "開式系統"), "系統邊界")
    if boundary == "閉式循環" and static > 0:
        raise InputError(f"閉式循環不可直接加樓高；靜揚程請設 0")
    eff = number(c["efficiency"], "泵／風機效率", 0.05, 1)
    if not is_water and static > 0:
        raise InputError(f"風管不使用水泵靜揚程，請設 0")
    v = q_m3s / runs / area if q_m3s > 0 else 0
    re = rho * v * diameter / mu if q_m3s > 0 else 0
    f = darcy_factor(re, rough_mm / 1000 / diameter) if q_m3s > 0 else 0
    leq = (
        diameter * sum((x * y for x, y in zip(counts, coeff)))
        if fitting == "等效長 L/D"
        else 0
    )
    velocity_pressure = rho * v * v / 2
    if q_m3s == 0:
        friction = local = equipment = static_pa = 0
    else:
        friction = (
            f * length / diameter * velocity_pressure
            if mode == "Darcy 自動"
            else length * rate * scale
        )
        local = (
            (
                f * leq / diameter * velocity_pressure
                if mode == "Darcy 自動"
                else leq * rate * scale
            )
            if fitting == "等效長 L/D"
            else sum_k * velocity_pressure
        )
        equipment = eq * scale
        static_pa = rho * G * static if is_water else 0
    loss = friction + local + equipment
    total = loss + static_pa
    return {
        "flow_m3s": q_m3s,
        "id_m": diameter,
        "area_m2": area,
        "runs": runs,
        "velocity_mps": v,
        "rho": rho,
        "mu": mu,
        "roughness_mm": rough_mm,
        "re": re,
        "f": f,
        "length_m": length,
        "equivalent_length_m": leq,
        "sum_k": sum_k,
        "friction_pa": friction,
        "local_pa": local,
        "equipment_pa": equipment,
        "static_pa": static_pa,
        "loss_pa": loss,
        "total_pa": total,
        "head_m": total / (rho * G),
        "mmAq": total / G,
        "shaft_kw": q_m3s * total / (1000 * eff),
        "efficiency": eff,
        "mode": mode,
        "fitting_mode": fitting,
        "rate_pa_m": rate * scale,
        "transition": 2300 <= re < 4000,
    }


def group_factor(count):
    for upper, f in (
        (3, 1),
        (4, 0.9),
        (6, 0.8),
        (9, 0.7),
        (20, 0.5),
        (30, 0.45),
        (40, 0.4),
        (100000, 0.35),
    ):
        if count <= upper:
            return f


def electrical_result(i, warnings):
    n = lambda k, lo=None, hi=None: number(i[k], k, lo, hi)
    voltage = VOLTAGE_MAP[choice(i["e_volt"], tuple(VOLTAGE_MAP), "電壓")]
    pf = n("e_pf", 0.1, 1)
    eff = n("e_eff", 0.1, 1)
    wire = choice(
        i["e_wire"], ("XLPE 絕緣電纜 (90°C)", "PVC 一般電纜 (60°C)"), "電纜絕緣"
    )
    ins = 90 if wire.startswith("XLPE") else 60
    terminal = integer(i["e_terminal_c"], "端子溫度", 60, 90)
    if terminal not in (60, 75, 90):
        raise InputError(f"端子溫度只支援 60／75／90°C")
    legacytemp = {
        "35℃ 以下 (標準)": 35,
        "36~40℃": 40,
        "41~45℃": 45,
        "46~50℃": 50,
        "51~55℃": 55,
    }
    ambient = max(
        n("e_ambient_c", -20, 55),
        legacytemp[choice(i["e_temp"], tuple(legacytemp), "環溫區間")],
    )
    dtfactor = next((f for upper, f in TEMP_FACTORS[ins] if ambient <= upper))
    count = integer(i["e_loaded_conductors"], "同管載流導線數", 1, 10000)
    dp = min(
        group_factor(count),
        DERATE_PIPES[choice(i["e_pipe"], tuple(DERATE_PIPES), "管槽降載")],
    )
    length = n("e_length_m", 0, 10000)
    dropmax = n("e_drop_limit_pct", 0.1, 20)
    rho20 = n("e_copper_rho20", 0.01, 0.03)
    reactance = n("e_reactance_ohm_km", 0, 1)
    sort = choice(i["e_sort"], ("最少並聯組數", "最少總銅截面"), "電纜排序")
    choice(i["e_basis"], ("TW 專案表初估（非完整合規）",), "選型依據")
    choice(i["np_hvac_link"], ("獨立輸入",), "NP 負載來源")
    hpkw = 0.745699871582 / eff
    uphp = n("e_up_hp", 0, 10000000.0)
    panels = {
        "UP": {
            "kw": n("e_up_kw", 0, 10000000.0)
            + n("e_up_oven", 0, 10000000.0)
            + uphp * hpkw,
            "hp": uphp,
            "kind": i["e_up_type"],
        }
    }
    npkw = n("e_np_pump", 0, 10000000.0)
    nphp = 0.0
    for name in ("fan", "heat", "humid", "exh"):
        value = n("e_np_" + name, 0, 10000000.0)
        unit = choice(i["u_e_np_" + name], ("kW", "HP"), "NP " + name + " 單位")
        npkw += value if unit == "kW" else value * hpkw
        if unit == "HP":
            nphp += value
    panels["NP"] = {"kw": npkw, "hp": nphp, "kind": i["e_np_type"]}
    for key, pan in panels.items():
        kind = choice(
            pan["kind"], ("一般負載", "連續負載", "馬達負載"), key + " 負載類型"
        )
        kw = pan["kw"]
        current = kw * 1000 / (math.sqrt(3) * voltage * pf)
        largest = n("e_" + key.lower() + "_largest_hp", 0, 10000000.0)
        if largest > pan["hp"] + 1e-08:
            raise InputError(f"{key} 最大馬達 HP 不得大於明列的 HP 合計")
        hasmotor = pan["hp"] > 0 or kind == "馬達負載"
        if kind == "連續負載":
            design = current * 1.25
        elif hasmotor and largest > 0:
            design = current + 0.25 * largest * hpkw * 1000 / (
                math.sqrt(3) * voltage * pf
            )
        elif hasmotor:
            design = current * 1.25
        else:
            design = current
        candidates = []
        for runs in range(1, 9):
            for row in WIRE_DB:
                size = row["size_mm2"]
                if size < 3.5 or (runs > 1 and size < 50):
                    continue
                base = row["XLPE_A" if ins == 90 else "PVC_A"]
                corrected = base * dtfactor * dp
                terminal_limit = row["PVC_A"] if terminal < 90 else base
                iz_per = min(corrected, terminal_limit)
                iz = runs * iz_per
                cap = min(iz, {3.5: 20, 5.5: 30}.get(size, math.inf))
                at = next(
                    (
                        rating
                        for rating in NFB_SIZES
                        if rating >= design - 1e-09 and rating <= cap + 1e-09
                    ),
                    None,
                )
                resistance = (
                    rho20 * (1 + 0.00393 * (min(ins, terminal) - 20)) * 1000 / size
                )
                dv = (
                    math.sqrt(3)
                    * current
                    * (resistance * pf + reactance * math.sqrt(1 - pf * pf))
                    * length
                    / 1000
                    / runs
                )
                drop = 100 * dv / voltage
                if at is not None and drop <= dropmax + 1e-10:
                    candidates.append(
                        {
                            "runs": runs,
                            "size_mm2": size,
                            "iz_a": iz,
                            "base_a": base,
                            "dt": dtfactor,
                            "dp": dp,
                            "terminal_limit_per_run_a": terminal_limit,
                            "iz_per_run_a": iz_per,
                            "protection_cap_a": cap,
                            "nfb_candidate_a": at,
                            "voltage_drop_v": dv,
                            "voltage_drop_pct": drop,
                            "r_ohm_km": resistance,
                            "x_ohm_km": reactance,
                            "copper_total_mm2": runs * size,
                            "operating_temp_assumption_c": min(ins, terminal),
                        }
                    )
        sortkey = (
            (lambda x: (x["runs"], x["size_mm2"]))
            if sort == "最少並聯組數"
            else lambda x: (x["copper_total_mm2"], x["runs"], x["size_mm2"])
        )
        candidates.sort(key=sortkey)
        if kw and (not candidates):
            raise InputError(
                f"{key} 沒有符合載流、保護上限及壓降的候選電纜（最多 8 組並聯）"
            )
        selected = (
            candidates[0]
            if kw
            else {
                "runs": 0,
                "size_mm2": 0,
                "iz_a": 0,
                "nfb_candidate_a": 0,
                "voltage_drop_v": 0,
                "voltage_drop_pct": 0,
                "copper_total_mm2": 0,
            }
        )
        pan.update(
            current_a=current,
            design_current_a=design,
            voltage=voltage,
            pf=pf,
            eff=eff,
            ambient_c=ambient,
            dt=dtfactor,
            dp=dp,
            largest_hp=largest,
            has_motor=hasmotor,
            nfb_finalized=False,
            selected=selected,
            candidate_count=len(candidates) if kw else 0,
        )
        if hasmotor:
            warnings.append(
                key
                + " 含馬達：目前用 kW／HP 估算電流，最大馬達未填時保守用全負荷 125%；斷路器僅候選，須另核啟動、過載與短路保護。"
            )
        if selected["runs"] > 1:
            warnings.append(
                key
                + " 並聯需核同長同材同截面、均流、各相配置；同管載流根數依實際路由設定。"
            )
    warnings.extend(
        [
            "電氣採三相平衡及同一等效 PF。kW 為電氣輸入，HP 為軸輸出並除效率；不同設備不得重複填入。",
            "原電纜表缺少安裝方式／來源，完整保留但僅作專案初估；2.0 欄位量綱可疑，保留原資料但不參與選型。",
            "缺少 75°C 端子表時保守用原 60°C 表限制。環溫及同管設定取兩輸入中較不利值。",
            "一般保護候選要求設計電流 ≤ AT ≤ 有效載流／小線保護上限；未自動套用上調一級例外。",
            "尚需確認短路電流、Icu/Ics、選擇協調、接地、中性線與諧波；本報告不構成配電施工核定。",
        ]
    )
    return panels


def gas_result(i, warnings):
    n = lambda k, lo=None, hi=None: number(i[k], k, lo, hi)
    p = n("atm_kpa", 60, 120)
    st = n("gas_std_t", -60, 60)
    sp = n("gas_std_kpa", 60, 120)
    temp = n("gas_temp", -60, 150)
    z = n("gas_z_ratio", 0.1, 3)
    barg = n("gas_barg", 0, 300)
    minbar = n("gas_min_barg", 0, 300)
    if minbar > barg and any(
        (
            i.get(f"gas{j}_pressure_mode", "共用最低壓力") == "共用最低壓力"
            and float(i[f"gas{j}_q"]) > 0
            for j in (1, 2, 3)
        )
    ):
        raise InputError("遠端最低表壓不得高於供氣表壓", field_name="gas_min_barg")
    pv = n("pv_torr", 1e-06, 900)
    pvmin = n("pv_min_torr", 1, 760)
    if pv * 133.322368421 > p * 1000:
        raise InputError(f"PV 絕對壓不得高於所在地大氣壓")
    if n("pv_q", 0, 100000000.0) > 0 and pv < pvmin:
        raise InputError(
            f"PV 低於此連續介質流速初估模型的壓力下限；需真空導通率與幫浦曲線"
        )
    result = {}
    for index in (1, 2, 3, 4):
        typ = (
            choice(
                i[f"gas{index}_type"], tuple(GAS_DESIGN_VELOCITY_MPS), f"氣體 {index}"
            )
            if index < 4
            else "PV"
        )
        if index < 4 and typ == "PV":
            raise InputError(f"PV 請填專用真空欄；特氣欄只接受正壓氣體")
        qstd = n(f"gas{index}_q" if index < 4 else "pv_q", 0, 100000000.0)
        localbar = (
            n(f"gas{index}_barg", 0, 300)
            if index < 4 and i.get(f"gas{index}_pressure_mode") == "本路管內壓力"
            else minbar
        )
        if index < 4 and qstd > 0 and (localbar > barg):
            raise InputError(f"本路管內表壓高於供氣表壓", field_name=f"gas{index}_barg")
        pa = (p + localbar * 100) * 1000 if typ != "PV" else pv * 133.322368421
        qactual = qstd * sp * 1000 / pa * (temp + 273.15) / (st + 273.15) * z
        vmax = (
            n("pv_velocity", 0.1, 100)
            if index == 4 and "pv_velocity" in i
            else (
                n(f"gas{index}_velocity", 0.1, 100)
                if index < 4 and i.get(f"gas{index}_v_mode") == "自訂流速"
                else GAS_DESIGN_VELOCITY_MPS[typ]
            )
        )
        needed = math.sqrt(4 * (qactual / 60000) / math.pi / vmax) * 1000 if qstd else 0
        pipes = sorted(PIPE_DB, key=lambda r: r["id"])
        row = next((r for r in pipes if r["id"] >= needed), None) if qstd else None
        if qstd and row is None:
            raise InputError(f"{typ} 超過原始管材表範圍；不可把最大管徑當作符合")
        result[str(index)] = {
            "type": typ,
            "standard_lpm": qstd,
            "actual_lpm": qactual,
            "pressure_abs_pa": pa,
            "minimum_id_mm": needed,
            "selected_id_mm": row["id"] if row else 0,
            "size": row["name"] if row else "無需求",
            "velocity_mps": (
                qactual / 60000 / (math.pi * (row["id"] / 1000) ** 2 / 4) if row else 0
            ),
            "velocity_limit_mps": vmax,
        }
    warnings.extend(
        [
            "特氣／PV 採指定標準溫壓與 Z 比值換算實際流量；只做流速截面初估，未算可壓縮壓降及遠端供壓。",
            "O2／H2 等原流速表不是材料相容、點火風險或氣體安全核定；管件、潔淨度、洩漏與連鎖須另設計。",
            "PV 使用絕對壓，未計真空導通率、泵曲線與抽氣時間；材質必須另外核對外壓屈曲。",
        ]
    )
    return result


SOURCES = [
    (
        "S1",
        "濕空氣公式與乾空氣質量基準（ASHRAE 2017 對照）",
        "https://psychrometrics.github.io/psychrolib/_modules/psychrolib.html",
    ),
    (
        "S2",
        "盤管 ADP/BF 模型及限制",
        "https://bigladdersoftware.com/epx/docs/23-1/engineering-reference/coils.html",
    ),
    (
        "S3",
        "用戶用電設備裝置規則；實案仍須確認適用版本及表格",
        "https://law.moea.gov.tw/LawContent.aspx?id=FL011045",
    ),
    (
        "S4",
        "周圍溫度修正表 25-7",
        "https://law.moea.gov.tw/Download.ashx?FileID=190925&id=FL011045&type=LAW",
    ),
    (
        "S5",
        "同管載流導線數修正表 25-6",
        "https://law.moea.gov.tw/Download.ashx?FileID=190929&id=FL011045&type=LAW",
    ),
    (
        "S6",
        "ISO 14644-1 潔淨分類；不以固定 ACH 取代粒子測試",
        "https://www.iso.org/standard/53394.html",
    ),
    (
        "S7",
        "氧氣配管要求與壓力／流速適用條件",
        "https://www.eiga.eu/uploads/documents/DOC013.pdf",
    ),
    (
        "S8",
        "真空壓力單位與範圍",
        "https://www.leybold.com/en-uk/knowledge/vacuum-fundamentals/fundamental-physics-of-vacuum/units-and-ranges-of-pressure",
    ),
    (
        "S9",
        "美制冷凍噸單位",
        "https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8",
    ),
    (
        "S10",
        "日本冷凍噸定義",
        "https://www.jsrae.or.jp/books/jidoukiki/Jidou-SAMPLE.pdf",
    ),
    (
        "S11",
        "Darcy-Weisbach 管路方法",
        "https://www.energy.gov/sites/default/files/2013/12/f5/NSD_Methodology_Report.pdf",
    ),
]
