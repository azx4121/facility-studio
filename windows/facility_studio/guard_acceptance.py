"""Frozen GUI acceptance of invalid-input, warning and export boundaries."""
from pathlib import Path
from tempfile import TemporaryDirectory


def run(root, app, check):
    from . import ahu_desktop, desktop
    from .industrial_theme import Theme
    from .quality import assessment
    from .schema import FIELDS, default_project
    from .simple_reports import tool_report
    from .simple_schema import defaults

    fields = [('electrical', 'power'), ('duct', 'flow'), ('gas', 'flow'),
              ('lighting', 'area'), ('water', 'flow'), ('air', 'temperature'),
              ('units', 'value'), ('cleanroom', 'room_rh'), ('heat_loads', 'area'),
              ('pumps', 'flow'), ('liquid', 'flow'), ('vacuum', 'vacuum_p')]
    with TemporaryDirectory(prefix='facility-guard-') as temporary:
        folder = Path(temporary)
        for tool, key in fields:
            app.show_tool(tool)
            page = app.active_page()
            page.reset()
            page.calculate()
            check(tool + ' valid baseline', page.result is not None)
            page.variables[key].set('nan')
            target = folder / (tool + '.txt')
            check(tool + ' invalid input blocks frozen export',
                  page.result is None and not app.export_result(target) and not target.exists())
            page.variables[key].set(defaults(tool)[key])
            page.calculate()
            check(tool + ' corrected input recovers', page.result is not None)
        app.show_tool('gas')
        page = app.active_page()
        for gas, risk, tone in [('WF6', True, 'danger'), ('AsH3', None, 'warning')]:
            page.variables['gas'].set(gas)
            page.variables['velocity'].set('6')
            page.calculate()
            check(gas + ' phase warning reaches UI and report',
                  page.result is not None and page.result['liquefaction_risk'] is risk
                  and page.banner.label.cget('background') == Theme.TONES[tone][1]
                  and all(w in tool_report(page.result, page.data()) for w in page.result['warnings']))
        page.variables['gas'].set('N2')
        page.variables['velocity'].set('100')
        page.calculate()
        check('custom gas velocity triggers reference warning',
              any('流速' in w for w in page.result['warnings'])
              and page.banner.label.cget('background') == Theme.TONES['warning'][1])
        app.show_tool('duct')
        page = app.active_page()
        for key, value in {'check_path': '1', 'pressure': '1', 'length': '100', 'equipment': '100'}.items():
            page.variables[key].set(value)
        page.calculate()
        check('pressure failure has banner priority', '不足' in page.banner.label.cget('text')
              and page.banner.label.cget('background') == Theme.TONES['danger'][1])
        page.reset()
        work_root = desktop.tk.Toplevel(root)
        main = desktop.DesktopApp(work_root)
        ahu = ahu_desktop.AHUWindow(root)
        original_dialog = desktop.filedialog.asksaveasfilename
        original_warning = desktop.messagebox.showwarning
        messages = []
        try:
            desktop.messagebox.showwarning = lambda *a, **kw: messages.append(a)
            for kind, window, actions in [('main', main, ('export', 'export_audit', 'export_html', 'save_plot')),
                                           ('ahu', ahu, ('export', 'save_plot'))]:
                for action in actions:
                    main.recalculate() if kind == 'main' else ahu.calculate()
                    check(kind + ' export baseline ' + action, window.result is not None)
                    target = folder / (kind + '-' + action)
                    def dialog(kind=kind, target=target, **kwargs):
                        var = main.variables['project_name'] if kind == 'main' else ahu.vars['name']
                        var.set(var.get() + '*')
                        return str(target)
                    desktop.filedialog.asksaveasfilename = dialog
                    messages.clear()
                    getattr(window, action)()
                    check(kind + ' changed snapshot blocks ' + action,
                          not target.exists() and any('條件已變更' in str(m) for m in messages))
            ahu.calculate()
            ahu.result['quality'] = assessment([{'name': 'synthetic', 'detail': 'pending review', 'status': '待後續'}])
            ahu.refresh_link_status()
            check('deferred AHU review stays amber', ahu.banner.label.cget('background') == Theme.TONES['warning'][1])
            main.variables['sys_type'].set(FIELDS['sys_type']['options'][0])
            main.variables['ffu_cmh'].set('nan')
            main.recalculate()
            check('invalid active workbench field blocks result', main.result is None and main.export_button.instate(['disabled']))
            main.variables['ffu_cmh'].set(default_project()['inputs']['ffu_cmh'])
            main.recalculate()
            check('workbench correction restores result', main.result is not None)
        finally:
            desktop.filedialog.asksaveasfilename = original_dialog
            desktop.messagebox.showwarning = original_warning
            ahu.win.destroy()
            work_root.destroy()
