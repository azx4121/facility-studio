"""Explicit short-form facility calculations; unknown ratings never become approvals."""
import math
from fractions import Fraction

from .errors import ValidationError
from .utils import number, darcy_factor, dewpoint, state_trh
from .quick_tools import convert_all

ASHRAE = "https://handbook.ashrae.org/handbooks/F17/SI/F17_Ch23/f17_ch23_si.aspx"
LEYBOLD = "https://www.leybold.com/en-uk/knowledge/vacuum-fundamentals/fundamental-physics-of-vacuum/how-to-calculate-vacuum-conductance"
MOI = "https://ws.moi.gov.tw/Download.ashx?u=LzAwMS9VcGxvYWQvT2xkRmlsZV9BYnJpX0dvdi9yZXNlYXJjaC8yNzIxLzE1MjEwMTY1NTJ4NmVkYmEucGRm"
GF = "https://www.gfps.com/en-ca/applications/specialty-waste-wastewater-treatment.html"
MATERIALS = {
    "SUS316L": (None, "金屬；耐蝕、焊接、鈍化及潔淨度須依介質確認", GF),
    "UPVC／PVC-U": ((0, 60), "GF PVC-U 參考；升溫必須依產品壓溫曲線降額", "https://www.gfps.com/content/dam/gfps/com/specifications/en/gfps-system-specification-pvcu-metric-en.pdf"),
    "PVC": (None, "須分辨硬質 PVC-U 與含塑化劑軟管，不能只依 PVC 名稱判定", "https://assets.thermofisher.com/TFS-Assets/LPD/Product-Guides/Nalgene-Tubing-Selection-Guide-EN.pdf"),
    "CPVC／PVC-C": (None, "CPVC 管材、接著劑、密封件及濃度／溫度須共同查表", GF),
    "PFA": (None, "高純度／化學管路候選；實際管壁、滲透及壓溫須依型錄", "https://www.daikinchemicals.com/solutions/industries/tubes-and-hoses/industrial-tubing.html"),
    "PVDF": ((-20, 140), "GF SYGEF 材料溫區參考，不是任何壓力均可使用", "https://www.gfps.com/en-in/products-solutions/systems/sygef-standard.html"),
    "PU": (None, "聚酯／聚醚 PU 不可混用；部分聚酯 PU 不建議用於水溶液", "https://www.fishersci.com/shop/products/nalgene-280-polyurethane-tubing/p-4526140"),
    "PP": (None, "須明確 PP-H／PP-R 等級及產品壓溫、焊接與介質相容性", GF),
    "PPS": (None, "樹脂耐化資料不等於承壓管認證；須指定管材牌號與壓溫資料", "https://www.celanese.com/en/products/fortron-polyphenylene-sulfide"),
}
LIQUIDS = ("清水", "UPW／DI／RO", "乙二醇水溶液", "丙二醇水溶液", "乙醇", "甲醇", "丙酮",
           "IPA 異丙醇", "污水／混合廢液", "鹽酸", "硫酸", "氫氟酸", "氫氧化鈉", "過氧化氫", "自訂液體")
OD_SERIES = (16, 20, 25, 32, 40, 50, 63, 75, 90, 110, 125, 140, 160, 180, 200, 225, 250, 280, 315, 355, 400)


def n(data, key, default, low=None, high=None):
    return number(data.get(key, default), key, low, high)


def choice(data, key, default, options):
    value = data.get(key, default)
    if value not in options:
        raise ValidationError("請選擇有效選項", key)
    return value


def inches(mm):
    return str(Fraction(mm / 25.4).limit_denominator(16)) + '"'


def insulation(data, od_mm, fluid_t):
    """Radial steady conduction, explicit external surface coefficient, no hidden ΔT table."""
    if choice(data, "insulate", "0", ("0", "1")) != "1":
        return None
    ambient = n(data, "ambient_t", "30", -30, 65)
    rh = n(data, "ambient_rh", "75", 0, 100)
    k = n(data, "insulation_k", ".036", .01, .2)
    h = n(data, "external_h", "8", .1, 100)
    margin = n(data, "dew_margin", "1", 0, 10)
    qmax = n(data, "heat_limit", "20", .01, 10000)
    minimum = n(data, "contract_insulation_mm", "0", 0, 200)
    dp = dewpoint(state_trh(ambient, rh, 101.325)["w"], 101.325) if rh else -100
    r1 = od_mm / 2000

    def at(thick):
        r2 = r1 + thick / 1000
        resistance = math.log(r2 / r1) / (2 * math.pi * k) + 1 / (2 * math.pi * r2 * h)
        q = (fluid_t - ambient) / resistance
        surface = ambient + q / (2 * math.pi * r2 * h)
        return q, surface

    cold = fluid_t < ambient
    chosen = None
    for mm in (0, 6, 9, 12.7, 19.05, 25.4, 38.1, 50.8, 63.5, 76.2, 101.6, 127, 152.4, 200):
        q, surface = at(mm)
        if mm >= minimum and abs(q) <= qmax and (not cold or surface >= dp + margin):
            chosen = dict(thickness_mm=mm, heat_w_m=q, surface_t_c=surface)
            break
    return dict(chosen or {}, feasible=chosen is not None, dewpoint_c=dp,
                designation=(f"外徑 {od_mm:g} mm × {inches(chosen['thickness_mm'])}t" if chosen else "超出 200 mm 搜尋範圍／無可行保溫厚度"),
                source=ASHRAE, basis="防結露＋明填每米熱損／得熱上限＋明填契約最小厚度；非宣稱現行法規最小厚度",
                warnings=["以管外表面等於液體溫度保守估算；外表面熱傳係數須含對流與輻射；另須防潮層、接縫、支架熱橋與材料額定溫度確認。"])


def liquid(data):
    from CoolProp.CoolProp import PropsSI, PhaseSI
    from .engineering_backends import liquid_water
    name = choice(data, "liquid", "清水", LIQUIDS)
    material = choice(data, "material", "UPVC／PVC-U", MATERIALS)
    flow = convert_all("水量", n(data, "flow", "100", 0, 1e7), data.get("flow_unit", "LPM"))["LPM"]
    t = n(data, "liquid_t", "20", -30, 150)
    pressure = n(data, "liquid_p", "300", 1, 10000)
    concentration = n(data, "concentration", "20", 0, 100) if name not in ("清水", "UPW／DI／RO", "乙醇", "甲醇", "丙酮") else 0
    mode = choice(data, "properties", "依介質模型", ("依介質模型", "供應商物性"))
    warnings = []
    if mode == "供應商物性" or name in ("丙酮", "IPA 異丙醇", "污水／混合廢液", "鹽酸", "硫酸", "氫氟酸", "氫氧化鈉", "過氧化氫", "自訂液體"):
        rho = n(data, "liquid_rho", "", 1, 5000)
        mu = n(data, "liquid_mu", "", 1e-7, 100)
        cp = n(data, "liquid_cp", "", .01, 20)
        source = str(data.get("property_reference", "")).strip()
        if not source:
            raise ValidationError("化學液體與混合廢液須填物性來源及適用溫度／濃度，不能沿用水物性。", "property_reference")
    else:
        try:
            if name in ("清水", "UPW／DI／RO"):
                props = liquid_water(t, pressure)
                rho, cp, mu = props["rho"], props["cp"], props["mu"]
                source = props["source"]
            else:
                fluid = {"乙二醇水溶液": f"INCOMP::MEG-{concentration:g}%", "丙二醇水溶液": f"INCOMP::MPG-{concentration:g}%",
                         "乙醇": "Ethanol", "甲醇": "Methanol", "丙酮": "Acetone"}[name]
                if not fluid.startswith("INCOMP") and PhaseSI("T", t + 273.15, "P", pressure * 1000, fluid) != "liquid":
                    raise ValueError("所填溫壓不是液相")
                rho, cp, mu = [PropsSI(key, "T", t + 273.15, "P", pressure * 1000, fluid) for key in ("D", "C", "V")]
                cp /= 1000
                source = "CoolProp " + fluid
        except ValueError as error:
            raise ValidationError("液體物性模型不適用此溫壓／濃度：" + str(error), "liquid_t") from None
    if not all(math.isfinite(x) and x > 0 for x in (rho, cp, mu)):
        raise ValidationError("物性必須為有限正值", "properties")
    geometry = choice(data, "geometry", "外徑系列＋指定 SDR", ("外徑系列＋指定 SDR", "指定外徑及管壁"))
    vlimit = n(data, "velocity", "1.5", .01, 30)
    if geometry == "指定外徑及管壁":
        od = n(data, "outer_mm", "25", 1, 2000)
        wall = n(data, "wall_mm", "2", .05, 500)
    else:
        sdr = n(data, "sdr", "17", 3, 100)
        od = OD_SERIES[-1]
        for candidate in OD_SERIES:
            bore = candidate * (1 - 2 / sdr)
            od = candidate
            if flow / 60000 / (math.pi * (bore / 1000) ** 2 / 4) <= vlimit:
                break
        wall = od / sdr
        warnings.append("外徑系列與 SDR 僅作幾何初估；須按指定材料型錄的最小管壁、實際內徑及壓溫曲線確認，不能當成採購或承壓認證。")
    bore = od - 2 * wall
    if bore <= 0:
        raise ValidationError("管壁須小於外徑一半", "wall_mm")
    v = flow / 60000 / (math.pi * (bore / 1000) ** 2 / 4)
    rough = n(data, "roughness_mm", ".0015", 0, 5)
    re = rho * v * bore / 1000 / mu
    f = darcy_factor(re, rough / bore) if flow else 0
    rate = f / (bore / 1000) * rho * v * v / 2
    length = n(data, "length", "30", 0, 1e5)
    ksum = n(data, "k_sum", "4", 0, 1e5)
    friction_limit = n(data, "friction_limit", "400", .01, 1e6)
    drop = rate * length + ksum * rho * v * v / 2
    if v > vlimit:
        warnings.append(f"實際流速 {v:.3f} m/s 超過本案上限 {vlimit:g} m/s；須放大管徑或調整工況。")
    if rate > friction_limit:
        warnings.append(f"單位壓損 {rate:.2f} Pa/m 超過本案警戒 {friction_limit:g} Pa/m。")
    limits, material_note, url = MATERIALS[material]
    if limits and not limits[0] <= t <= limits[1]:
        warnings.append("液體溫度超出所引用材料產品的參考溫區。")
    warnings.append(material_note)
    if name == "UPW／DI／RO":
        warnings.append("水力物性可用純水模型；高純度適用性仍須材料溶出、表面、焊接及水質驗收，不能由流速判定。")
    if name == "污水／混合廢液":
        warnings.append("本模式限加壓、滿管、均質牛頓流體；含固體／非牛頓廢液與重力排水不得採用此定寸結果。")
    warnings.append("材料相容性及承壓待原廠按介質、濃度、溫度、管壁與密封件確認，未自動判為相容。")
    ins = insulation(data, od, t)
    if ins and not ins["feasible"]:
        warnings.append("保溫條件不可達，不能採用厚度。")
    return dict(tool="liquid", liquid=name, material=material, flow_lpm=flow, temperature_c=t,
                rho=rho, cp=cp, mu=mu, properties_source=source, material_source=url,
                outer_mm=od, wall_mm=wall, inner_mm=bore, velocity_mps=v, reynolds=re,
                friction_pa_m=rate, loss_pa=drop, hydraulic_kw=flow / 60000 * drop / 1000,
                insulation=ins, warnings=warnings, material_approved=False,
                formula="內徑＝外徑−2×管壁；v=Q/A；ΔP=(fL/D+ΣK)ρv²/2。",
                note="流量、管徑、水力及保溫在同一頁完成。數值模型未涵蓋腐蝕、磨蝕、結垢、氣液兩相、泵汽蝕與管材壓溫額定。")


def vacuum(data):
    unit_flow = choice(data, "flow_unit", "SLPM", ("SLPM", "SCFM", "Sm³/h"))
    std = n(data, "flow", "100", 0, 1e8) * {"SLPM": 1, "SCFM": 28.316846592, "Sm³/h": 1000/60}[unit_flow]
    unit = choice(data, "vacuum_unit", "Torr(abs)", ("Torr(abs)", "Pa(abs)", "kPa(abs)", "mbar(abs)"))
    p = n(data, "vacuum_p", "150", 1e-9, 1e9) * {"Torr(abs)": 101325/760, "Pa(abs)": 1, "kPa(abs)": 1000, "mbar(abs)": 100}[unit]
    atmosphere = n(data, "atmosphere", "101.325", 60, 120) * 1000
    if p >= atmosphere:
        raise ValidationError("PV 必須填低於所在地大氣壓的絕對壓力，不可填表壓或真空度百分比。", "vacuum_p")
    t = n(data, "temperature", "20", -30, 150) + 273.15
    std_t = n(data, "standard_t", "0", -30, 50) + 273.15
    std_p = n(data, "standard_p", "101.325", 1, 200) * 1000
    limit = n(data, "velocity", "15", .1, 100)
    actual = std * std_p / p * t / std_t
    mode = choice(data, "diameter_mode", "依流速初估", ("依流速初估", "指定內徑"))
    d = n(data, "inner_mm", "50", 1, 3000) / 1000 if mode == "指定內徑" else max(.001, math.ceil(math.sqrt(4 * actual / 60000 / math.pi / limit) * 1000 / 5) * 5 / 1000)
    if d > 3:
        raise ValidationError("依流速反算管徑超過 3000 mm，已超出初估範圍；請核對標準流量與真空絕壓，或指定實際內徑作抽速校核。", "vacuum_p")
    v = actual / 60000 / (math.pi * d * d / 4)
    pump = n(data, "pump_l_s", "100", .001, 1e9)
    length = n(data, "length", "10", .01, 1e5)
    # Use the existing product's pressure/standard-flow sizing; molecular
    # conductance is separately bounded to long straight air tubes near 20 C.
    product = d * 100 * (p / 100)  # cm*mbar
    conductance = effective = None
    warnings = ["標準流量折算與流速僅為定寸初估；不是泵浦抽速或管網壓降認證。"]
    if product < .01 and length / d >= 10:
        conductance = 12.1 * (d * 100) ** 3 / (length * 100) * math.sqrt(t / 293.15)
        effective = 1 / (1 / pump + 1 / conductance)
        regime = "分子流長直圓管（空氣）"
        if std > 0:
            warnings.append("分子流中平均漂移流速不可用來核准管徑；應以導通率及有效抽速重新選管。")
    elif product > .6:
        regime = "黏滯流；需沿程壓力及層流／紊流校核"
    else:
        regime = "過渡流或短管；須使用適用導通率模型"
    if effective and std / 60000 * std_p / p * t / std_t * 1000 > effective:
        warnings.append("指定氣載所需實際抽速大於管路有效抽速，無法維持所填工作壓力。")
    if v > limit:
        warnings.append(f"PV 實際流速 {v:.2f} m/s 超過本案上限 {limit:g} m/s。")
    return dict(tool="vacuum", pressure_pa=p, standard_lpm=std, actual_lpm=actual,
                inner_mm=d*1000, velocity_mps=v, regime=regime, conductance_l_s=conductance,
                effective_speed_l_s=effective, pump_speed_l_s=pump, warnings=warnings,
                formula="Qactual=Qstd×Pstd/Pabs×T/Tstd；分子流長直圓管 C=12.1d³/L（cm、L/s、空氣20°C）；1/Seff=1/Sp+1/C。",
                note="PV 在簡易工具內完成，不切換工作台。導通率只限明列適用條件；特氣／混合氣、管件與真空外壓強度另核。", source=LEYBOLD)


def duct_sheet(long_side_mm):
    if long_side_mm <= 0:
        return dict(thickness_mm=0, gauge="無需求", source=MOI)
    mm, gauge = next((t, g) for bound, t, g in ((460, .6, 24), (1220, .8, 22), (1830, 1., 20), (float('inf'), 1.2, 18)) if long_side_mm <= bound)
    return dict(thickness_mm=mm, gauge=f"#{gauge}", label=f"{mm:g} mm／#{gauge}", source=MOI,
                status="參考選用，非施工核准",
                note="內政部106年排煙研究表4.2／4.3中壓參考；須連同補強間距、接縫、正負壓與契約SMACNA表確認。不能套用到腐蝕、排煙耐火或任意圓管構造。")
