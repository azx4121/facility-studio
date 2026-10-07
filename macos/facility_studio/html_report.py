"""Escaped, printable design summary with a separate calculation appendix."""

from html import escape
from .reports import report
from .schema import DEFAULTS
from .i18n import localized_report, verbatim


@localized_report
def summary_html(result):
    r = result
    i = dict(r["project"]["inputs"])
    i.update({k: r["effective_inputs"][k] for k in r.get("inactive_fields", {})})

    def table(rows):
        return (
            "<table>"
            + "".join(
                "<tr>"
                + "".join("<td>" + escape(str(v)) + "</td>" for v in row)
                + "</tr>"
                for row in rows
            )
            + "</table>"
        )

    conditions = [
        ("系統", i["sys_type"]),
        ("夏季外氣", i["oa_t"] + " °C／" + i["oa_rh"] + " %RH"),
        ("冬季外氣", i["ow_t"] + " °C／" + i["ow_rh"] + " %RH"),
        ("室內", i["ra_t"] + " °C／" + i["ra_rh"] + " %RH"),
        ("冬季邊界", i["winter_model"]),
        ("容量餘裕", i["sf"] + " %"),
    ]
    metrics = [
        ("室內顯熱", f"{r['qs']:.2f} kW"),
        ("室內產濕", f"{r['moisture']*3600:.2f} kg/h"),
        ("補償外氣", f"{r['oa_room_cmh']:.1f} CMH（室內基準）"),
        ("處理風量", f"{r['supply_room_cmh']:.1f} CMH（室內基準）"),
        (
            "夏季兩段水側冷量",
            f"{sum(r['summer'][k]['water_kw'] for k in ['c1','c2']):.2f} kW（未加餘裕）",
        ),
        ("DCC 設計顯熱", f"{r.get('dcc_design_kw',r['dcc_kw']):.2f} kW（未加餘裕）"),
    ]
    issues = [
        (x["status"], x["name"], x["detail"])
        for x in r["quality"]["items"]
        if x["status"] != "通過"
    ]
    return (
        '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>設計摘要</title><style>body{font:15px/1.65 system-ui,sans-serif;color:#163047;max-width:1050px;margin:32px auto;padding:20px}h1{font-size:28px}h2{font-size:19px;border-bottom:2px solid #188b87}table{border-collapse:collapse;width:100%;margin:12px 0}td{border-bottom:1px solid #dde5eb;padding:7px;vertical-align:top}td:first-child{width:26%;font-weight:600}pre{white-space:pre-wrap;font:12px/1.7 monospace}.status{background:#edf5f7;padding:12px}small{color:#526677}@media print{body{margin:0;padding:0;font-size:11pt}.appendix{break-before:page}tr{break-inside:avoid}button{display:none}@page{size:A4;margin:17mm}}</style><button onclick="window.print()">列印／另存 PDF</button><h1>'
        + verbatim(i["project_name"], DEFAULTS["project_name"])
        + '</h1><p class="status">V5.5.5｜'
        + escape(r["quality"]["status"])
        + "｜需求初估，待原廠同工況及工程覆核</p><h2>設計條件</h2>"
        + table(conditions)
        + "<h2>容量與分工</h2>"
        + table(metrics)
        + "<h2>主要公式</h2><p>Qs = m_da(1.006 + 1.86ws)(Tr − Ts) + QDCC<br>產濕 G = 3600 m_da(wr − ws)<br>盤管空氣側 Q = m_da(hin − hout)；水側扣除凝結水液態焓<br>LPM = 60000Q / (ρcpΔT)</p><h2>需確認的條件</h2>"
        + table(issues)
        + "<small>專案雜湊："
        + escape(r["hash"])
        + '</small><section class="appendix"><h2>計算附錄</h2><pre>'
        + escape(report(r, language="zh-Hant").source)
        + "</pre><h2>參數來源</h2>"
        + table(
            [
                (k, v["source"], v["note"])
                for k, v in r["project"]["provenance"].items()
                if v["source"] != "系統預設"
            ]
        )
        + "</section></html>"
    )
