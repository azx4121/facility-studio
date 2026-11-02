"""Physical C2 rating used by the existing AHU engine, not a model vote."""
import math
import warnings


def rate_coil(inputs, inlet, m_da):
    # python-hvac installs a module-level warning filter on import. Confine
    # that side effect, then record warnings for this calculation explicitly.
    with warnings.catch_warnings():
        from hvac.fluids import HumidAir, Fluid
        from hvac.heat_exchanger.recuperator.fintube.continuous_fin.air_to_water import (
            PlainFinTubeAirToWaterCounterFlowHeatExchanger as Coil,
        )
    from .engineering_backends import registry
    q = registry().Quantity
    n = lambda key: float(inputs[key])
    if not math.isfinite(m_da) or m_da <= 0:
        raise ValueError("盤管乾空氣質量流率須為正有限數值。")
    for key in ("coil_rows", "coil_circuits"):
        if not n(key).is_integer():
            raise ValueError("管排數與並聯水路數須為整數。")
    if not n("coil_di") < n("coil_do") < min(n("coil_pitch_trv"), n("coil_pitch_lon")):
        raise ValueError("須符合內徑＜外徑＜橫向／縱向管中心距。")
    if n("coil_fin_t") >= n("coil_fin_pitch"):
        raise ValueError("翅片厚度必須小於間距。")
    tubes_per_row = int(n("coil_height") / n("coil_pitch_trv"))
    if tubes_per_row < 1 or n("coil_circuits") > tubes_per_row * n("coil_rows"):
        raise ValueError("盤管高度或並聯水路數與可容納管數不相容。")
    if inlet["t"] <= n("c2_in"):
        raise ValueError("入口水溫不低於入口空氣；此冷卻盤管模型不適用。")
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        coil = Coil(
            q(n("coil_width"), "mm"), q(n("coil_height"), "mm"), int(n("coil_rows")),
            q(n("coil_pitch_trv"), "mm"), q(n("coil_pitch_lon"), "mm"),
            q(n("coil_do"), "mm"), q(n("coil_di"), "mm"), q(n("coil_fin_t"), "mm"),
            q(1 / n("coil_fin_pitch"), "1/mm"), num_circuits=int(n("coil_circuits")),
        )
        air = HumidAir(Tdb=q(inlet["t"], "degC"), W=q(inlet["w"], "kg/kg"),
                       P=q(n("p"), "kPa"))
        water = Fluid("Water")(T=q(n("c2_in"), "degC"), P=q(n("coil_water_abs_kpa"), "kPa"))
        water_mass = q(n("coil_water_lpm"), "liter/minute") * water.rho
        coil.set_operating_conditions(air, water, q(m_da, "kg/s"), water_mass)
        rated = coil.rate(i_max=50, tol=q(.00001, "K"))
        kw = float(rated["Q_dot"].to("kW").magnitude)
        out = rated["air_out"]
        air_kw = float(((air.h - out.h) * q(m_da, "kg/s")).to("kW").magnitude)
        result = dict(
            capacity_kw=kw, air_kw=air_kw,
            air_balance_residual_kw=air_kw - kw,
            outlet_t=float(out.Tdb.to("degC").magnitude),
            outlet_w=float(out.W.to("kg/kg").magnitude),
            water_outlet_t=float(rated["water_out"].T.to("degC").magnitude),
            air_dp_pa=float(rated["dP_air"].to("Pa").magnitude),
            water_dp_pa=float(rated["dP_water"].to("Pa").magnitude),
            surface={"wet": "全濕", "dry": "全乾", "partially_wet": "部分濕（乾／濕模型近似）"}[rated["air_surface_condition"]],
            warnings=sorted({str(w.message) for w in captured
                             if "surface tension is only defined within the two-phase region" not in str(w.message)}),
            informational=("單相純水不取表面張力；此盤管模型未使用水的表面張力。"
                           if any("surface tension is only defined within the two-phase region" in str(w.message) for w in captured) else ""),
            method="python-hvac 平直翅片管逆流 ε-NTU；CoolProp 物性；非原廠選型認證",
        )
    if not all(math.isfinite(v) for v in result.values() if isinstance(v, (int, float))):
        raise ValueError("盤管模型產生非有限數值。")
    if kw <= 0 or abs(result["air_balance_residual_kw"]) > max(.001, abs(kw) * .001):
        raise ValueError("盤管數值熱平衡未通過，不能採用模型結果。")
    return result
