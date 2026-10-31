from .errors import InputError
from pathlib import Path
import copy
import json
import math
from .json_io import read_json_file
from .data import VOLTAGE_MAP, FFU_SIZES
from .quality import assess_main
from . import airflow_guard
from .schema import (
    V54_INPUT_KEYS,
    V55_INPUT_KEYS,
    V556_INPUT_KEYS,
    V560_INPUT_KEYS,
    PD_DEFAULTS,
    DEFAULTS,
    FIELDS,
    LEGACY_INPUT_KEYS,
    LEGACY_PD_KEYS,
    PD_KEYS,
    QUALITY_PRESETS,
    SCHEMA_VERSION,
    UTILITY_ONLY_KEYS,
    V52_INPUT_KEYS,
    V53_INPUT_KEYS,
    VERSION,
)
from .utils import (
    EXTRA_DEFAULTS,
    G,
    JRT_KW,
    MW_RATIO,
    US_RT_KW,
    choice,
    dewpoint,
    duct_selection,
    electrical_result,
    electrical_power_kw,
    gas_result,
    integer,
    number,
    project_hash,
    sat_pa,
    state_trh,
    state_tw,
    to_cmh_strict,
    to_lpm_strict,
    water_selection,
)


def migrate_project(p):
    if isinstance(p, dict) and p.get("schema_version") == 5:
        if (
            set(p) != {"schema_version", "inputs", "pressure_drop"}
            or not isinstance(p.get("inputs"), dict)
            or set(p["inputs"]) != LEGACY_INPUT_KEYS
        ):
            raise InputError(f"V5.0 專案欄位缺漏或含未知欄位")
        if (
            not isinstance(p["pressure_drop"], dict)
            or set(p["pressure_drop"]) != set(PD_KEYS)
            or any(
                (
                    not isinstance(c, dict) or set(c) != LEGACY_PD_KEYS
                    for c in p["pressure_drop"].values()
                )
            )
        ):
            raise InputError(f"V5.0 壓損欄位不完整")
        p = copy.deepcopy(p)
        p["schema_version"] = 6
        p["inputs"].update(
            latent_mode="已知潛熱 kW",
            process_moisture_kg_h="0",
            pv_pressure_unit="Torr(abs)",
            upw_quality_mode="自訂規格",
        )
        for c in p["pressure_drop"].values():
            c.update(
                estimate_mode="詳細計算",
                allowance_pct="30",
                equipment_known="已知設備壓差",
            )
    if isinstance(p, dict) and p.get("schema_version") == 6:
        if (
            set(p) != {"schema_version", "inputs", "pressure_drop"}
            or not isinstance(p.get("inputs"), dict)
            or set(p["inputs"]) != V52_INPUT_KEYS
        ):
            raise InputError(f"V5.1/5.2 欄位缺漏或不同來源格式，不能以相同版本號誤載")
        p = copy.deepcopy(p)
        p["schema_version"] = 7
        p["inputs"].update({k: DEFAULTS[k] for k in V53_INPUT_KEYS - V52_INPUT_KEYS})
    if isinstance(p, dict) and p.get("schema_version") == 7:
        if set(p.get("inputs", {})) != V53_INPUT_KEYS:
            raise InputError(f"V5.3 專案欄位不完整，不能自動移轉")
        p = copy.deepcopy(p)
        p["schema_version"] = 8
        p["inputs"]["sys_type"] = p["inputs"]["sys_type"].replace("全期外氣", "全外氣")
        p["inputs"].update({k: DEFAULTS[k] for k in V54_INPUT_KEYS - V53_INPUT_KEYS})
    if isinstance(p, dict) and p.get("schema_version") == 8:
        if set(p.get("inputs", {})) != V54_INPUT_KEYS:
            raise InputError("V5.4 欄位不完整，無法移轉")
        p = copy.deepcopy(p)
        p["schema_version"] = 9
        p["inputs"].update({k: DEFAULTS[k] for k in V55_INPUT_KEYS - V54_INPUT_KEYS})
        p["inputs"]["winter_model"] = "外氣處理基準（舊版）"
        p["provenance"] = {
            k: {"source": "舊專案輸入", "note": "V5.4 或更早版本移轉；未推定原廠來源"}
            for k in V55_INPUT_KEYS
        }
    if isinstance(p, dict) and p.get("schema_version") == 9:
        if set(p.get("inputs", {})) != V55_INPUT_KEYS:
            raise InputError("V5.5 專案欄位不完整，不能自動移轉")
        from .project_store import provenance_record
        p = copy.deepcopy(p)
        p["schema_version"] = 10
        new_keys = V556_INPUT_KEYS - V55_INPUT_KEYS
        p["inputs"].update({k: DEFAULTS[k] for k in new_keys})
        for loop in ("mchw", "chw", "dccw", "pcw", "hw"):
            for prop in ("rho", "cp", "mu"):
                p["inputs"][loop + "_" + prop] = p["inputs"]["water_" + prop]
        if not isinstance(p.get("provenance"), dict) or set(p["provenance"]) != V55_INPUT_KEYS:
            raise InputError("V5.5 參數來源不完整，不能自動移轉")
        for k in new_keys:
            p["provenance"][k] = provenance_record(
                "舊專案輸入", "V5.5.6 移轉：保留原共用物性與計算範圍", p["inputs"][k]
            )
    if isinstance(p, dict) and p.get("schema_version") == 10:
        if set(p.get("inputs", {})) != V556_INPUT_KEYS or not isinstance(p.get("provenance"), dict) or set(p["provenance"]) != V556_INPUT_KEYS:
            raise InputError("V5.5.6–5.5.10欄位或來源不完整，不能自動移轉")
        p = copy.deepcopy(p)
        p["schema_version"] = 11
        for k in V560_INPUT_KEYS - V556_INPUT_KEYS:
            p["inputs"][k] = DEFAULTS[k]
            # An absent legacy field has no observed source timestamp. Keep
            # migration deterministic so repeated calculations retain identity.
            p["provenance"][k] = {
                "source": "舊專案輸入",
                "note": "V5.6移轉：新增自訂氣體名稱草稿，原氣體種類與工程條件保留",
            }
    if isinstance(p, dict) and p.get("schema_version") == 11:
        if (set(p.get("inputs", {})) != V560_INPUT_KEYS
                or not isinstance(p.get("provenance"), dict)
                or set(p["provenance"]) != V560_INPUT_KEYS):
            raise InputError("V5.6.0欄位或來源不完整，不能自動移轉")
        p = copy.deepcopy(p)
        p["schema_version"] = 12
        legacy_v12 = {
            "ffu_topology": "獨立FFU循環（MAU直接入室）",
            "ffu_airflow_basis": "FFU總送風（已含OA）",
        }
        for k in set(FIELDS) - V560_INPUT_KEYS:
            p["inputs"][k] = legacy_v12.get(k, DEFAULTS[k])
            p["provenance"][k] = {
                "source": "舊專案輸入",
                "note": "工程修訂：保留獨立FFU循環、MAU直接入室及門縫孔口法；新增可選假設，未推定型錄值",
            }
    if (isinstance(p, dict) and p.get("schema_version") == 12
            and p.get("inputs", {}).get("light_u_mode") == "室指數 K 自動（DIALux 基準）"):
        p = copy.deepcopy(p)
        p["inputs"]["light_u_mode"] = "型錄 U＋室指數 K 檢核"
        p["provenance"]["light_u"]["note"] = (
            "移除無光度依據的U(K)推估；採用原手填U，請依燈具型錄重新確認並重算。"
        )

    return p


def water_properties(inputs, loop):
    """Resolve fluid properties for one circuit without touching another circuit."""
    loop = loop.lower()
    independent = inputs[loop + "_fluid_mode"] == "本迴路獨立物性"
    prefix = loop + "_" if independent else "water_"
    return dict(
        rho=float(inputs[prefix + "rho"]),
        cp=float(inputs[prefix + "cp"]),
        mu=float(inputs[prefix + "mu"]),
        source=inputs[loop + "_fluid_mode"],
        fluid=inputs[loop + "_fluid_name"] if independent else "共用流體參考",
    )


def _inward(x, up):
    """Round x to 6 significant digits toward the inside of the allowed range, so the stated bound is accepted."""
    scale = 10 ** (5 - math.floor(math.log10(abs(x))))
    return (math.ceil(x * scale - 1e-9) if up else math.floor(x * scale + 1e-9)) / scale


def pv_to_torr(value, unit):
    factor = {"Torr(abs)": 1.0, "kPa(abs)": 760 / 101.325, "mbar(abs)": 760 / 1013.25}
    choice(unit, tuple(factor), "pv_pressure_unit")
    torr = number(value, "pv_torr") * factor[unit]
    if torr < 1 - 1e-09 or torr > 760 + 1e-09:
        raise InputError(
            f"PV 絕對壓力須介於 {_inward(1 / factor[unit], True):.6g}～{_inward(760 / factor[unit], False):.6g} {unit}"
            f"（本模型限 1～760 Torr 絕壓，約 0.133322～101.325 kPa）；請確認單位",
            field_name=f"pv_torr",
        )
    return min(760.0, max(1.0, torr))


def latent_breakdown(i):
    people = (
        (float(i["ppl_A"]) + float(i["ppl_B"])) * float(i["people_latent_w"]) / 1000
    )
    mode = i["latent_mode"]
    process = (
        float(i["process_latent_kw"])
        if mode == "已知潛熱 kW"
        else (
            float(i["process_moisture_kg_h"]) * 2501 / 3600
            if mode == "已知產濕量 kg/h"
            else 0.0
        )
    )
    return {
        "people_kw": people,
        "process_kw": process,
        "people_kg_h": people * 3600 / 2501,
        "process_kg_h": process * 3600 / 2501,
        "total_kw": people + process,
        "mode": mode,
    }


from .utils import pressure_result as _pressure_detailed


def pressure_result(
    config, q_m3s, diameter, area, runs, rho, mu, rough_mm, is_water=True
):
    from .field_state import effective_pressure

    config = effective_pressure(config, is_water)
    mode = choice(config["estimate_mode"], ("簡易估算", "詳細計算"), "壓損計算方式")
    allowance = number(config["allowance_pct"], "管件等效長度餘裕", 0, 200) / 100
    known = choice(
        config["equipment_known"],
        ("尚無資料（不含設備）", "已知設備壓差"),
        "設備壓差資料",
    )
    c = copy.deepcopy(config)
    if known == "尚無資料（不含設備）":
        c["equipment_drop"] = "0"
    if mode == "簡易估算":
        c.update(mode="Darcy 自動", fitting_mode="直接 K 值", sum_k="0")
        if known == "尚無資料（不含設備）":
            c["equipment_drop"] = "0"
    r = _pressure_detailed(c, q_m3s, diameter, area, runs, rho, mu, rough_mm, is_water)
    if mode == "簡易估算":
        r["local_pa"] = r["friction_pa"] * allowance
        r["equivalent_length_m"] = float(c["length_m"]) * allowance
        r["loss_pa"] = r["friction_pa"] + r["local_pa"] + r["equipment_pa"]
        r["total_pa"] = r["loss_pa"] + r["static_pa"]
        r["head_m"] = r["total_pa"] / (rho * G)
        r["mmAq"] = r["total_pa"] / G
        r["shaft_kw"] = q_m3s * r["total_pa"] / (1000 * r["efficiency"])
    r.update(
        estimate_mode=mode,
        allowance_pct=allowance * 100,
        equipment_included=known == "已知設備壓差",
        static_note=(
            "風管不使用水側靜揚程；保留的靜揚程草稿不參與計算。"
            if not is_water else
            "閉式循環不把樓高加進循環泵差壓；系統靜壓另核。"
            if config["boundary"] == "閉式循環" else
            "開式系統靜揚程採有效高差；請核對取水與出水邊界。"
        ),
    )
    return r


def validate_project(p, exclude=()):
    from .field_state import main_inactive

    p = migrate_project(p)
    if (
        not isinstance(p, dict)
        or set(p) != {"schema_version", "inputs", "pressure_drop", "provenance"}
        or p["schema_version"] != SCHEMA_VERSION
    ):
        raise InputError(f"專案格式需要 V5.6；支援完整 V5.0～5.5 專案自動移轉")
    from .optional_inputs import check_input_keys, validate_optional_inputs

    check_input_keys(p["inputs"], "專案輸入欄位缺漏或含未知欄位")
    if not isinstance(p["pressure_drop"], dict) or set(p["pressure_drop"]) != set(
        PD_KEYS
    ):
        raise InputError(f"壓損系統資料缺漏")
    from .project_store import validate_provenance

    validate_provenance(p["provenance"], FIELDS)
    inactive = main_inactive(p["inputs"])
    for k, f in FIELDS.items():
        if k in exclude:
            continue
        v = p["inputs"][k]
        if not isinstance(v, str) or len(v) > 1000:
            raise InputError(f"專案值必須為文字", field_name=f"{k}")
        if k in inactive:
            continue
        if f["options"]:
            choice(v, f["options"], k)
        elif f["text"]:
            if not v.strip() or len(v) > 500:
                raise InputError(f"文字不可空白且不得超過 500 字", field_name=f"{k}")
        else:
            number(v, k, f["low"], f["high"])
    from .field_state import optional_inactive

    validate_optional_inputs(
        p["inputs"], inactive, optional_inactive(p["inputs"], inactive), exclude
    )
    if "pv_torr" not in exclude:
        pv_to_torr(p["inputs"]["pv_torr"], p["inputs"]["pv_pressure_unit"])
    for k, c in p["pressure_drop"].items():
        if not isinstance(c, dict) or set(c) != set(PD_DEFAULTS):
            raise InputError(f"{k} 壓損欄位缺漏")
        try:
            if any(not isinstance(v, str) or len(v) > 1000 for v in c.values()):
                raise InputError("壓損欄位必須是有長度限制的文字")
            number(c["manual_id_mm"], "實際內徑", 0, 3000)
            pressure_result(c, 0, 0, 0, 0, 1000, 0.001, 0.045, k in PD_KEYS[:5])
        except InputError as e:
            raise InputError(f"{e}", field_name=f"PD:{k}") from None
    return p


def read_project(path):
    if Path(path).stat().st_size > 15000000:
        raise InputError("專案檔案超過 15 MB")

    p = read_json_file(path)
    if not isinstance(p, dict):
        raise InputError("專案 JSON 必須為物件")
    if p.get("kind") == "facility_workspace":
        from .workspace_store import validate_workspace
        p = validate_workspace(p)["main"]
    return validate_project(p)


def wetbulb(t, rh, p):
    target = state_trh(t, rh, p)["w"]
    lo = -90.0
    hi = t
    for _ in range(100):
        b = (lo + hi) / 2
        sw = (
            state_trh(b, 100, p)["w"]
            if b >= -60
            else MW_RATIO * sat_pa(b) / (p * 1000 - sat_pa(b))
        )
        if b >= 0:
            w = ((2501 - 2.326 * b) * sw - 1.006 * (t - b)) / (
                2501 + 1.86 * t - 4.186 * b
            )
        else:
            w = ((2830 - 0.24 * b) * sw - 1.006 * (t - b)) / (2830 + 1.86 * t - 2.1 * b)
        if w > target:
            hi = b
        else:
            lo = b
    return (lo + hi) / 2


def lighting(i):
    n = lambda k: number(i[k], k, FIELDS[k]["low"], FIELDS[k]["high"])
    area = sum((n("en_L_" + z) * n("en_W_" + z) for z in "AB"))
    u_mode = choice(
        i.get("light_u_mode", "手動固定 U"),
        ("手動固定 U", "型錄 U＋室指數 K 檢核"),
        "light_u_mode",
    )
    zone_k = {}
    if u_mode == "型錄 U＋室指數 K 檢核":
        work_h = n("light_work_h")
        if area > 0:
            k_weighted = 0.0
            for z in "AB":
                l_z, w_z, h_z = n("en_L_" + z), n("en_W_" + z), n("en_H_" + z)
                a_z = l_z * w_z
                if a_z > 0:
                    hm = h_z - work_h
                    if hm <= 0.1:
                        raise InputError(
                            f"{z} 區淨高必須高於照明工作面高度至少 0.1 m",
                            field_name="light_work_h",
                        )
                    k_z = a_z / (hm * (l_z + w_z))
                    zone_k[z] = k_z
                    k_weighted += a_z * k_z
            room_index = k_weighted / area
            u_val = n("light_u")
        else:
            room_index = 0.0
            u_val = n("light_u")
    else:
        room_index = None
        u_val = n("light_u")
    qty = (
        math.ceil(
            n("light_lux") * area / (n("light_lm") * u_val * n("light_m"))
            - 1e-12
        )
        if area
        else 0
    )
    return {
        "area_m2": area,
        "qty": qty,
        "kw": qty * n("light_w") / 1000,
        "lighting_w_m2": qty * n("light_w") / area if area else 0,
        "u": u_val,
        "u_mode": u_mode,
        "room_index_k": room_index,
        **({"zone_k": zone_k} if zone_k else {}),
    }


def std_lpm(value, unit):
    return (
        number(value, "標準流量", 0, 100000000.0)
        * {"SLPM": 1, "SCFM": 28.316846592, "CMH": 1000 / 60}[
            choice(unit, ("SLPM", "SCFM", "CMH"), "氣體流量單位")
        ]
    )


def blend(a, b, f, p):
    w = a["w"] * f + b["w"] * (1 - f)
    h = a["h"] * f + b["h"] * (1 - f)
    return state_tw((h - 2501 * w) / (1.006 + 1.86 * w), w, p)


def coil_record(name, a, b, m, cp):
    q = m * (a["h"] - b["h"])
    cond = m * (a["w"] - b["w"])
    if q < -1e-06 or cond < -1e-09:
        raise InputError(f"{name} 不可產生未配置的加熱或加濕")
    liquid = max(0, cond) * 4.1868 * b["t"]
    water = q - liquid
    if water < -1e-06:
        raise InputError(f"{name} 水側負荷不合理")
    return {
        "name": name,
        "inlet": a,
        "outlet": b,
        "air_kw": max(0, q),
        "water_kw": max(0, water),
        "condensate_kg_s": max(0, cond),
        "liquid_kw": liquid,
    }


def c1_blend(enter, adp, beta, p, *, season, target_t, field_name):
    """Retain the physical rejection and identify the C1 control that caused it."""
    try:
        return blend(enter, adp, beta, p)
    except InputError as error:
        if error.code != "supersaturated_air":
            raise
        label = {"summer": "夏季", "winter": "冬季"}[season]
        raise InputError(
            f"{error}；{label} C1；入口 {enter['t']:.4f}°C / {enter['rh']:.4f}%RH"
            f"；ADP {adp['t']:.4f}°C；出口乾球需求 {target_t:.4f}°C"
            "；請核對 C1 出口需求、入口與供水＋ADP 裕度。",
            field_name=field_name,
            code=error.code,
        ) from error


def solve_c2_bypass(
    s1,
    ts,
    wc,
    a2,
    p,
    *,
    allow_reheat="1",
    bf_min=0.0,
    field_name="chw2_in",
    raise_on_infeasible=True,
):
    """Cooling-coil outlet on the bypass line from s1 to a saturated ADP, ending at humidity wc.

    For ADP temperature A the outlet humidity fixes BF(A) = (wc - w_A) / (w_1 - w_A); the
    outlet is the BF mix of s1 and ADP(A), with dry bulb t(A). BF(A) falls strictly as A
    rises; t(A) is not monotonic. An ADP is admissible when a2 <= A <= tdp(wc) (chilled
    water), BF(A) >= bf_min (coil depth) and t(A) >= tdp (a bypass line crossing the
    saturation curve gives no realisable outlet there).
      * direct: some admissible A gives t(A) = ts; the one with the largest BF is used;
      * reheat: otherwise, the warmest admissible outlet below ts, then reheat; when reheat is
        not allowed this raises, or (raise_on_infeasible=False) returns that coil point with
        path "reheat_required" so the reheat stage, not the coil, reports the shortfall;
      * no admissible path: otherwise, including BF(a2) < bf_min or tdp < a2; reheat cannot
        help, and the outlet is never forced to saturation (BF = 0) past a stated floor.
    Over-drying followed by humidification is not modelled. Every feasible point satisfies
    outlet = BF x s1 + (1 - BF) x ADP. bf_min <= 0 means no coil performance basis: BF >= 0
    is used and the result is pending equipment data. With raise_on_infeasible=False an
    infeasible result has feasible_adp False, no ADP/BF and an unsaturated placeholder tc.
    Returned keys are a superset of the previous version's keys.
    """
    basis_known = bf_min is not None and float(bf_min) > 0
    bf_lim = float(bf_min) if basis_known else 0.0
    tdp = dewpoint(wc, p)
    result = dict(
        tc=None, direct_tc=None, achievable_without_reheat=False, adp_req_c=None, bf_req=None,
        bf_min=bf_lim, low_bf_warning=False, tdp=tdp, t_at_a2=tdp, feasible_adp=False,
        bf_basis="專案指定" if basis_known else "未提供（設備能力待資料）",
        bf_at_a2=None, t_min_reachable=None, t_max_reachable=None, path="infeasible", reason=None,
    )

    def infeasible(reason, tc, field=field_name):
        result.update(reason=reason, tc=max(tc, tdp), direct_tc=max(tc, tdp))
        if raise_on_infeasible:
            raise InputError(reason, field_name=field)
        return result

    def feasible(path, adp_t, tc):
        bf = at(adp_t)[0]
        result.update(tc=tc, direct_tc=tc, achievable_without_reheat=path == "direct", adp_req_c=adp_t,
                      bf_req=bf, low_bf_warning=bf < 0.05, path=path, feasible_adp=True)
        return result

    placeholder = max(tdp, min(s1["t"], ts))
    if tdp < a2 - airflow_guard.COIL_DEWPOINT_TOLERANCE_K:
        return infeasible("冷卻盤管所需露點低於供水＋ADP 裕度；需增加可用除濕風量或降低供水溫度", placeholder)

    def at(adp_t):
        sat = state_trh(adp_t, 100, p)
        bf = (wc - sat["w"]) / (s1["w"] - sat["w"])
        h = bf * s1["h"] + (1.0 - bf) * sat["h"]
        return bf, (h - 2501.0 * wc) / (1.006 + 1.86 * wc)

    bf_a2, t_a2 = at(a2)
    result.update(t_at_a2=t_a2, bf_at_a2=bf_a2)
    if bf_a2 < bf_lim - 1e-12:
        return infeasible(
            f"冷卻盤管無法除濕到 {wc * 1000:.3f} g/kg：BF 最高只能為 {bf_a2:.3f}（ADP 取最低 {a2:.2f}°C），"
            f"低於盤管 BF 下限 {bf_lim:g}；再熱無法解決",
            placeholder,
        )
    a_hi = tdp
    if bf_lim > 0:
        lo, hi = a2, tdp
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if at(mid)[0] >= bf_lim:
                lo = mid
            else:
                hi = mid
        a_hi = lo
    n = 400
    points = [a2 + (a_hi - a2) * k / n for k in range(n + 1)]
    temps = [at(x)[1] for x in points]

    def refine(k, sign):
        """Golden-section search for sign x t(A) around grid point k; never worse than it."""
        lo, hi = points[max(k - 1, 0)], points[min(k + 1, n)]
        g = (5 ** 0.5 - 1) / 2
        f = lambda x: sign * at(x)[1]
        x1, x2 = hi - g * (hi - lo), lo + g * (hi - lo)
        f1, f2 = f(x1), f(x2)
        for _ in range(60):
            if f1 >= f2:
                hi, x2, f2 = x2, x1, f1
                x1 = hi - g * (hi - lo)
                f1 = f(x1)
            else:
                lo, x1, f1 = x1, x2, f2
                x2 = lo + g * (hi - lo)
                f2 = f(x2)
        return max(points[k], 0.5 * (lo + hi), key=f)

    valid = [k for k in range(n + 1) if temps[k] >= tdp - 1e-09]
    if not valid:
        return infeasible(
            f"冷卻盤管旁通線在 BF 下限 {bf_lim:g} 內全部落入過飽和區（入口接近飽和）；"
            f"無可實現的出風，再熱無法解決",
            placeholder,
        )
    a_max = refine(max(valid, key=temps.__getitem__), 1)
    t_max = at(a_max)[1]
    t_min = max(tdp, min(temps[k] for k in valid))
    result.update(t_min_reachable=t_min, t_max_reachable=t_max)
    tol = 5e-07  # K; absorbs dew-point round-off between callers and this solver
    if ts >= tdp - tol:
        # A root t(A) = ts >= tdp is unsaturated, so any bracket counts; scan from the largest BF.
        pairs = sorted(set(zip(points, temps)) | {(a_max, t_max)})
        for (x0, y0), (x1, y1) in zip(pairs, pairs[1:]):
            if abs(y0 - ts) <= tol:
                return feasible("direct", x0, ts)
            if (y0 - ts) * (y1 - ts) <= 0:
                lo, hi, f_lo = x0, x1, y0 - ts
                for _ in range(80):
                    mid = 0.5 * (lo + hi)
                    f_mid = at(mid)[1] - ts
                    if f_lo * f_mid <= 0:
                        hi = mid
                    else:
                        lo, f_lo = mid, f_mid
                return feasible("direct", 0.5 * (lo + hi), ts)
        if abs(pairs[-1][1] - ts) <= tol:
            return feasible("direct", pairs[-1][0], ts)
    below = [k for k in valid if temps[k] < ts - tol]
    if not below:
        return infeasible(
            f"冷卻盤管在 BF 下限 {bf_lim:g}、出風含濕比 {wc * 1000:.3f} g/kg 時，最低可達出風乾球為 {t_min:.2f}°C，"
            f"高於送風目標 {ts:.2f}°C；再熱無法解決。需提供可達更低 BF 的盤管性能、降低供水溫度、提高送風溫度或增加除濕風量",
            t_min,
        )
    if t_max < ts:
        warm_a, warm_t = a_max, t_max
    else:  # admissible set with a gap around ts (not observed in sampling): best grid point below ts
        k = max(below, key=temps.__getitem__)
        warm_a, warm_t = points[k], temps[k]
    if allow_reheat == "0":
        # The coil point itself is admissible; what is missing is reheat (a system issue).
        reason = (f"冷卻盤管需再熱：送風目標 {ts:.2f}°C 高於盤管在出風含濕比 {wc * 1000:.3f} g/kg 時的最高可達出風 {warm_t:.2f}°C；"
                  f"目前不允許再熱")
        if raise_on_infeasible:
            raise InputError(reason, field_name="allow_reheat")
        feasible("reheat_required", warm_a, warm_t)
        result["reason"] = reason
        return result
    return feasible("reheat", warm_a, warm_t)


def condition_air(i, enter, m, ts, ws, pre=True, *, season="summer"):
    p = float(i["atm_kpa"])
    cp = float(i["water_cp"])
    a1 = (float(i["chw1_in"]) + float(i["adp_approach"])
          if i["pre_mode"] != "單盤管（一般空調箱）" else 0.0)
    a2 = float(i["chw2_in"]) + float(i["coil_approach"])
    supply = state_tw(ts, ws, p)
    s1 = enter
    beta = None
    mode = i["pre_mode"] if pre else "停用／旁通"
    if mode == "自動旁通因子估算":
        t1 = min(enter["t"], max(float(i["pre_t"]), a1))
        if t1 < enter["t"] - 1e-08:
            adp = state_trh(a1, 100, p)
            if enter["w"] <= adp["w"]:
                s1 = state_tw(t1, enter["w"], p)
            else:
                hv = 2501 + 1.86 * t1
                denominator = (
                    enter["h"] - adp["h"] - (enter["w"] - adp["w"]) * hv
                )
                if not math.isfinite(denominator) or denominator <= 1e-9:
                    raise InputError(
                        "一段盤管旁通因子無法求解，請核對入口與 ADP 狀態。", field_name="pre_t"
                    )
                beta = (1.006 * t1 + adp["w"] * hv - adp["h"]) / denominator
                beta = max(0, min(1, beta))
                s1 = c1_blend(enter, adp, beta, p, season=season,
                              target_t=t1, field_name="pre_t")
    elif mode == "指定出口（需求檢核）":
        s1 = state_trh(float(i["pre_t"]), float(i["pre_rh"]), p)
        if s1["t"] < a1 - 1e-08:
            raise InputError(f"一段指定出口低於供水＋ADP 裕度", field_name=f"pre_t")
        if s1["w"] < enter["w"] - 1e-10 and dewpoint(s1["w"], p) < a1 - 1e-08:
            raise InputError(f"一段除濕露點低於可達 ADP", field_name=f"pre_rh")
    c1 = coil_record("一段盤管", enter, s1, m, cp)
    wc = min(s1["w"], ws)
    c2_sol = None
    if wc < s1["w"] - 1e-10:
        c2_sol = solve_c2_bypass(
            s1,
            ts,
            wc,
            a2,
            p,
            allow_reheat=i.get("allow_reheat", "1"),
            bf_min=float(i.get("c2_bf_min", 0.0)),
            field_name="chw2_in",
        )
        tc = c2_sol["tc"]
    else:
        tc = min(s1["t"], ts)
    if tc < s1["t"] - 1e-08 and tc < a2 - 1e-07:
        raise InputError(f"冷卻盤管冷卻溫度低於可達 ADP", field_name=f"coil_approach")
    s2 = state_tw(tc, wc, p)
    c2 = coil_record("冷卻盤管" if i["pre_mode"] == "單盤管（一般空調箱）" else "二段盤管", s1, s2, m, cp)
    if c2_sol is not None:
        c2["direct_outlet_t"] = c2_sol["direct_tc"]
        c2["achievable_without_reheat"] = c2_sol["achievable_without_reheat"]
        c2["adp_req_c"] = c2_sol["adp_req_c"]
        c2["bf_req"] = c2_sol["bf_req"]
        c2["bf_min"] = c2_sol["bf_min"]
        c2["overcool_reheat_penalty_kw"] = max(0.0, m * (state_tw(c2_sol["direct_tc"], wc, p)["h"] - s2["h"]))
    heat_state = state_tw(ts, wc, p)
    heat = m * (heat_state["h"] - s2["h"])
    humid = m * (ws - wc)
    humid_kw = m * (supply["h"] - heat_state["h"])
    if heat < -1e-06:
        raise InputError(f"送風需要未配置的額外冷卻")
    if heat > 1e-06 and i["allow_reheat"] == "0":
        raise InputError(
            f"此工況需要加熱／再熱，請啟用或調整設計條件", field_name=f"allow_reheat"
        )
    if humid > 1e-09 and i["allow_humidify"] == "0":
        raise InputError(
            f"此工況需要加濕，請啟用或調整設計條件", field_name=f"allow_humidify"
        )
    residual = (
        c1["air_kw"] + c2["air_kw"] - heat - humid_kw - m * (enter["h"] - supply["h"])
    )
    return {
        "coil_configuration": "單盤管" if i["pre_mode"] == "單盤管（一般空調箱）" else "雙盤管／預冷旁通" if i["pre_mode"] == "停用／旁通" else "雙盤管",
        "enter": enter,
        "c1": c1,
        "c2": c2,
        "heat_state": heat_state,
        "supply": supply,
        "mass": m,
        "reheat_kw": max(0, heat),
        "humid_kg_h": max(0, humid * 3600),
        "humid_air_kw": max(0, humid_kw),
        "energy_residual_kw": residual,
        "pre_bf": beta,
    }


def calculate(p, isolate_utilities=False):
    workspace = None
    if isinstance(p, dict) and p.get("kind") == "facility_workspace":
        from .workspace_store import validate_workspace
        workspace = validate_workspace(p)
        p = workspace["main"]
    from .field_state import effective_main, main_inactive

    p = copy.deepcopy(
        validate_project(p, UTILITY_ONLY_KEYS if isolate_utilities else ())
    )
    i = effective_main(p["inputs"])
    n = lambda k: float(i[k])
    warn = []
    rtkw = US_RT_KW if i["rt_type"].startswith("US") else JRT_KW
    sf = 1 + n("sf") / 100
    room = state_trh(n("ra_t"), n("ra_rh"), n("atm_kpa"))
    oa = state_trh(n("oa_t"), n("oa_rh"), n("atm_kpa"))
    ow = state_trh(n("ow_t"), n("ow_rh"), n("atm_kpa"))
    light = lighting(i)
    zones = {}
    ppl = 0
    leak = 0
    for z in "AB":
        area = n("en_L_" + z) * n("en_W_" + z)
        vol = area * n("en_H_" + z)
        if area > 0 and vol <= 0:
            raise InputError(f"有面積時淨高必須大於零", field_name=f"en_H_{z}")
        count = integer(i["ppl_" + z], "ppl_" + z)
        if count and (not area):
            raise InputError(f"有人員時區域不可為零面積", field_name=f"ppl_{z}")
        cmh = (
            vol * n("en_ach_" + z)
            if i["mode_" + z] == "ACH"
            else area * n("coverage_" + z) * n("face_" + z) * 3600
        )
        dp = n("en_p_" + z)
        speed = n("leak_cd") * math.sqrt(2 * dp / room["rho_moist"]) if dp > 0 else 0.0
        keys = (
            ("en_gap_L", "en_gap_W", "en_door_A", "en_door_F")
            if z == "A"
            else ("gap_B_L", "gap_B_W", "door_B_A", "door_B_F")
        )
        gl, gw, da, df = [n(k) for k in keys]
        if i["leak_method"] == "門縫孔口法" and df * n("door_open_seconds") > 3600:
            raise InputError(
                f"開門總時間不可超過一小時", field_name=f"door_open_seconds"
            )
        if i["leak_method"] == "15Pa基準ACH法":
            l = vol * n("base_leak_ach") * math.sqrt(dp / 15) if dp > 0 else 0.0
        else:
            l = (gl * gw * 3600 + da * df * n("door_open_seconds")) * speed if area else 0
        zones[z] = {"area": area, "volume": vol, "cmh": cmh, "leak": l}
        ppl += count
        leak += l
    circ = sum((z["cmh"] for z in zones.values()))
    is_mau = i["sys_type"].startswith("MAU")
    ffu_count = 0  # Final count depends on the adopted OA and airflow basis.
    gross = n("eq_kw") * n("eq_rt") / 100
    pcw_properties = water_properties(i, "pcw")
    pcw = (
        integer(i["pcw_n"], "pcw_n")
        * n("pcw_lpm")
        / 60000
        * pcw_properties["rho"]
        * pcw_properties["cp"]
        * n("pcw_dt")
    )
    exheat = gross * n("exh_ratio") / 100
    if pcw + exheat > gross + 1e-06:
        raise InputError(
            f"PCW 與直接排氣帶走熱量超過同工況設備總發熱", field_name=f"pcw_n"
        )
    uconvert = 4.1868 / 3600 if i["u_unit"] == "kcal/(h·m²·K)" else 0.001
    parts = {
        "equipment_net": gross - pcw - exheat,
        "pcw_removed": pcw,
        "exhaust_removed": exheat,
        "people": ppl * n("people_sensible_w") / 1000,
        "lighting": light["kw"],
        "wall": n("en_wall") * n("wall_u") * (n("oa_t") - n("ra_t")) * uconvert,
        "floor": n("en_floor")
        * n("floor_u")
        * (n("floor_adj_t") - n("ra_t"))
        * uconvert,
        "oven": n("oven_kw"),
        "solar": n("solar_kw"),
        "fan": n("fan_room_kw") + ffu_count * n("ffu_w") / 1000,
    }
    qs = sum(
        (v for k, v in parts.items() if k not in ("pcw_removed", "exhaust_removed"))
    )
    latent = latent_breakdown(i)
    ql = latent["total_kw"]
    moist = ql / 2501
    if i["latent_mode"] == "尚不清楚（暫不計製程）":
        warn.append(
            "製程產濕尚未提供，目前只計人員；有開放水槽、濕洗或蒸汽洩漏時需補填，勿當作已完成除濕設計。"
        )
    ducts = {}
    for key in ["gex", "sex", "aex", "vex", "hex"]:
        nominal = to_cmh_strict(i[key + "_q"], i["u_" + key], key)
        design = nominal * (1 + n("exhaust_margin_pct") / 100)
        d = duct_selection(design, n("v_" + key), n("duct_ratio"), i["duct_shape"])
        d["nominal_cmh"] = nominal
        ducts[key.upper()] = d
    pvstd = std_lpm(i["pv_q"], i["u_pv"])
    pvroom = (
        pvstd
        / 1000
        * 60
        * n("gas_std_kpa")
        / n("atm_kpa")
        * (n("ra_t") + 273.15)
        / (n("gas_std_t") + 273.15)
        * n("pv_room_fraction")
    )
    minoa = max(
        leak + n("prd_q") + sum((d["flow_cmh"] for d in ducts.values())) + pvroom,
        ppl * n("oa_per_person"),
    )
    manual = n("en_manual_oa")
    if manual and manual < minoa - 1e-06:
        raise InputError(
            f"指定外氣 {manual:g} 低於補償下限 {minoa:.1f} CMH",
            field_name=f"en_manual_oa",
        )
    moa = (manual or minoa) / room["v_da"] / 3600
    minadp = n("chw2_in") + n("coil_approach")
    minw = state_trh(minadp, 100, n("atm_kpa"))["w"]
    if is_mau:
        if moist and minw >= room["w"]:
            raise InputError(
                f"可達含濕量不足以處理室內產濕，請降低冷卻盤管 ADP", field_name=f"chw2_in"
            )
        needed = moist / (room["w"] - minw) * 1.05 if moist else 0
        if manual and moa + 1e-09 < needed / 1.05:
            raise InputError(
                f"指定外氣不足以在二段 ADP 下維持室內濕度", field_name=f"en_manual_oa"
            )
        m = moa if manual else max(moa, needed)
        moa = m
        ts = n("mau_supply_t")
        if m == 0:
            if moist:
                raise InputError(f"零外氣無法處理產濕")
            ws = room["w"]
        else:
            ws = room["w"] - moist / m
        supply = state_tw(ts, ws, n("atm_kpa"))
        adopted_oa = moa * room["v_da"] * 3600
        plenum = i["ffu_topology"] == "MAU入靜壓箱經FFU送風"
        add_oa = plenum and i["ffu_airflow_basis"] == "室內基本循環（另加OA）"
        ffu_total = circ + adopted_oa if add_oa else circ
        dcc_return = circ if (add_oa or not plenum) else ffu_total - adopted_oa
        # Moisture generation and the achievable ADP determine OA analytically
        # above; FFU motor heat is sensible only and cannot change that OA mass.
        # Finalise FFU count AFTER that latent/OA solution, then recompute qs and
        # the DCC balance. No unneeded numerical fixed-point loop is introduced.
        ffu_count = math.ceil(ffu_total / n("ffu_cmh")) if ffu_total else 0
        if ffu_count and not sum(zone["area"] for zone in zones.values()):
            raise InputError("FFU配置需要大於零的室內面積", field_name="en_L_A")
        parts["fan"] = n("fan_room_kw") + ffu_count * n("ffu_w") / 1000
        qs = sum(v for k, v in parts.items() if k not in ("pcw_removed", "exhaust_removed"))
        mau_qs = m * (1.006 + 1.86 * ws) * (room["t"] - ts)
        dcc = max(0, qs - mau_qs)
        room_heat = max(0, mau_qs - qs)
        if room_heat > 1e-06:
            raise InputError(
                f"MAU 過冷或室內淨熱損，需要室內加熱控制；請調整送風溫度或改混合空調模式",
                field_name=f"mau_supply_t",
            )
        enter = oa
        airflow_basis = airflow_guard.not_applicable("MAU 外氣量由解析式決定；FFU 循環風量另計")
    else:
        ffu_total = 0.0
        dcc_return = 0.0
        m_floor = max(circ / room["v_da"] / 3600, moa, 1e-08)
        m = (
            m_floor
            if i.get("airflow_search_floor") == "circulation"
            else max(m_floor, abs(qs) / 10, moist / 0.002)
        )

        m_start = m
        # PHYSICAL: does any finite airflow exist? Raises with the cause and the remedy when it does not.
        airflow_exist = airflow_guard.existence(
            room, oa, moa, qs, moist, minadp, minw, n("atm_kpa"), m_start, n("coil_approach")
        )
        # NUMERICAL: the net moisture the coil must remove does not depend on the trial airflow. The old test
        # compared w(enter) with w(supply) against 1e-10 kg/kg; that difference is moisture / airflow, so at an
        # enormous airflow it fell below the tolerance and the search accepted a limit point (defect F-1).
        coil_moisture = airflow_guard.moisture_to_remove(room, oa, moa, moist)
        coil_moisture_tol = airflow_guard.humidity_tolerance(m_start)

        def _airflow_feasible(m_cand):
            ws_c = room["w"] - moist / m_cand
            if ws_c < 0:
                return False, ws_c, 0.0
            ts_c = room["t"] - qs / (m_cand * (1.006 + 1.86 * max(0, ws_c)))
            blend(oa, room, moa / m_cand, n("atm_kpa"))  # a supersaturated mixture is still rejected here
            humidity_possible = coil_moisture <= coil_moisture_tol or airflow_guard.supply_humidity_reachable(
                ws_c, minw, minadp, n("atm_kpa")
            )
            ok = (
                ts_c >= minadp
                and (ts_c <= 80)
                and humidity_possible
                and (dewpoint(ws_c, n("atm_kpa")) <= ts_c + 1e-07)
            )
            return ok, ws_c, ts_c

        prev_m = m_floor
        for step in range(airflow_guard.SEARCH_STEPS):
            ok, ws, ts = _airflow_feasible(m)
            if ok:
                if step > 0 and not _airflow_feasible(prev_m)[0]:
                    lo_m, hi_m = prev_m, m
                    for _ in range(32):
                        mid_m = 0.5 * (lo_m + hi_m)
                        if _airflow_feasible(mid_m)[0]:
                            hi_m = mid_m
                        else:
                            lo_m = mid_m
                    m = hi_m
                    _, ws, ts = _airflow_feasible(m)
                break
            prev_m = m
            m *= airflow_guard.SEARCH_GROWTH
        else:
            raise InputError(f"無法求得滿足顯熱／濕度與供水條件的送風量")
        enter = blend(oa, room, moa / m, n("atm_kpa"))
        airflow_basis = airflow_guard.describe(
            m, m_start, m_floor, room, qs, moist, minw, minadp, n("atm_kpa"), n("coil_approach"),
            n("chw2_in"), "circulation" if i.get("airflow_search_floor") == "circulation" else "load", airflow_exist,
        )
        if airflow_basis["load_driven"] and airflow_basis["inflation"] > airflow_guard.INFLATION_WARN:
            warn.append(
                f"供風量由{airflow_basis['governing']}決定：基準 {m_start * room['v_da'] * 3600:,.0f} CMH 增為 {airflow_basis['inflation']:.1f} 倍"
                f"（供風溫差 {airflow_basis['supply_dt_k']:.2f} K）；請確認冰水供水溫度與室內濕度目標。"
            )
        dcc = 0
        mau_qs = qs
        if not i["sys_type"].startswith("AHU"):
            warn.append(
                "FCU／RCU 採外氣於入口混入的等效控制體；實際外氣另接 MAU 時需另設系統拓樸。"
            )
    summer = condition_air(i, enter, m, ts, ws)
    if is_mau:
        dcc_flow_cmh = n("dcc_airflow_cmh") if i["dcc_airflow_mode"] == "獨立 DCC 循環" else dcc_return
        if dcc_flow_cmh > 0:
            m_dcc = dcc_flow_cmh / 3600 / room["v_da"]
            cp_room = 1.006 + 1.86 * room["w"]
            t_dcc_out = room["t"] - dcc / (m_dcc * cp_room)
            summer["dcc_outlet_t"] = t_dcc_out
            summer["dcc_condensation_risk"] = bool(t_dcc_out < dewpoint(room["w"], n("atm_kpa")) + 1e-6)
    winter_enter = ow if is_mau else blend(ow, room, moa / m, n("atm_kpa"))
    winter_room = None
    if i["winter_model"] == "室內熱濕平衡（定風量）":
        from .winter import room_targets

        winter_room = room_targets(
            i, room, parts, m, moist, ffu_kw=ffu_count * n("ffu_w") / 1000
        )
        winter = condition_air(
            i,
            winter_enter,
            m,
            winter_room["supply_t"],
            winter_room["supply_w"],
            pre=False,
            season="winter",
        )
        winter_room["sensible_residual_kw"] = (
            m
            * (1.006 + 1.86 * winter["supply"]["w"])
            * (room["t"] - winter["supply"]["t"])
            + winter_room["dcc_kw"]
            - winter_room.get("terminal_heat_kw", 0.0)
            - winter_room["sensible_kw"]
        )
        # Same test as the HW design load below: only an explicit "HW" source puts the
        # remaining room heat loss into HW; otherwise it stays an unassigned demand.
        winter_room["terminal_heat_source"] = "HW" if i.get("winter_terminal_heat_source") == "HW" else None
        if winter_room.get("mau_temp_capped"):
            warn.append(
                f"冬季 MAU 送風溫度已限制於上限 {winter_room['max_mau_t']:g}°C；剩餘室內熱損 {winter_room['terminal_heat_kw']:.2f}"
                + (" kW 已轉列室內加熱需求並計入 HW。" if winter_room["terminal_heat_source"] == "HW"
                   else " kW 列為未配置室內加熱需求，待指定熱源；未計入 HW 或 NP。")
            )
        winter_room["moisture_residual_kg_s"] = (
            m * (room["w"] - winter["supply"]["w"]) - winter_room["moisture_kg_s"]
        )
        if (
            abs(winter_room["sensible_residual_kw"]) > 1e-5
            or abs(winter_room["moisture_residual_kg_s"]) > 1e-8
        ):
            raise InputError("冬季室內守恆檢核失敗", field_name="winter_model")
    else:
        winter = condition_air(i, winter_enter, m, room["t"], room["w"], pre=False,
                               season="winter")
    dcc_design = max(dcc, winter_room["dcc_kw"] if winter_room else 0.0)
    if dcc_design > 1e-06 and n("dccw_in") < dewpoint(room["w"], n("atm_kpa")) + n(
        "dccw_dp_margin"
    ):
        raise InputError(f"乾盤管進水未達露點＋安全裕度", field_name=f"dccw_in")
    dcc = 0 if dcc < 1e-06 else dcc
    coilkw = summer["c1"]["water_kw"] + summer["c2"]["water_kw"]
    winter_coilkw = winter["c1"]["water_kw"] + winter["c2"]["water_kw"]
    terminal_coilkw = max(coilkw, winter_coilkw)
    summer["coincident_cooling_kw"] = coilkw + dcc
    winter["coincident_cooling_kw"] = winter_coilkw + (winter_room["dcc_kw"] if winter_room else 0.0)
    fcu_need = max(
        m * room["v_da"] * 3600 / n("en_fcu_cmh"), terminal_coilkw * sf / rtkw / n("fcu_rt")
    )
    counts = {
        "FFU": ffu_count,
        "DCC": (
            math.ceil(dcc_design * sf / rtkw / n("en_dcc_rt") - 1e-12) if is_mau else 0
        ),
        "FCU": math.ceil(fcu_need - 1e-12) if i["sys_type"].startswith("FCU") else 0,
        "RCU": (
            math.ceil(terminal_coilkw * sf / rtkw / n("en_rcu_rt") - 1e-12)
            if i["sys_type"].startswith("RCU")
            else 0
        ),
    }
    winter_terminal_heat_kw = (
        winter_room.get("terminal_heat_kw", 0.0) if winter_room else 0.0
    )
    heat = max(summer["reheat_kw"], winter["reheat_kw"] + (winter_terminal_heat_kw if i.get("winter_terminal_heat_source") == "HW" else 0.0))
    loads = {
        "MCHW": max(summer["c1"]["water_kw"], winter["c1"]["water_kw"]) * sf,
        "CHW": max(summer["c2"]["water_kw"], winter["c2"]["water_kw"]) * sf,
        "DCCW": dcc_design * sf,
        "PCW": pcw,
        "HW": heat * sf,
    }
    water = {}
    pressure = {}
    for key, q, u, delta in [
        ("MCHW", "mchw_q", "u_mchw", "chw1_dt"),
        ("CHW", "chw_q", "u_chw", "dt_chw"),
        ("DCCW", "dccw_q", "u_dccw", "dt_dccw"),
        ("PCW", "pcw_tot", "u_pcw_tot", "dt_pcw_sys"),
        ("HW", "hw_q", "u_hw", "dt_hw"),
    ]:
        conf = p["pressure_drop"][key]
        fluid = water_properties(i, key)
        linked = i[key.lower() + "_link"] == "連動負荷"
        flow = (
            loads[key] * 60000 / (fluid["rho"] * fluid["cp"] * n(delta))
            if linked
            else to_lpm_strict(i[q], i[u], key)
        )
        w = water_selection(
            flow, n("water_velocity_max"), "流速上限", float(conf["manual_id_mm"])
        )
        w.update(
            load_kw=loads[key],
            capacity_kw=flow / 60000 * fluid["rho"] * fluid["cp"] * n(delta),
            delta_t=n(delta),
            linked=linked,
            fluid_properties=fluid,
        )
        water[key] = w
        if not linked and w["capacity_kw"] + 1e-06 < loads[key]:
            warn.append(
                f"{key} 獨立水量容量 {w['capacity_kw']:.1f} kW，低於同範圍需求 {loads[key]:.1f} kW；請確認服務範圍或改連動。"
            )
        pressure[key] = pressure_result(
            conf,
            flow / 60000,
            w["id_mm"] / 1000,
            w["area_m2"],
            w["runs"],
            fluid["rho"],
            fluid["mu"],
            n("water_roughness_mm"),
        )
    for key, d in ducts.items():
        conf = p["pressure_drop"][key]
        manualid = float(conf["manual_id_mm"])
        if manualid:
            if d["shape"] != "圓管":
                raise InputError(f"{key} 自訂 ID 只適用圓管，請切換風管形狀或設 0", field_name="PD:" + key)
            if d["flow_cmh"]:
                d.update(
                    diameter_m=manualid / 1000,
                    area_m2=math.pi * (manualid / 1000) ** 2 / 4,
                )
                d["velocity_mps"] = d["flow_cmh"] / 3600 / d["area_m2"]
                if d["velocity_mps"] > d["velocity_limit_mps"] + 1e-08:
                    raise InputError(f"{key} 指定內徑超過流速上限", field_name="PD:" + key)
        pressure[key] = pressure_result(
            conf,
            d["flow_cmh"] / 3600,
            d["diameter_m"],
            d["area_m2"],
            1 if d["flow_cmh"] else 0,
            n("air_rho"),
            n("air_mu"),
            n("duct_roughness_mm"),
            False,
        )
    electric = {} if isolate_utilities else electrical_from_inputs(i)
    gas = {} if isolate_utilities else gas_from_inputs(i)
    missing = [
        k
        for k, d in pressure.items()
        if d["flow_m3s"] and (not d["equipment_included"])
    ]
    if missing:
        warn.append(
            "壓損 "
            + "、".join(missing)
            + " 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。"
        )
    quality = (
        QUALITY_PRESETS[i["upw_type"]]
        if i["upw_quality_mode"] == "自動參考值"
        else i["upw_res"]
    )
    upw = {
        "resistivity": quality,
        "lpm": n("upw_q"),
        "id_mm": (
            math.sqrt(4 * n("upw_q") / 60000 / math.pi / n("upw_v")) * 1000
            if n("upw_q")
            else 0
        ),
        "relation": "≤" if i["upw_v_mode"] == "最低維持流速" else "≥",
    }
    massres = m * (room["w"] - summer["supply"]["w"]) - moist
    sensres = (
        m * (1.006 + 1.86 * summer["supply"]["w"]) * (room["t"] - summer["supply"]["t"])
        + dcc
        - qs
    )
    if abs(massres) > 1e-08 or abs(sensres) > 1e-05:
        raise InputError(f"內部守恆檢核失敗，報告已停止")
    for chain in [summer, winter]:
        if abs(chain["energy_residual_kw"]) > 1e-05:
            raise InputError(f"盤管能量檢核失敗，報告已停止")
    if (
        summer["reheat_kw"]
        or summer["humid_kg_h"]
        or winter["reheat_kw"]
        or winter["humid_kg_h"]
    ):
        warn.append(
            "加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。"
        )
    r = {
        "version": VERSION,
        "project": p,
        "effective_inputs": i,
        "inactive_fields": main_inactive(p["inputs"]),
        "hash": project_hash(p),
        "room": room,
        "oa": oa,
        "winter_oa": ow,
        "light": light,
        "zones": zones,
        "parts": parts,
        "qs": qs,
        "ql": ql,
        "latent": latent,
        "moisture": moist,
        "minimum_oa_cmh": minoa,
        "oa_mass": moa,
        "oa_room_cmh": moa * room["v_da"] * 3600,
        "extra_relief_cmh": max(0, moa * room["v_da"] * 3600 - minoa),
        "circulation_cmh": circ,
        "supply_room_cmh": m * room["v_da"] * 3600,
        "summer": summer,
        "winter": winter,
        "dcc_kw": dcc,
        "dcc_sensible_kw": dcc,
        "q_room_sensible_kw": qs,
        "dcc_cmh": (n("dcc_airflow_cmh") if i["dcc_airflow_mode"] == "獨立 DCC 循環" else dcc_return) if is_mau else 0.0,
        "dcc_return_cmh": dcc_return,
        "ffu_topology": i["ffu_topology"],
        "ffu_airflow_basis": i["ffu_airflow_basis"],
        "ffu_total_cmh": ffu_total,
        "ffu_unit_cmh": n("ffu_cmh"),
        "ffu_count": ffu_count,
        "ffu_size": i["ffu_size"],
        "ffu_area_each": FFU_SIZES[i["ffu_size"]],
        "coverage_ratio": ffu_count * FFU_SIZES[i["ffu_size"]] / sum(z["area"] for z in zones.values()) * 100 if ffu_count else 0.0,
        "coverage_limit_pct": n("ffu_coverage_limit_pct"),
        "required_oa_cmh": minoa,
        "leakage_cmh": leak,
        "q_mau_kw": coilkw if is_mau else 0.0,
        "q_total_kw": max(summer["coincident_cooling_kw"], winter["coincident_cooling_kw"]),
        "q_total_rt": max(summer["coincident_cooling_kw"], winter["coincident_cooling_kw"]) / US_RT_KW,
        "q_total_basis": "夏冬同時峰值冷量（未加餘裕）",
        "q_loop_envelope_kw": sum(loads[key] for key in ("MCHW", "CHW", "DCCW")) / sf,
        "q_loop_envelope_rt": sum(loads[key] for key in ("MCHW", "CHW", "DCCW")) / sf / US_RT_KW,
        "counts": counts,
        "terminal_cooling_kw": terminal_coilkw,
        "terminal_cooling_season": "winter" if winter_coilkw > coilkw else "summer",
        "water": water,
        "pressure": pressure,
        "ducts": ducts,
        "electric": electric,
        "gas": gas,
        "upw": upw,
        "rt_kw": rtkw,
        "sf": sf,
        "mass_residual": massres,
        "sensible_residual": sensres,
        "warnings": warn,
        "airflow_basis": airflow_basis,
    }
    r["winter_room"] = winter_room
    r["dcc_design_kw"] = dcc_design
    r["dcc_design_season"] = "winter" if winter_room and winter_room["dcc_kw"] > dcc else "summer"
    r["dcc_design_cmh"] = r["dcc_cmh"]
    r["quality"] = assess_main(r)
    r["coverage_exceeded"] = r["coverage_ratio"] > r["coverage_limit_pct"]
    if is_mau:
        from .quality import assessment, finding
        issues = copy.deepcopy(r["quality"]["items"])
        finding(issues, "FFU天花板實體配置", "未達" if r["coverage_exceeded"] else "通過",
                f"FFU覆蓋率 {r['coverage_ratio']:.1f}%；專案可安裝上限 {r['coverage_limit_pct']:g}%，須另核實際模組及消防／照明空間。", "ffu_size")
        if r["coverage_exceeded"]:
            warn.append(f"FFU覆蓋率 {r['coverage_ratio']:.1f}% 超過專案安裝上限 {r['coverage_limit_pct']:g}%。")
        if ffu_count and not n("ffu_w"):
            finding(issues, "FFU入室發熱", "待資料", "目前單台FFU入室發熱為0；若功率尚未確認，室內顯熱及DCC負荷仍待補。", "ffu_w")
        if i["ffu_topology"] == "MAU入靜壓箱經FFU送風" and ffu_total + 1e-6 < r["oa_room_cmh"]:
            finding(issues, "FFU總風量與外氣", "未達", "FFU總送風小於OA，無法成立回風混合控制體；請增加循環需求或改用基本循環另加OA。", "ffu_airflow_basis")
        r["quality"] = assessment(issues)
    if workspace:
        from .contributions import aggregate_ledger
        from .quality import assessment, finding
        ledger = workspace["demand_ledger"]
        try:
            summary = aggregate_ledger(ledger, r["effective_inputs"])
        except (ValueError, KeyError, TypeError) as exc:
            summary = {"sources": list(ledger["entries"].values()), "water": [], "pending": [str(exc)], "updates": {}}
        r["demand_summary"] = summary
        issues = copy.deepcopy(r["quality"]["items"])
        for detail in summary["pending"]:
            finding(issues, "需求彙整待確認", "待資料", detail, None)
        if any(r["project"]["inputs"][k] != v for k, v in ledger["last_updates"].items()):
            finding(issues, "需求彙整目的值已修改", "待資料", "來源明細保留，但主案已有手動修改；請重新預覽帶入或移除來源，彙整表不能當成目前主案採用值。", None)
        documents = {d["id"]: d for d in workspace["ahus"]}
        from .design_workflow import ahu_source_hash
        for source in ledger["entries"].values():
            if source["kind"] == "AHU":
                document = documents.get(source["id"])
                if document is None or ahu_source_hash(document["inputs"]) != source["source_hash"]:
                    finding(issues, "來源快照：" + source["name"], "待資料", "來源未保存或已修改；需求仍採上次帶入值，請重新檢核。", None)
        r["quality"] = assessment(issues)
    return r


def electrical_from_inputs(i):
    n = lambda k: float(i[k])
    ei = dict(EXTRA_DEFAULTS)
    ei.update(i)
    # The workbench exposes ranges, not numeric ambient/count inputs. Represent
    # the adopted range in the adapter instead of fabricating -20 C / 1 wire.
    ambient_upper = {
        "35℃ 以下 (標準)": 35, "36~40℃": 40, "41~45℃": 45,
        "46~50℃": 50, "51~55℃": 55,
    }
    conductor_upper = {
        "3根以下 (標準)": 3, "4根": 4, "5~6根": 6, "7~9根": 9,
        "10~20根": 20, "21~30根": 30, "31~40根": 40, "41根以上": 41,
    }
    ei.update(
        e_ambient_c=str(ambient_upper[i["e_temp"]]),
        e_loaded_conductors=str(conductor_upper[i["e_pipe"]]),
        e_up_hp="0", e_up_kw="0",
    )

    def load_kw(key):
        v = n(key)
        unit = i["u_" + key]
        pan = key.split("_")[1]
        pf_key = "e_" + pan + "_pf"
        pf = n(pf_key) if i.get("e_" + pan + "_pf_mode") == "本盤獨立 PF" else n("e_pf")
        return electrical_power_kw(v, unit, VOLTAGE_MAP[i["e_volt"]], pf, i["e_eff"], key)

    for pan, keys in [
        ("up", ["eq", "oven"]),
        ("np", ["fan", "heat", "humid", "exh", "pump"]),
    ]:
        ei[f"e_{pan}_has_hp"] = any(i[f"u_e_{pan}_{key}"] == "HP" for key in keys)
        hp = sum((n(f"e_{pan}_{key}") for key in keys if i[f"u_e_{pan}_{key}"] == "HP"))
        kw = sum((load_kw(f"e_{pan}_{key}") for key in keys))
        if pan == "up":
            ei.update(
                e_up_hp=str(hp),
                e_up_kw=str(max(0, kw - hp * 0.745699871582 / n("e_eff"))),
                e_up_oven="0",
            )
        else:
            ei.update(
                e_np_fan=str(hp),
                u_e_np_fan="HP",
                e_np_pump=str(max(0, kw - hp * 0.745699871582 / n("e_eff"))),
                u_e_np_pump="kW",
            )
            for key in ["heat", "humid", "exh"]:
                ei["e_np_" + key] = "0"
                ei["u_e_np_" + key] = "kW"
    return electrical_result(ei, [])


def gas_from_inputs(i):
    gi = dict(EXTRA_DEFAULTS)
    gi.update(i)
    for j in (1, 2, 3):
        gi[f"gas{j}_q"] = str(std_lpm(i[f"gas{j}_q"], i[f"u_gas{j}"]))
    gi["pv_q"] = str(std_lpm(i["pv_q"], i["u_pv"]))
    gi["pv_torr"] = str(pv_to_torr(i["pv_torr"], i["pv_pressure_unit"]))
    return gas_result(gi, [])
