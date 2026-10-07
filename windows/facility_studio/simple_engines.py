"""Independent everyday calculations, with explicit adopted assumptions."""

import math

from .data import NFB_SIZES, PIPE_DB, WIRE_DB
from .errors import ValidationError
from .quick_tools import (
    UNITS,
    UNIT_ALIASES,
    UNIT_HELP,
    convert_all,
    psychrometric,
    water_heat,
)
from .utils import TEMP_FACTORS, darcy_factor, duct_selection, group_factor
from .utils import integer, number, water_selection

SUPPLIES = {
    "三相 380V": (3, 380.0),
    "三相 220V": (3, 220.0),
    "三相 208V": (3, 208.0),
    "三相 400V": (3, 400.0),
    "三相 480V": (3, 480.0),
    "單相 220V": (1, 220.0),
    "單相 110V": (1, 110.0),
}
FLOW_FACTORS = {"CMH": 1.0, "CFM": 1.69901079552, "L/s": 3.6}
GAS_FLOW_FACTORS = {"SLPM": 1.0, "SCFM": 28.316846592, "Sm³/h": 1000 / 60}
GAS_PRESSURE_FACTORS = {
    "bar(g)": 100.0,
    "kPa(g)": 1.0,
    "kgf/cm²(g)": 98.0665,
    "MPa(g)": 1000.0,
}
AIR_PRESSURE_FACTORS = {"Pa": 1.0, "mmAq": 9.80665, "kPa": 1000.0}


def selected(value, options, key):
    if value not in options:
        raise ValidationError("請選擇有效選項", key)
    return value


def electrical(
    data, *, supply_override=None, design_current_a=None, conservative_drop=False
):
    kw = number(data["power"], "power", 0, 1000000)
    if supply_override is None:
        supply = selected(data["supply"], SUPPLIES, "supply")
        phases, voltage = SUPPLIES[supply]
    else:
        phases = integer(supply_override[0], "phases", 1, 3)
        if phases not in (1, 3):
            raise ValidationError("相數限1或3", "phases")
        voltage = number(supply_override[1], "voltage", 50, 690)
        supply = f"{'三相' if phases == 3 else '單相'} {voltage:g}V"
    kind = selected(data["kind"], ("一般設備", "連續運轉", "馬達"), "kind")
    pf = number(data["pf"], "pf", 0.1, 1)
    length = number(data["length"], "length", 0, 10000)
    ambient = number(data["ambient"], "ambient", -20, 55)
    loaded = integer(data["loaded"], "loaded", 1, 10000)
    insulation = selected(data["insulation"], ("XLPE", "PVC"), "insulation")
    terminal = int(selected(data["terminal"], ("60", "75", "90"), "terminal"))
    drop_limit = number(data["drop_limit"], "drop_limit", 0.1, 20)
    factor = math.sqrt(3) if phases == 3 else 1.0
    current = kw * 1000 / (factor * voltage * pf)
    design = current * (1.25 if kind != "一般設備" else 1.0)
    if design_current_a is not None:
        design = number(design_current_a, "design_current_a", current - 1e-8, 100000000)
    temperature = 90 if insulation == "XLPE" else 60
    dt = next(
        correction
        for limit, correction in TEMP_FACTORS[temperature]
        if ambient <= limit
    )
    dp = group_factor(loaded)
    options = []
    if kw > 0:
        for runs in range(1, 9):
            for row in WIRE_DB:
                size = row["size_mm2"]
                if size < 3.5 or (runs > 1 and size < 50):
                    continue
                base = row["XLPE_A" if temperature == 90 else "PVC_A"]
                terminal_cap = row["PVC_A"] if terminal < 90 else base
                iz = runs * min(base * dt * dp, terminal_cap)
                protection_cap = min(iz, {3.5: 20, 5.5: 30}.get(size, math.inf))
                at = next(
                    (
                        rating
                        for rating in NFB_SIZES
                        if design <= rating + 1e-9 and rating <= protection_cap + 1e-9
                    ),
                    None,
                )
                resistance = (
                    0.017241
                    * (1 + 0.00393 * (min(temperature, terminal) - 20))
                    * 1000
                    / size
                )
                drop_factor = math.sqrt(3) if phases == 3 else 2.0
                drop_v = (
                    drop_factor
                    * current
                    * (resistance * pf + 0.08 * math.sqrt(1 - pf * pf))
                    * length
                    / 1000
                    / runs
                )
                if conservative_drop:
                    # A feeder may serve different PFs and combinations of active equipment.
                    drop_v = (
                        drop_factor
                        * design
                        * math.hypot(resistance, 0.08)
                        * length
                        / 1000
                        / runs
                    )
                drop_pct = 100 * drop_v / voltage
                if at is not None and drop_pct <= drop_limit + 1e-9:
                    options.append(
                        dict(
                            runs=runs,
                            size_mm2=size,
                            ampacity_a=iz,
                            nfb_a=at,
                            drop_v=drop_v,
                            drop_pct=drop_pct,
                        )
                    )
        if not options:
            raise ValidationError(
                "目前參考表找不到符合電流及壓降的線徑；請調整長度或在完整工作台評估。",
                "power",
            )
    candidate = (
        min(options, key=lambda row: (row["runs"], row["size_mm2"]))
        if options
        else None
    )
    return dict(
        tool="electrical",
        power_kw=kw,
        supply=supply,
        phases=phases,
        voltage=voltage,
        pf=pf,
        current_a=current,
        design_a=design,
        kind=kind,
        selected=candidate,
        length_m=length,
        dt=dt,
        dp=dp,
        terminal_c=terminal,
        drop_basis="設計電流與R/X阻抗上界" if conservative_drop else "運轉電流及輸入PF",
        formula="三相 I=P×1000/(√3×V×PF)；單相 I=P×1000/(V×PF)。連續／馬達初估採125%；候選需滿足設計電流≤AT≤有效載流量。",
        note="kW 是電氣輸入。線徑使用原專案初估表；缺少75°C端子表時採60°C表。馬達NFB仍須核啟動與獨立過載保護；中性線、接地及短路容量另核。",
    )


def ducts(data):
    unit = selected(data["flow_unit"], FLOW_FACTORS, "flow_unit")
    cmh = number(data["flow"], "flow", 0, 10000000) * FLOW_FACTORS[unit]
    check_path = selected(str(data.get("check_path", "0")), ("0", "1"), "check_path")
    pressure_unit = selected(
        data["pressure_unit"], AIR_PRESSURE_FACTORS, "pressure_unit"
    ) if check_path == "1" else "Pa"
    pressure = (
        (number(data["pressure"], "pressure", 0, 1000000) if check_path == "1" else 0)
        * AIR_PRESSURE_FACTORS[pressure_unit]
    )
    if check_path == "0":
        try:
            # Preserve a valid draft for unit switching; it is not a sizing
            # condition and must never make dimensions-only mode fail.
            pressure = number(data["pressure"], "pressure", 0, 1000000) * AIR_PRESSURE_FACTORS[data["pressure_unit"]]
        except (ValueError, KeyError):
            pressure = 0.0
    velocity = number(data["velocity"], "velocity", 0.1, 40)
    ratio = number(data["ratio"], "ratio", 1, 4)
    rectangle = duct_selection(cmh, velocity, ratio, "方管")
    round_duct = duct_selection(cmh, velocity, ratio, "圓管")
    length = None
    if check_path == "1":
        length = number(data["length"], "length", 0, 100000)
        k = number(data["k_sum"], "k_sum", 0, 10000)
        equipment = number(data["equipment"], "equipment", 0, 1000000)
        for result in (rectangle, round_duct):
            v, diameter = result["velocity_mps"], result["diameter_m"]
            reynolds = 1.2 * v * diameter / 0.0000181
            f = (
                darcy_factor(reynolds, 0.00009 / diameter)
                if diameter > 0 and v > 0
                else 0.0
            )
            dynamic = 1.2 * v * v / 2
            friction = f * length / diameter * dynamic if diameter > 0 else 0.0
            loss = friction + k * dynamic + equipment if cmh > 0 else 0.0
            result.update(
                loss_pa=loss,
                friction_pa=friction,
                k=k,
                equipment_pa=equipment if cmh > 0 else 0.0,
                pressure_margin_pa=pressure - loss if cmh > 0 else 0.0,
                budget_sufficient=pressure >= loss if cmh > 0 else None,
            )
    return dict(
        tool="duct",
        flow_cmh=cmh,
        pressure_pa=pressure,
        velocity_limit=velocity,
        ratio=ratio,
        rectangle=rectangle,
        round=round_duct,
        path_checked=length is not None,
        length_m=length,
        formula="A=風量/3600/風速；圓管D=√(4A/π)。路徑阻力=f×L/Dh×ρv²/2＋ΣK×ρv²/2＋設備壓降。",
        note="靜壓是可用於管路的壓力預算，不能單獨決定尺寸。未勾選已知路徑時不判定壓力是否足夠；圓管依2英吋級距選取。",
    )


def compressed_air(data):
    gas = selected(data["gas"], ("CDA", "N2", "Ar"), "gas")
    flow_basis = selected(data.get("flow_basis", "標準流量"), ("標準流量", "管內實際流量"), "flow_basis")
    flow_factors = GAS_FLOW_FACTORS if flow_basis == "標準流量" else {"ALPM": 1, "ACFM": 28.316846592, "Am³/h": 1000 / 60}
    unit = selected(data["flow_unit"], flow_factors, "flow_unit")
    amount = number(data["flow"], "flow", 0, 100000000) * flow_factors[unit]
    pressure_unit = selected(
        data["pressure_unit"], GAS_PRESSURE_FACTORS, "pressure_unit"
    )
    gauge_kpa = (
        number(data["pressure"], "pressure", 0, 30000)
        * GAS_PRESSURE_FACTORS[pressure_unit]
    )
    if gauge_kpa > 30000:
        raise ValidationError("表壓超出300 bar初估範圍", "pressure")
    velocity = number(data["velocity"], "velocity", 0.1, 100)
    temperature = number(data["temperature"], "temperature", -60, 150)
    atm = number(data["atmosphere"], "atmosphere", 60, 120)
    reference_t = number(data["reference_t"], "reference_t", -60, 60)
    reference_p = number(data["reference_p"], "reference_p", 60, 120)
    absolute = atm + gauge_kpa
    standard = amount if flow_basis == "標準流量" else amount * absolute / reference_p * (reference_t + 273.15) / (temperature + 273.15)
    actual = (
        standard
        * reference_p
        / absolute
        * (temperature + 273.15)
        / (reference_t + 273.15)
    )
    required = (
        math.sqrt(4 * actual / 60000 / math.pi / velocity) * 1000 if standard else 0.0
    )
    pipe = (
        next((row for row in PIPE_DB if row["id"] >= required), None)
        if standard
        else None
    )
    if standard and pipe is None:
        raise ValidationError("需求超過參考管徑表，不能把最大管徑當成符合。", "flow")
    speed = actual / 60000 / (math.pi * (pipe["id"] / 1000) ** 2 / 4) if pipe else 0.0
    return dict(
        tool="gas",
        flow_basis=flow_basis,
        gas=gas,
        standard_lpm=standard,
        actual_lpm=actual,
        absolute_kpa=absolute,
        gauge_kpa=gauge_kpa,
        minimum_id_mm=required,
        pipe=pipe,
        velocity_mps=speed,
        velocity_limit=velocity,
        temperature_c=temperature,
        reference_t=reference_t,
        reference_p=reference_p,
        formula="實際流量=標準流量×P標準/P絕對×T管內(K)/T標準(K)；D內=√(4Q實際/πv)。",
        note="壓力採管內表壓，另加所在地大氣壓。理想氣體Z=1，僅流速定寸；參考內徑需依實供管材核對，長管路另算壓降。",
    )


def lighting(data):
    mode = selected(data["mode"], ("估算照度", "反算燈數"), "mode")
    area_mode = selected(
        data["area_mode"], ("面積 m²", "面積 坪", "長×寬", "體積 m³"), "area_mode"
    )
    if area_mode == "長×寬":
        area = number(data["length"], "length", 0.01, 10000) * number(
            data["width"], "width", 0.01, 10000
        )
    else:
        area = number(data["area"], "area", 0.01, 10000000)
        if area_mode == "面積 坪":
            area *= 400 / 121
        elif area_mode == "體積 m³":
            area /= number(data["height"], "height", 0.1, 100)
    watts = number(data["watts"], "watts", 0, 100000)
    lumen_mode = selected(
        data["lumen_mode"], ("LED功率初估", "燈具型錄流明"), "lumen_mode"
    )
    if lumen_mode == "LED功率初估":
        efficacy = number(data["efficacy"], "efficacy", 1, 300)
        lumens = watts * efficacy
    else:
        lumens = number(data["lumens"], "lumens", 0.01, 10000000)
    utilization = number(data["utilization"], "utilization", 0.01, 1)
    maintenance = number(data["maintenance"], "maintenance", 0.01, 1)
    if mode == "反算燈數":
        target = number(data["target"], "target", 0, 100000)
        if lumens <= 0:
            raise ValidationError("反算燈數時，每盞光通量必須大於零。", "watts")
        qty = math.ceil(target * area / (lumens * utilization * maintenance) - 1e-12)
    else:
        qty = integer(data["quantity"], "quantity", 0, 1000000)
        target = None
    illuminance = qty * lumens * utilization * maintenance / area
    return dict(
        tool="lighting",
        area_m2=area,
        quantity=qty,
        watts=watts,
        lumens_per_lamp=lumens,
        lumen_mode=lumen_mode,
        utilization=utilization,
        maintenance=maintenance,
        illuminance_lux=illuminance,
        total_kw=qty * watts / 1000,
        target_lux=target,
        formula="平均照度Lux=盞數×每盞流明lm×利用率U×維護係數M/面積m²；所需盞數向上取整。",
        note="Lux是空間照度，燈具光通量使用lm。體積須除以淨高換算面積；LED功率初估使用假設光效，不能代替型錄流明或照度均勻度模擬。",
    )


def water(data):
    mode = selected(data["mode"], ("已知水量", "已知熱量"), "mode")
    delta = number(data["delta"], "delta", 0.1, 100)
    if mode == "已知水量":
        unit = selected(data["flow_unit"], ("LPM", "US GPM", "m³/h"), "flow_unit")
        value = number(data["flow"], "flow", 0, 10000000)
        lpm = convert_all("水量", value, unit)["LPM"]
        thermal = water_heat("熱量 kW", lpm, delta)
    else:
        unit = selected(data["power_unit"], ("kW", "US RT"), "power_unit")
        kw = convert_all("冷熱功率", number(data["power"], "power", 0, 10000000), unit)[
            "kW"
        ]
        thermal = water_heat("流量 LPM", kw, delta)
        lpm = thermal["lpm"]
    limit = number(data["velocity"], "velocity", 0.1, 10)
    pipe = water_selection(lpm, limit)
    return dict(
        tool="water",
        thermal=thermal,
        pipe=pipe,
        velocity_limit=limit,
        formula=thermal["formula"],
        note="水物性採ρ=1000 kg/m³、cp=4.1868 kJ/(kg·K)；管徑按流速上限初估。未計水泵揚程與設備壓降。",
    )


def air_state(data):
    temperature = number(data["temperature"], "temperature", -60, 90)
    rh = number(data["rh"], "rh", 0, 100)
    atmosphere = number(data["atmosphere"], "atmosphere", 60, 120)
    state = psychrometric("乾球＋RH", temperature, rh, atmosphere)
    return dict(
        tool="air",
        state=state,
        formula="w=0.621945×Pw/(P−Pw)；h=1.006T＋w(2501＋1.86T)，以kg乾空氣為基準。",
        note="濕度0%時露點無有限值；顯示為無有限露點，不以假數值代替。",
    )


def unit_conversion(data):
    category = selected(
        UNIT_ALIASES.get(data["category"], data["category"]), UNITS, "category"
    )
    results = convert_all(category, data["value"], data["unit"])
    return dict(
        tool="units",
        category=category,
        values=results,
        formula={
            "溫度差（升溫／降溫）": "ΔT(K)=ΔT(°C)=ΔT(°F)×5/9。",
            "閥門流量係數（Kv／Cv）": "Kv≈0.865×Cv(US)；Cv(US)≈Kv/0.865。",
        }.get(category, "依所選物理量進行等值換算；溫度本身包含零點位移。"),
        note=UNIT_HELP.get(category, "依所選單位等值換算。"),
    )


ENGINES = {
    "electrical": electrical,
    "duct": ducts,
    "gas": compressed_air,
    "lighting": lighting,
    "water": water,
    "air": air_state,
    "units": unit_conversion,
}


def calculate_tool(tool, data):
    if tool not in ENGINES:
        raise ValidationError("沒有這個簡易工具", "tool")
    return ENGINES[tool](data)
