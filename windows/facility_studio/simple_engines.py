"""Independent everyday calculations, with explicit adopted assumptions."""

import math

from .data import (NFB_SIZES, PIPE_DB, WIRE_DB, FFU_SIZES, ROUGHNESS_MM, HVAC_PIPES, HVAC_PIPE_REFERENCES,
                   STANDARD_MOTOR_KW)
from .errors import ValidationError
from .gas_catalog import GAS_OPTIONS, CUSTOM_GAS, custom_name
from .quick_tools import (
    UNITS,
    UNIT_ALIASES,
    UNIT_HELP,
    convert_all,
    psychrometric,
    water_heat,
)
from .utils import TEMP_FACTORS, darcy_factor, duct_selection, group_factor
from .utils import integer, number, water_selection, load_current, next_standard

US_RT_KW = 3.5168528420667

ELECTRICAL_POWER_UNITS = ("kW", "W", "HP", "PS", "A", "kVA")
MOTOR_POWER_UNITS = ("HP", "PS")
HP_KW = 0.745699871582
PS_KW = 0.73549875


def electrical_power_factor(unit, motor_efficiency="0.90"):
    """Electrical input for kW/W; shaft output divided by efficiency for HP/PS."""
    selected(unit, ("kW", "W", "HP", "PS"), "power_unit")
    eta = (number(motor_efficiency, "motor_efficiency", 0.1, 1)
           if unit in MOTOR_POWER_UNITS else 1.0)
    return {"kW": 1.0, "W": 0.001, "HP": HP_KW, "PS": PS_KW}[unit] / eta


def electrical_unit_factor(unit, voltage, pf, eta, phases):
    """Return effective electrical input kW per 1 unit of the selected power_unit."""
    phase_factor = math.sqrt(3) if phases == 3 else 1.0
    if unit in ("kW", "W", "HP", "PS"):
        return electrical_power_factor(unit, eta)
    if unit == "A":
        return phase_factor * voltage * pf / 1000.0
    if unit == "kVA":
        return pf
    raise ValidationError("請選擇有效選項", "power_unit")


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
    power_unit = selected(data.get("power_unit", "kW"), ELECTRICAL_POWER_UNITS, "power_unit")
    raw_power = number(data["power"], "power", 0, 1000000000)
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
    has_motor = power_unit in MOTOR_POWER_UNITS
    eta = (number(data.get("motor_efficiency", "0.90"), "motor_efficiency", 0.1, 1)
           if has_motor else 1.0)
    el_kw = raw_power * electrical_unit_factor(power_unit, voltage, pf, eta, phases)
    kw = el_kw
    if kw > 1000000:
        raise ValidationError("不可大於 1000000", "power")
    length = number(data["length"], "length", 0, 10000)
    ambient = number(data["ambient"], "ambient", -20, 55)
    loaded = integer(data["loaded"], "loaded", 1, 10000)
    insulation = selected(data["insulation"], ("XLPE", "PVC"), "insulation")
    terminal = int(selected(data["terminal"], ("60", "75", "90"), "terminal"))
    drop_limit = number(data["drop_limit"], "drop_limit", 0.1, 20)
    if "mau_input_kw" in data:
        number(data["mau_input_kw"], "mau_input_kw", 0, 1000000)
    if "process_input_kw" in data:
        number(data["process_input_kw"], "process_input_kw", 0, 1000000)
    chiller_in = number(data["chiller_input_kw"], "chiller_input_kw", 0, 1000000) if "chiller_input_kw" in data else 0.0
    if "chiller_cop" in data and chiller_in == 0:
        number(data["chiller_cop"], "chiller_cop", 0, 20)
    factor = math.sqrt(3) if phases == 3 else 1.0
    current = load_current(kw, voltage, pf, 1.0, phases)
    design = current * (1.25 if kind != "一般設備" or has_motor else 1.0)
    if design_current_a is not None:
        design = number(design_current_a, "design_current_a", current - 1e-8, 100000000)
    design_breaker = design
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
    # This is the same protected circuit as the selected conductor, not an
    # independently sized upstream main feeder.
    breaker_at = candidate["nfb_a"] if candidate else None
    equivalents = {
        u: el_kw / electrical_unit_factor(u, voltage, pf, eta, phases)
        for u in ELECTRICAL_POWER_UNITS
        if u not in MOTOR_POWER_UNITS or has_motor
    }
    return dict(
        tool="electrical",
        input_value=raw_power,
        power_value=raw_power,
        power_unit=power_unit,
        power_kw=kw,
        eta=eta,
        motor_efficiency=eta if has_motor else None,
        shaft_kw=el_kw * eta if has_motor else None,
        electrical_input_kw=el_kw,
        equivalent_hp=equivalents.get("HP"),
        apparent_kva=equivalents["kVA"],
        power_w=equivalents["W"],
        equivalents=equivalents,
        supply=supply,
        phases=phases,
        voltage=voltage,
        pf=pf,
        current_a=current,
        design_a=design,
        design_breaker_a=design_breaker,
        recommended_breaker_at=breaker_at,
        warnings=[] if candidate is not None or kw == 0 else ["需求超出內建斷路器級距，須另選規格"],
        kind=kind,
        selected=candidate,
        length_m=length,
        insulation=insulation,
        ambient_c=ambient,
        loaded_conductors=loaded,
        drop_limit_pct=drop_limit,
        dt=dt,
        dp=dp,
        terminal_c=terminal,
        drop_basis="設計電流與R/X阻抗上界" if conservative_drop else "運轉電流及輸入PF",
        formula="三相 I=P輸入×1000/(√3×V×PF)；單相 I=P輸入×1000/(V×PF)。HP／PS先除馬達效率換成輸入kW；連續／馬達負載初估125%。",
        note="kW／W是電氣輸入；HP／PS是馬達軸輸出，除以效率換算。kVA須乘PF；A依電壓與相數換算。冷量RT不可直接當用電，請在帶入欄提供冰機COP或輸入kW。125%不能取代啟動、過載及短路保護。",
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
        friction_method = selected(data.get("friction_method", "實際風速＋水力直徑"),
                                   ("實際風速＋水力直徑", "Huebscher 等摩擦圓管"), "friction_method")
        roughness = number(data.get("roughness_mm", ROUGHNESS_MM["galvanized_duct"]), "roughness_mm", 0, 5)
        for result in (rectangle, round_duct):
            v, diameter = result["velocity_mps"], result["diameter_m"]
            vf, df = (result["equivalent_velocity_mps"], result["equivalent_diameter_m"]) if friction_method == "Huebscher 等摩擦圓管" else (v, diameter)
            reynolds = 1.2 * vf * df / 0.0000181
            f = (
                darcy_factor(reynolds, (roughness / 1000) / df)
                if df > 0 and vf > 0
                else 0.0
            )
            dynamic = 1.2 * v * v / 2
            friction = f * length / df * (1.2 * vf * vf / 2) if df > 0 else 0.0
            loss = friction + k * dynamic + equipment if cmh > 0 else 0.0
            result.update(
                loss_pa=loss,
                friction_pa=friction,
                k=k,
                equipment_pa=equipment if cmh > 0 else 0.0,
                pressure_margin_pa=pressure - loss if cmh > 0 else 0.0,
                budget_sufficient=pressure >= loss if cmh > 0 else None,
                friction_method=friction_method,
                friction_diameter_m=df,
                friction_velocity_mps=vf,
                friction_factor=f,
                roughness_mm=roughness,
                relative_roughness=(roughness / 1000 / df) if df else 0,
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
        k_sum=k if check_path == "1" else None,
        equipment_input_pa=equipment if check_path == "1" else None,
        roughness_mm=roughness if check_path == "1" else None,
        friction_method=friction_method if check_path == "1" else None,
        formula="A=風量/3600/風速；圓管D=√(4A/π)。路徑阻力=f×L/Dh×ρv²/2＋ΣK×ρv²/2＋設備壓降。",
        note="靜壓是可用於管路的壓力預算，不能單獨決定尺寸。未勾選已知路徑時不判定壓力是否足夠；圓管依2英吋級距選取。",
    )


def compressed_air(data):
    gas = selected(data["gas"], GAS_OPTIONS, "gas")
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
    z_ratio = number(data.get("z_ratio", "1"), "z_ratio", 0.1, 3)
    name = custom_name(data.get("gas_name"), "gas_name") if gas == CUSTOM_GAS and amount > 0 else None
    absolute = atm + gauge_kpa
    standard = amount if flow_basis == "標準流量" else amount * absolute / reference_p * (reference_t + 273.15) / (temperature + 273.15) / z_ratio
    actual = (
        standard
        * reference_p
        / absolute
        * (temperature + 273.15)
        / (reference_t + 273.15)
        * z_ratio
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
        custom_name=name,
        z_ratio=z_ratio,
        standard_lpm=standard,
        actual_lpm=actual,
        atmosphere_kpa=atm,
        absolute_kpa=absolute,
        gauge_kpa=gauge_kpa,
        minimum_id_mm=required,
        pipe=pipe,
        velocity_mps=speed,
        velocity_limit=velocity,
        temperature_c=temperature,
        reference_t=reference_t,
        reference_p=reference_p,
        formula="實際流量=標準流量×P標準/P絕對×T管內(K)/T標準(K)×Z管內/Z標準；D內=√(4Q實際/πv)。",
        note="壓力採管內表壓，另加所在地大氣壓。Z比1為理想氣體；僅適用單一氣相流速定寸，不核定材料相容、洩漏、點火或氣體安全；參考內徑需依實供管材核對，長管路另算壓降。",
    )


def lighting(data):
    mode = selected(data["mode"], ("估算照度", "反算燈數"), "mode")
    area_mode = selected(
        data["area_mode"], ("面積 m²", "面積 坪", "長×寬", "體積 m³"), "area_mode"
    )
    u_mode = selected(
        data.get("u_mode", "手動固定 U"),
        ("手動固定 U", "型錄 U＋室指數 K 檢核"),
        "u_mode",
    )
    if area_mode == "長×寬":
        length_m = number(data["length"], "length", 0.01, 10000)
        width_m = number(data["width"], "width", 0.01, 10000)
        area = length_m * width_m
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
    if u_mode == "型錄 U＋室指數 K 檢核":
        if area_mode != "長×寬":
            raise ValidationError("室指數需輸入實際長寬，請選長×寬面積模式。", "area_mode")
        mount_h = number(data.get("mount_h", "3"), "mount_h", 0.5, 100)
        work_h = number(data.get("work_h", "0.8"), "work_h", 0, 50)
        hm = mount_h - work_h
        if hm <= 0.1:
            raise ValidationError("燈具安裝高度必須高於工作面高度至少 0.1 m。", "mount_h")
        room_index = (length_m * width_m) / (hm * (length_m + width_m))
    else:
        mount_h = None
        work_h = None
        room_index = None
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
        u_mode=u_mode,
        room_index_k=room_index,
        mount_h_m=mount_h,
        work_h_m=work_h,
        utilization=utilization,
        maintenance=maintenance,
        illuminance_lux=illuminance,
        total_kw=qty * watts / 1000,
        target_lux=target,
        formula=(
            "室指數K=L×W/((H燈−H工)×(L+W))；U採手填型錄值；平均照度Lux=盞數×每盞流明lm×利用率U×維護係數M/面積m²；所需盞數向上取整。"
            if room_index is not None
            else "平均照度Lux=盞數×每盞流明lm×利用率U×維護係數M/面積m²；所需盞數向上取整。"
        ),
        note=(
            "室指數K只描述幾何；利用係數U須依燈具配光、室內反射率與原廠表格填入。未載入光度檔，本工具不宣稱重現DIALux；預設U仍為初估假設。"
            if room_index is not None
            else "Lux是空間照度，燈具光通量使用lm。體積須除以淨高換算面積；LED功率初估使用假設光效，不能代替型錄流明或照度均勻度模擬。"
        ),
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
        unit = selected(data["power_unit"], tuple(UNITS["冷熱功率"]), "power_unit")
        kw = convert_all("冷熱功率", number(data["power"], "power", 0, 10000000), unit)[
            "kW"
        ]
        thermal = water_heat("流量 LPM", kw, delta)
        lpm = thermal["lpm"]
    limit = number(data["velocity"], "velocity", 0.1, 10)
    pipe_options = ("自動依流速選型",) + tuple(row["size"] for row in HVAC_PIPES)
    pipe_choice = selected(data.get("pipe_size", "自動依流速選型"), pipe_options, "pipe_size")
    water_warnings = []
    if pipe_choice == "自動依流速選型":
        pipe = water_selection(lpm, limit)
    else:
        chosen = next(row for row in HVAC_PIPES if row["size"] == pipe_choice)
        if lpm == 0:
            pipe = {"lpm": 0, "id_mm": 0, "runs": 0, "velocity_mps": 0, "area_m2": 0, "size": "無需求"}
        else:
            d_mm = chosen["id_mm"]
            area_m2 = math.pi * (d_mm / 1000) ** 2 / 4
            vel_mps = (lpm / 60000) / area_m2
            ref = HVAC_PIPE_REFERENCES.get(pipe_choice)
            pipe = {
                "lpm": lpm,
                "id_mm": d_mm,
                "runs": 1,
                "velocity_mps": vel_mps,
                "area_m2": area_m2,
                "size": pipe_choice,
                **({"reference": dict(ref)} if ref else {}),
            }
            if vel_mps > limit + 1e-9:
                water_warnings.append(
                    f"指定管徑 {pipe_choice} 實際水速 {vel_mps:.2f} m/s 高於設計水速上限 {limit:g} m/s；請核對壓損或改選較大管徑。"
                )
    length = number(data.get("length", "30"), "length", 0, 100000)
    k_sum = number(data.get("k_sum", "4"), "k_sum", 0, 10000)
    equipment = number(data.get("equipment_pa", "0"), "equipment_pa", 0, 1e8)
    rough = number(data.get("roughness_mm", ROUGHNESS_MM["commercial_steel"]), "roughness_mm", 0, 5)
    diameter = pipe["id_mm"] / 1000
    speed = pipe["velocity_mps"]
    re = 1000 * speed * diameter / 0.001
    friction_factor = darcy_factor(re, rough / 1000 / diameter) if lpm else 0
    friction_rate = friction_factor / diameter * 1000 * speed ** 2 / 2 if lpm else 0
    friction = friction_rate * length
    local = k_sum * 1000 * speed ** 2 / 2
    equipment = equipment if lpm else 0
    loss = friction + local + equipment
    pressure = dict(friction_pa=friction, local_pa=local, equipment_pa=equipment,
                    loss_pa=loss, head_m=loss / (1000 * 9.80665),
                    friction_pa_m=friction_rate, friction_factor=friction_factor,
                    roughness_mm=rough, relative_roughness=rough / 1000 / diameter if diameter else 0,
                    length_m=length, k_sum=k_sum, equipment_included=equipment > 0)
    return dict(
        tool="water",
        thermal=thermal,
        pipe=pipe,
        flow_lpm=lpm,
        load_kw=thermal["kw"],
        pressure=pressure,
        velocity_limit=limit,
        pipe_size=pipe_choice,
        **({"warnings": water_warnings} if water_warnings else {}),
        formula=thermal["formula"],
        note="水物性採ρ=1000 kg/m³、cp=4.1868 kJ/(kg·K)、μ=0.001Pa·s；壓損按一條最不利路徑估算，並聯管分流。設備壓降為明填值；閉式循環不加樓高。",
    )


def cleanroom(data):
    """Plenum topology: room return crosses DCC; return + OA cross the FFUs."""
    area = number(data.get("area", "100"), "area", 0.01, 1e7)
    height = number(data.get("height", "3"), "height", 0.1, 100)
    volume = area * height
    ach = number(data.get("ach", "60"), "ach", 0, 2000)
    delta_p = number(data.get("delta_p", "15"), "delta_p", -200, 200)
    base_leak = number(data.get("base_leak_ach", "1"), "base_leak_ach", 0, 100)
    leakage = volume * base_leak * math.sqrt(delta_p / 15) if delta_p > 0 else 0.0
    persons = integer(data.get("persons", "10"), "persons", 0, 100000)
    exhaust = number(data.get("exhaust_cmh", "0"), "exhaust_cmh", 0, 1e8)
    required_oa = max(exhaust + leakage, persons * 30.0)
    manual_oa = number(data.get("oa_cmh", "0"), "oa_cmh", 0, 1e8)
    if manual_oa and manual_oa + 1e-8 < required_oa:
        raise ValidationError("指定外氣不可低於排氣、正壓洩漏及人員需求下限", "oa_cmh")
    oa = manual_oa or required_oa
    recirculation = volume * ach
    topology = selected(data.get("ffu_topology", "MAU入靜壓箱經FFU送風"),
                        ("獨立FFU循環（MAU直接入室）", "MAU入靜壓箱經FFU送風"), "ffu_topology")
    basis = (selected(data.get("ffu_airflow_basis", "室內基本循環（另加OA）"),
                      ("FFU總送風（已含OA）", "室內基本循環（另加OA）"), "ffu_airflow_basis")
             if topology == "MAU入靜壓箱經FFU送風" else "室內基本循環（另加OA）")
    add_oa = topology == "MAU入靜壓箱經FFU送風" and basis == "室內基本循環（另加OA）"
    ffu_total = recirculation + oa if add_oa else recirculation
    dcc = ffu_total - oa if topology == "MAU入靜壓箱經FFU送風" else recirculation
    unit_cmh = number(data.get("ffu_unit_cmh", "1000"), "ffu_unit_cmh", 1, 1e7)
    size = selected(data.get("ffu_size", "1200x600 (0.72m²)"), FFU_SIZES, "ffu_size")
    unit_kw = number(data.get("ffu_unit_kw", "0.18"), "ffu_unit_kw", 0, 100)
    count = math.ceil(ffu_total / unit_cmh) if ffu_total else 0
    coverage = count * FFU_SIZES[size] / area * 100
    limit = number(data.get("coverage_limit_pct", "85"), "coverage_limit_pct", 1, 100)
    warnings = ([f"FFU 天花板覆蓋率 {coverage:.1f}% 超過可安裝上限 {limit:g}%；需調整單台風量、配置或空間。"]
                if coverage > limit else [])
    if dcc < 0:
        warnings.append("FFU總送風小於OA，無法成立回風混合控制體；請增加循環需求或改用基本循環另加OA。")
    return dict(tool="cleanroom", area_m2=area, volume_m3=volume, height_m=height,
                ach=ach, persons=persons, delta_p=delta_p, base_leak_ach=base_leak,
                dcc_cmh=dcc, recirculation_cmh=recirculation,
                ffu_topology=topology, ffu_airflow_basis=basis,
                airflow_feasible=dcc >= 0,
                leakage_cmh=leakage, exhaust_cmh=exhaust,
                required_oa_cmh=required_oa, oa_cmh=oa,
                ffu_total_cmh=ffu_total, ffu_unit_cmh=unit_cmh, ffu_size=size,
                ffu_area_each=FFU_SIZES[size], ffu_count=count,
                ffu_unit_kw=unit_kw, ffu_fan_kw=count * unit_kw,
                coverage_ratio=coverage, coverage_limit_pct=limit,
                coverage_exceeded=coverage > limit, warnings=warnings,
                formula="獨立循環：FFU=DCC=基準風量；靜壓箱路徑：FFU總風=DCC回風＋OA，依所選ACH基準分配。OA=max(排氣＋洩漏,人數×30)；洩漏=體積×基準ACH×√(ΔP/15)，ΔP≤0時為0。",
                note="ACH依氣流路徑與風量基準解讀，不一律加OA。15Pa／1ACH、30CMH/人及85%是專案初估條件，需依實際洩漏、製程及安裝圖確認。負DCC回風量保留為不可行結果，不截成0。")


def heat_loads(data):
    area = number(data.get("area", "100"), "area", 0, 1e7)
    persons = integer(data.get("persons", "10"), "persons", 0, 100000)
    lighting = area * number(data.get("lighting_w_m2", "12"), "lighting_w_m2", 0, 10000) / 1000
    envelope = area * number(data.get("envelope_w_m2", "20"), "envelope_w_m2", 0, 10000) / 1000
    people_sensible = persons * number(data.get("people_sensible_w", "75"), "people_sensible_w", 0, 1000) / 1000
    people_latent = persons * number(data.get("people_latent_w", "55"), "people_latent_w", 0, 1000) / 1000
    equipment = number(data.get("equipment_kw", "20"), "equipment_kw", 0, 1e7)
    count = integer(data.get("ffu_count", "0"), "ffu_count", 0, 10000000)
    fan = count * number(data.get("ffu_unit_kw", "0.18"), "ffu_unit_kw", 0, 100)
    oa = number(data.get("oa_cmh", "0"), "oa_cmh", 0, 1e8)
    delta_h = number(data.get("oa_delta_h", "50"), "oa_delta_h", 0, 500)
    basis = selected(data.get("oa_load_basis", "外氣至室內基準"),
                     ("外氣至室內基準", "外氣至實際露點送風"), "oa_load_basis")
    room = lighting + envelope + people_sensible + equipment + fan
    mau = 1.2 * oa / 3600 * delta_h
    # Actual low-dew-point MAU enthalpy already contains the room latent removal.
    # Avoid silently charging the same moisture a second time to the chiller.
    latent_addition = people_latent if basis == "外氣至室內基準" else 0.0
    credit = (number(data.get("mau_room_sensible_kw", "0"), "mau_room_sensible_kw", 0, room)
              if basis == "外氣至實際露點送風" else 0.0)
    supply_delta_t = (number(data.get("mau_supply_delta_t", "0"), "mau_supply_delta_t", 0, 60)
                      if basis == "外氣至實際露點送風" else 0.0)
    credit_limit = 1.2 * oa / 3600 * 1.006 * supply_delta_t
    if basis == "外氣至實際露點送風" and not oa and people_latent:
        raise ValidationError("零外氣無法在MAU實際露點模式處理人員潛熱，請提供除濕外氣量或改用室內基準。", "oa_cmh")
    if credit and not oa:
        raise ValidationError("零外氣量不能提供MAU入室顯熱冷卻", "mau_room_sensible_kw")
    if credit > credit_limit + 1e-8:
        raise ValidationError("MAU顯熱抵扣超過所填外氣量及送風溫差的空氣側上限，請確認室內減送風溫差。", "mau_room_sensible_kw")
    dcc = room - credit
    total = dcc + mau + latent_addition
    scope = ("中性供風初估，未抵扣MAU顯熱" if basis == "外氣至室內基準" else
             "實際露點送風；MAU顯熱抵扣採明填值，零時為未抵扣冷量上界")
    return dict(tool="heat_loads", area_m2=area, persons=persons,
                q_lighting_kw=lighting, q_envelope_kw=envelope,
                q_people_sensible_kw=people_sensible, q_people_latent_kw=people_latent,
                q_equipment_kw=equipment, q_ffu_kw=fan, ffu_count=count,
                q_room_sensible_kw=room, q_mau_kw=mau, q_mau_rt=mau / US_RT_KW,
                q_dcc_kw=dcc, dcc_sensible_kw=dcc, load_basis=scope,
                mau_room_sensible_kw=credit,
                mau_supply_delta_t=supply_delta_t, mau_sensible_limit_kw=credit_limit,
                q_total_kw=total, q_total_rt=total / US_RT_KW,
                room_latent_added_kw=latent_addition, oa_load_basis=basis, oa_cmh=oa,
                formula="室內顯熱=照明＋圍護＋人員顯熱＋設備＋FFU；MAU=1.2×OA/3600×Δh；RT=總kW/3.516852842。",
                note="圍護20W/m²與外氣Δh=50為初估。中性供風以室內顯熱作DCC需求；實際低露點模式不重加人員潛熱，並扣明填MAU入室顯熱供冷。抵扣不得超過1.2×OA/3600×1.006×明填室內減送風溫差的保守上限；未填抵扣時是冷量上界。再熱及濕度可達性請用完整工作台。")


def pumps(data):
    unit = selected(data.get("flow_unit", "LPM"), ("LPM", "m³/h", "US GPM"), "flow_unit")
    flow = number(data.get("flow", "100"), "flow", 0, 1e7)
    lpm = flow * {"LPM": 1, "m³/h": 1000 / 60, "US GPM": 3.785411784}[unit]
    path_head = number(data.get("head_m", "20"), "head_m", 0, 10000)
    static = number(data.get("static_head_m", "0"), "static_head_m", 0, 10000)
    terminal = number(data.get("terminal_head_m", "0"), "terminal_head_m", 0, 10000)
    margin = number(data.get("head_margin_pct", "0"), "head_margin_pct", 0, 100)
    head = (path_head + terminal) * (1 + margin / 100) + static
    eta_pump = number(data.get("eta_pump", "0.70"), "eta_pump", 0.01, 1)
    eta_motor = number(data.get("eta_motor", "0.90"), "eta_motor", 0.01, 1)
    hydraulic = (lpm * 60 / 1000) * head * 9.81 / 3600
    shaft = hydraulic / eta_pump
    electric = shaft / eta_motor
    required_motor = shaft * 1.15
    recommended = next_standard(required_motor, STANDARD_MOTOR_KW)
    warning = ["所需馬達容量超過75kW參考表，須另選標準級距；未將最大規格冒充符合。"] if recommended is None else []
    return dict(tool="pumps", flow_lpm=lpm, flow_m3_h=lpm * 60 / 1000,
                head_m=head, eta_pump=eta_pump, eta_motor=eta_motor,
                path_head_m=path_head, static_head_m=static, terminal_head_m=terminal,
                head_margin_pct=margin,
                hydraulic_power_kw=hydraulic, shaft_power_kw=shaft,
                motor_input_kw=electric, required_motor_kw=required_motor,
                recommended_motor_kw=recommended, warnings=warning,
                formula="清水水功率kW=Q(m³/h)×H(m)×9.81/3600；軸功率=水功率/η泵；輸入電功率=軸功率/η馬達；銘牌以軸功率×1.15向上選級。",
                note="馬達銘牌為額定機械輸出kW，不能以輸入電功率選級。設計揚程須含最不利回路及設備壓差；閉式循環不直接加樓高，另核NPSH與泵曲線。")


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
    "cleanroom": cleanroom,
    "heat_loads": heat_loads,
    "pumps": pumps,
}


def calculate_tool(tool, data):
    if tool == "pipes":
        tool = "water"
    if tool not in ENGINES:
        raise ValidationError("沒有這個簡易工具", "tool")
    result = ENGINES[tool](data)
    # Preserve the active conditions with the successful result. Inactive
    # drafts must neither affect calculations nor appear as adopted inputs.
    from .simple_schema import TOOLS, active_field, defaults
    values = dict(defaults(tool), **data)
    keys = set()
    for row in TOOLS[tool]["fields"]:
        if active_field(tool, row["key"], values):
            keys.add(row["key"])
            if row["units"]:
                keys.add(row["units"][0])
    result["adopted_inputs"] = {key: values[key] for key in sorted(keys)}
    return result
