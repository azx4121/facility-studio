"""Room moisture balance and the existing MAU coil solver, one control volume."""
from .errors import InputError, ValidationError
from .utils import number, state_trh, state_tw, dewpoint


def evaluate(data, airflow):
    from .engine import condition_air
    from .schema import DEFAULTS

    def n(key, default, low, high):
        return number(data.get(key, default), key, low, high)

    p = n("room_pressure", "101.325", 60, 120)
    room = state_trh(n("room_t", "22", 5, 40), n("room_rh", "50", 1, 95), p)
    outdoor = state_trh(n("outdoor_t", "35", -40, 60), n("outdoor_rh", "70", 0, 100), p)
    supply_t = n("mau_supply_t", "22", 5, 40)
    process = n("process_moisture", "0", 0, 1e6)
    people = airflow["persons"] * n("people_latent_w", "55", 0, 1000) / 1000 * 3600 / 2501
    water_t = n("coil_water_t", "7", 0, 30)
    approach = n("coil_approach", "1", .1, 15)
    bf_text = str(data.get("coil_bf_min", "")).strip()
    bf = number(bf_text, "coil_bf_min", 0, .5) if bf_text else None
    mass = airflow["oa_cmh"] / 3600 / room["v_da"]
    result = dict(room=room, outdoor=outdoor, pressure_kpa=p, mass_da_kg_s=mass,
                  people_moisture_kg_h=people, process_moisture_kg_h=process,
                  room_moisture_kg_h=people + process, supply=None, coil=None,
                  supply_dewpoint_c=None, status="未達條件", warnings=[],
                  performance_confirmed=False, bf_min=bf, water_t=water_t,
                  approach_k=approach, supply_t_c=supply_t)
    if mass <= 0:
        result["warnings"].append("MAU 外氣量為零，沒有可用的送風控制體；請提供外氣量。")
        return result
    ws = room["w"] - (people + process) / 3600 / mass
    result["required_supply_w"] = ws
    if ws < 0:
        result["warnings"].append("室內產濕超過此 MAU 風量可移除的上限，所需送風含濕比為負；請增加外氣量或調整除濕分工。")
        return result
    result["supply_dewpoint_c"] = dewpoint(ws, p)
    try:
        supply = state_tw(supply_t, ws, p)
    except InputError:
        result["warnings"].append("MAU 送風溫度低於所需送風露點，形成過飽和需求；請提高送風溫度。")
        return result
    result["supply"] = supply
    result["room_moisture_residual_kg_s"] = mass * (room["w"] - ws) - (people + process) / 3600
    inputs = dict(DEFAULTS, pre_mode="單盤管（一般空調箱）", atm_kpa=str(p),
                  chw2_in=str(water_t), coil_approach=str(approach))
    if bf is not None:
        inputs["c2_bf_min"] = str(bf)
    try:
        coil = condition_air(inputs, outdoor, mass, supply_t, ws)
    except InputError as error:
        result["warnings"].append("MAU 盤管需求不可達：" + str(error))
        return result
    result["coil"] = coil
    result["coil_condensate_kg_h"] = coil["c2"]["condensate_kg_s"] * 3600
    result["coil_air_kw"] = coil["c2"]["air_kw"]
    result["coil_water_kw"] = coil["c2"]["water_kw"]
    result["status"] = "需求計算完成；實體盤管能力待核對"
    result["warnings"].append("此頁依室內產濕反算送風與單盤管需求；實體除濕能力須在分段空調箱填入幾何或原廠性能核對。")
    if bf is None:
        result["warnings"].append("盤管 BF 下限未提供，目前僅為理想需求下界，不能宣稱實機可達。")
    return result


def ahu_inputs(result):
    """Explicit independent snapshot; never changes an existing main project."""
    from .ahu_schema import NM_DEFAULTS
    mau = result["mau"]
    if mau["supply"] is None or mau["mass_da_kg_s"] <= 0:
        raise ValidationError("無有效 MAU 送風需求，請先修正潔淨室條件。", "room_rh")
    sa, oa = mau["supply"], mau["outdoor"]
    if oa["t"] < -30:
        raise ValidationError("外氣低於單機夏季入口 -30°C 下限；請在單機採用適用的冬季條件核對，不能自動改寫外氣。", "outdoor_t")
    # The legacy AHU humidity validator is 5..95%: do not silently clamp a
    # legitimate but unsupported short-form target into a different state.
    if not 5 <= sa["rh"] <= 95:
        raise ValidationError("送風濕度超出單機表單 5～95%RH 範圍；請調整送風溫度，不能自動截斷濕度。", "mau_supply_t")
    values = dict(NM_DEFAULTS, name="潔淨室條件快照（獨立單機，變更請重新建立）",
                  flow=str(mau["mass_da_kg_s"] * sa["v_da"] * 3600),
                  p=str(mau["pressure_kpa"]), summer_t=str(oa["t"]), summer_rh=str(oa["rh"]),
                  sa_t=str(sa["t"]), sa_rh=str(sa["rh"]),
                  summer_c1_mode="旁通", winter_c1_mode="旁通",
                  c2_in=str(mau["water_t"]), c2_adp=str(mau["approach_k"]),
                  c2_out=str(mau["water_t"] + 5))
    if mau["bf_min"] is not None:
        values["c2_bf_min"] = str(mau["bf_min"])
    from .ahu_engine import nm_validate
    nm_validate(values)
    return values
