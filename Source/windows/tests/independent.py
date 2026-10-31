import math, re


def independent_checks(case, r):
    out = []

    def check(name, actual, expected, tol=1e-6):
        out.append(
            dict(
                name=name,
                actual=actual,
                expected=expected,
                passed=abs(actual - expected) <= tol * max(1, abs(expected)),
            )
        )

    if case["model"] == "main":
        i = case["project"]["inputs"]
        f = lambda k: float(i[k])
        s = r["summer"]
        m = s["mass"]
        for season in ["summer", "winter"]:
            ch = r[season]
            mch = ch["mass"]
            for tag in ["c1", "c2"]:
                c = ch[tag]
                hin = 1.006 * c["inlet"]["t"] + c["inlet"]["w"] * (
                    2501 + 1.86 * c["inlet"]["t"]
                )
                hout = 1.006 * c["outlet"]["t"] + c["outlet"]["w"] * (
                    2501 + 1.86 * c["outlet"]["t"]
                )
                check(
                    season + "_" + tag + "_air_energy", c["air_kw"], mch * (hin - hout)
                )
                check(
                    season + "_" + tag + "_condensate_mass",
                    c["condensate_kg_s"],
                    mch * (c["inlet"]["w"] - c["outlet"]["w"]),
                )
        check(
            "room_moisture_kg_h",
            m * (r["room"]["w"] - s["supply"]["w"]) * 3600,
            r["moisture"] * 3600,
        )
        text = a.report(r)
        printed = float(re.search(r"室內顯熱 ([\d.\-]+) kW", text)[1])
        check("printed_room_sensible", printed, r["qs"], 1e-5)
        for k, d in r["water"].items():
            if not d["lpm"]:
                continue
            check(
                k + "_area_flow_velocity",
                d["velocity_mps"],
                d["lpm"] / 60000 / d["runs"] / (math.pi * (d["id_mm"] / 1000) ** 2 / 4),
            )
            check(
                k + "_water_capacity",
                d["capacity_kw"],
                d["lpm"] / 60000 * f("water_rho") * f("water_cp") * d["delta_t"],
            )
        for k, d in r["gas"].items():
            if not d["standard_lpm"]:
                continue
            expected = (
                d["standard_lpm"]
                * (f("gas_std_kpa") * 1000 / d["pressure_abs_pa"])
                * ((f("gas_temp") + 273.15) / (f("gas_std_t") + 273.15))
                * f("gas_z_ratio")
            )
            check(k + "_gas_ideal_state", d["actual_lpm"], expected)
        for k, d in r["pressure"].items():
            if not d["flow_m3s"]:
                continue
            v = d["flow_m3s"] / d["runs"] / d["area_m2"]
            reynolds = d["rho"] * v * d["id_m"] / d["mu"]
            check(
                k + "_pressure_sum",
                d["total_pa"],
                d["friction_pa"] + d["local_pa"] + d["equipment_pa"] + d["static_pa"],
            )
            if d["mode"] == "Darcy 自動" and not 2300 <= reynolds < 4000:
                if reynolds < 2300:
                    friction = 64 / reynolds
                else:
                    x = 7.0
                    b = d["roughness_mm"] / 1000 / d["id_m"] / 3.7
                    for _ in range(40):
                        x -= (x + 2 * math.log10(b + 2.51 * x / reynolds)) / (
                            1
                            + 2
                            / math.log(10)
                            * (2.51 / reynolds)
                            / (b + 2.51 * x / reynolds)
                        )
                    friction = 1 / x**2
                check(
                    k + "_Colebrook_or_laminar",
                    d["friction_pa"],
                    friction * d["length_m"] / d["id_m"] * d["rho"] * v * v / 2,
                )
        for k, e in r["electric"].items():
            keys = (
                ["eq", "oven"] if k == "UP" else ["fan", "heat", "humid", "exh", "pump"]
            )
            kw = 0
            for name in keys:
                key = "e_" + k.lower() + "_" + name
                v = f(key)
                u = i["u_" + key]
                kw += (
                    v
                    if u == "kW"
                    else (
                        v * 0.745699871582 / f("e_eff")
                        if u == "HP"
                        else v
                        * math.sqrt(3)
                        * a.VOLTAGE_MAP[i["e_volt"]]
                        * f("e_pf")
                        / 1000
                    )
                )
            check(
                k + "_current",
                e["current_a"],
                kw * 1000 / (math.sqrt(3) * a.VOLTAGE_MAP[i["e_volt"]] * f("e_pf")),
            )
            selected = e["selected"]
            if kw:
                candidates = []
                ins = 90 if i["e_wire"].startswith("XLPE") else 60
                term = int(i["e_terminal_c"])
                for runs in range(1, 9):
                    for wire in a.WIRE_DB:
                        size = wire["size_mm2"]
                        if size < 3.5 or (runs > 1 and size < 50):
                            continue
                        base = wire["XLPE_A" if ins == 90 else "PVC_A"]
                        iz = runs * min(
                            base * e["dt"] * e["dp"],
                            wire["PVC_A"] if term < 90 else base,
                        )
                        limit = min(iz, {3.5: 20, 5.5: 30}.get(size, math.inf))
                        at = next(
                            (
                                x
                                for x in a.NFB_SIZES
                                if e["design_current_a"] - 1e-9 <= x <= limit + 1e-9
                            ),
                            None,
                        )
                        rr = (
                            0.017241
                            * (1 + 0.00393 * (min(ins, term) - 20))
                            * 1000
                            / size
                        )
                        drop = (
                            100
                            * math.sqrt(3)
                            * e["current_a"]
                            * (rr * f("e_pf") + 0.08 * math.sqrt(1 - f("e_pf") ** 2))
                            * f("e_length_m")
                            / 1000
                            / runs
                            / e["voltage"]
                        )
                        if at is not None and drop <= f("e_drop_limit_pct") + 1e-10:
                            candidates.append((runs, size))
                order = (
                    (lambda t: (t[0] * t[1], t[0], t[1]))
                    if i["e_sort"] == "最少總銅截面"
                    else (lambda t: t)
                )
                expected = min(candidates, key=order)
                check(k + "_rank_runs", selected["runs"], expected[0])
                check(k + "_rank_size", selected["size_mm2"], expected[1])
                check(
                    k + "_protection_inequalities",
                    float(
                        e["design_current_a"] <= selected["nfb_candidate_a"] + 1e-8
                        and selected["nfb_candidate_a"] <= selected["iz_a"] + 1e-8
                    ),
                    1,
                )
    else:
        for season in ["summer", "winter"]:
            s = r[season]
            m = s["mass"]
            steam = s.get("steam", dict(air_kw=0, kg_h=0))
            check(
                season + "_energy",
                m * (s["sa"]["h"] - s["oa"]["h"]),
                s["h1"]["air_kw"]
                + s["h2"]["air_kw"]
                - s["c1"]["air_kw"]
                - s["c2"]["air_kw"]
                + steam["air_kw"]
                + float(r["inputs"]["fan_air_kw"]),
            )
            check(
                season + "_moisture",
                m * (s["sa"]["w"] - s["oa"]["w"]) * 3600,
                s["evap_kg_h"]
                + steam["kg_h"]
                - sum(s[k]["condensate_kg_s"] for k in ["c1", "c2"]) * 3600,
            )
            if s["wash_on"]:
                check(
                    season + "_wetfilm_enthalpy", s["wash_in"]["h"], s["wash_out"]["h"]
                )
    return out
