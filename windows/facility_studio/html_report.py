"""Printable HTML5 reports with escaped values and an executive design overview."""

from html import escape
from pathlib import Path

from .reports import report, nm_report, executive_summary_html
from .schema import DEFAULTS, VERSION
from .i18n import localized_report, verbatim


REPORT_CSS = """
:root{color-scheme:light;--page:#F8FAFC;--card:#FFFFFF;--border:#CBD5E1;
--nav:#0F172A;--blue:#0284C7;--ink:#334155;--muted:#64748B;
--success:#16A34A;--success-bg:#DCFCE7;--warning:#D97706;--warning-bg:#FEF9C3;
--danger:#DC2626;--danger-bg:#FEE2E2}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);overflow-wrap:anywhere;
font:14px/1.7 "Microsoft JhengHei UI","Noto Sans TC",system-ui,sans-serif}
.report-header{background:var(--nav);color:#fff;padding:28px max(24px,calc((100vw - 1240px)/2))}
.report-header h1{margin:0 0 8px;font-size:28px;overflow-wrap:anywhere}.report-header p{margin:0;color:#CBD5E1}
main{max-width:1288px;margin:0 auto;padding:24px}h2{font-size:19px;color:var(--nav);margin:0 0 16px}
section{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:22px}
.executive-summary{border-top:4px solid var(--blue)}.kpi-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:16px 0 22px}
.kpi-card{border:1px solid var(--border);border-radius:10px;padding:14px 16px;min-width:0;background:var(--card)}
.kpi-label{font-size:12px;color:var(--muted);margin:0 0 8px}.kpi-value{font:700 20px/1.4 Consolas,"DejaVu Sans Mono",monospace;
color:var(--nav);margin:0 0 12px;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.badge{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11px;line-height:1.5;white-space:normal}
.success{color:#166534;background:var(--success-bg)}.warning{color:#92400E;background:var(--warning-bg)}
.danger{color:#991B1B;background:var(--danger-bg)}.neutral{color:var(--muted);background:#E2E8F0}
.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:0}th,td{text-align:left;padding:11px 12px;
border-bottom:1px solid #E2E8F0;vertical-align:top;overflow-wrap:anywhere}thead th{background:var(--nav);color:#fff;font-size:12px}
tbody tr:nth-child(even){background:var(--page)}tbody th{font-weight:600;width:20%}
.selection-table td{font-family:Consolas,"Microsoft JhengHei UI",monospace;font-variant-numeric:tabular-nums}
.selection-table td:last-child{font-family:"Microsoft JhengHei UI",sans-serif;width:11%}
.status{padding:12px 16px;border-left:4px solid var(--warning);background:var(--warning-bg);border-radius:4px;margin:0 0 20px}
.muted,small{color:var(--muted)}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.8 Consolas,"Microsoft JhengHei UI",monospace;
margin:0;font-variant-numeric:tabular-nums}.toolbar{max-width:1288px;margin:16px auto 0;padding:0 24px;text-align:right}
button{border:0;border-radius:7px;padding:10px 18px;background:var(--blue);color:white;font-weight:700;cursor:pointer}
button:hover{background:#0369A1}footer{padding:8px 24px 24px;text-align:center;color:var(--muted);font-size:12px}
@media(max-width:900px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.selection-table{min-width:720px}}
@media(max-width:560px){main{padding:12px}section{padding:14px}.kpi-grid{grid-template-columns:1fr}.report-header h1{font-size:23px}}
@media print{body{background:white;font-size:10pt}.toolbar{display:none}.report-header{background:white;color:#0F172A;padding:0 0 18px}
.report-header p{color:#64748B}main{max-width:none;padding:0}section{border-radius:0;padding:12px;margin-bottom:16px}
.kpi-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.kpi-card{padding:10px}.kpi-value{font-size:13pt}
thead{display:table-header-group}tr,.kpi-card{break-inside:avoid}.table-scroll{overflow:visible}.selection-table{min-width:0}
.appendix{break-before:page}th,td{padding:6px}footer{padding:0}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}
@page{size:A4 landscape;margin:14mm}}
"""


def _table(rows, headers=None):
    head = ("<thead><tr>" + "".join('<th scope="col">' + escape(str(v)) + "</th>" for v in headers)
            + "</tr></thead>") if headers else ""
    body = "".join("<tr>" + "".join("<td>" + escape(str(v)) + "</td>" for v in row) + "</tr>" for row in rows)
    return '<div class="table-scroll"><table>' + head + "<tbody>" + body + "</tbody></table></div>"


def _document(title, subtitle, content):
    return ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            + '<meta name="viewport" content="width=device-width, initial-scale=1"><title>' + title
            + '</title><style>' + REPORT_CSS + '</style></head><body><header class="report-header"><h1>' + title
            + '</h1><p>' + escape(subtitle) + '</p></header><div class="toolbar">'
            + '<button type="button" onclick="window.print()">列印／另存 PDF</button></div><main>'
            + content + '</main><footer>需求初估；設備額定與實際工況須由原廠及設計人員確認。</footer></body></html>')


@localized_report
def summary_html(result):
    """Existing full-project API; reject incomplete calculations before export."""
    appendix = report(result, language="zh-Hant").source
    r = result
    i = dict(r["project"]["inputs"])
    i.update({k: r["effective_inputs"][k] for k in r.get("inactive_fields", {})})
    conditions = [
        ("系統", i["sys_type"]),
        ("夏季外氣", f"{i['oa_t']} °C／{i['oa_rh']} %RH"),
        ("冬季外氣", f"{i['ow_t']} °C／{i['ow_rh']} %RH"),
        ("室內", f"{i['ra_t']} °C／{i['ra_rh']} %RH"),
        ("冬季邊界", i["winter_model"]),
        ("容量餘裕", i["sf"] + " %"),
    ]
    issues = [(x["status"], x["name"], x["detail"]) for x in r["quality"]["items"] if x["status"] != "通過"]
    provenance = [(k, verbatim(v["source"]), verbatim(v["note"])) for k, v in r["project"]["provenance"].items()
                  if v["source"] != "系統預設"]
    content = executive_summary_html(r)
    content += '<p class="status">' + escape(r["quality"]["status"]) + '｜需求初估，待原廠同工況及工程覆核</p>'
    content += '<section><h2>設計條件</h2>' + _table(conditions, ("項目", "設計條件")) + '</section>'
    content += '<section><h2>需確認的條件</h2>' + (_table(issues, ("狀態", "項目", "說明")) if issues else '<p>目前已知條件無新增異常。</p>') + '</section>'
    content += '<section class="appendix"><h2>計算附錄</h2><pre>' + escape(appendix) + '</pre></section>'
    content += '<section><h2>參數來源</h2>' + _table(provenance, ("欄位", "來源", "備註")) + '<p class="muted">專案雜湊：' + escape(str(r["hash"])) + '</p></section>'
    return _document(verbatim(i["project_name"], DEFAULTS["project_name"]), "V" + VERSION + "｜工程設計摘要", content)


@localized_report
def _quick_html(result):
    from .simple_reports import presentation

    pipeline = result.get("pipeline", result)
    content = executive_summary_html(result)
    content += '<p class="status">獨立工具／連動管線初估；尚未計算的設備不補造數值。</p>'
    stages = [result] if result.get("tool") else [value for value in pipeline.values() if isinstance(value, dict) and value.get("tool")]
    for stage in stages:
        cards, details = presentation(stage)
        content += '<section><h2>' + escape(str(stage["tool"])) + '</h2>' + _table(cards, ("項目", "計算結果"))
        content += '<p>' + '<br>'.join(escape(str(item)) for item in details) + '</p>'
        if stage.get("formula"):
            content += '<pre>' + escape(str(stage["formula"])) + '</pre>'
        if stage.get("note"):
            content += '<p class="muted">' + escape(str(stage["note"])) + '</p>'
        content += '</section>'
    warnings = pipeline.get("warnings", [])
    if warnings:
        content += '<section><h2>需確認的條件</h2><p>' + '<br>'.join(escape(str(item)) for item in warnings) + '</p></section>'
    return _document("工程設計摘要", "V" + VERSION + "｜跨模組計算", content)


@localized_report
def _ahu_html(result):
    # A single MAU calculation is not an entire cleanroom facility calculation.
    from .reports import nm_summary_html
    from .ahu_schema import NM_DEFAULTS

    text = nm_report(result, language="zh-Hant").source
    content = nm_summary_html(result) + '<section class="appendix"><h2>計算附錄</h2><pre>' + escape(text) + '</pre></section>'
    return _document(verbatim(result["inputs"]["name"], NM_DEFAULTS["name"]), "V" + VERSION + "｜MAU 單機需求", content)


def html_report(result, *, language=None):
    """Create an HTML5 report for a full project, MAU, tool or quick pipeline."""
    if isinstance(result, dict) and "project" in result:
        return summary_html(result, language=language)
    if isinstance(result, dict) and "inputs" in result and "summer" in result and "winter" in result:
        return _ahu_html(result, language=language)
    if not isinstance(result, dict):
        from .errors import InputError
        raise InputError("設計總覽需要計算結果。", code="incomplete_result")
    return _quick_html(result, language=language)


def export_html_report(result, path, *, language=None):
    """Write a complete report atomically and return its absolute output path."""
    from .utils import atomic_text

    destination = Path(path).expanduser().resolve()
    document = html_report(result, language=language)
    atomic_text(destination, str(document))
    return destination
