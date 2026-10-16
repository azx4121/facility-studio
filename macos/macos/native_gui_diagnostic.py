"""External tracing of an unchanged App's bundled runtime and GUI modules.

The external embedding entry has a different Cocoa main-bundle identity from
the FacilityStudio launcher. The uninstrumented launcher self-test is the control;
these probes are diagnostic evidence, never a replacement for its assertions.
"""
import argparse
import copy
import faulthandler
import functools
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time
import traceback


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('runtime', 'continuous', 'segmented', 'selftest'), required=True)
    parser.add_argument('--switches', type=int, default=100)
    parser.add_argument('--periodic-dump', type=int, choices=(0, 1, 25), default=0)
    args = parser.parse_args()
    if sys.platform != 'darwin' or args.switches < 2:
        parser.error('Use native macOS and at least two language switches.')
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ['FACILITY_STUDIO_PREFERENCES'] = str(args.output.resolve()/'preferences.json')
    started = time.monotonic()
    trace = (args.output / 'events.txt').open('w', encoding='utf-8', buffering=1)
    sequence = 0
    phase = 'bootstrap'
    depths = {}

    def emit(event, **detail):
        nonlocal sequence
        sequence += 1
        row = dict(sequence=sequence, seconds=round(time.monotonic()-started, 6),
                   pid=os.getpid(), thread=threading.get_ident(), phase=phase,
                   event=event, **detail)
        trace.write(json.dumps(row, ensure_ascii=False, default=str)+'\n')
        trace.flush()

    def cancel_periodic_dump():
        emit('watchdog.cancel.begin', periodic_seconds=args.periodic_dump)
        faulthandler.cancel_dump_traceback_later()
        emit('watchdog.cancel.end', periodic_seconds=args.periodic_dump)

    faulthandler.enable()
    if args.periodic_dump:
        faulthandler.dump_traceback_later(args.periodic_dump, repeat=True)
    resources = args.app.resolve() / 'Contents/Resources'
    spec = importlib.util.spec_from_file_location('_probe_original_bootstrap', resources/'bootstrap.py')
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    bootstrap.configure_runtime(resources)
    original_launcher = args.app.resolve()/'Contents/MacOS/FacilityStudio'
    assert Path(sys.executable).resolve() == original_launcher, 'Embedded sys.executable does not identify the original launcher'
    framework = args.app.resolve()/'Contents/Frameworks/Python.framework/Versions/3.13'
    assert Path(sys.prefix).resolve() == framework, 'External helper loaded the wrong Python home'
    import tkinter as tk
    from facility_studio import i18n
    from facility_studio.localized_tk import LanguagePicker
    from facility_studio.simple_desktop import SimpleToolsApp
    from facility_studio.desktop import DesktopApp
    from facility_studio.tools_view import QuickToolsWindow
    from facility_studio.air_chart import AirChart
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib
    assert sys.version_info[:2] == (3, 13), 'External helper did not load the original CPython version'
    assert Path(__import__('_tkinter').__file__).resolve().is_relative_to(framework.resolve()), 'Tk extension is outside the original App runtime'
    assert Path(matplotlib.__file__).resolve().is_relative_to(resources/'python-packages'/platform.machine()), 'Matplotlib is outside the original architecture wheel set'

    identity = dict(executable=sys.executable, prefix=sys.prefix,
                    source=str(resources/'app'), architecture=platform.machine(),
                    python=sys.version, matplotlib=matplotlib.__version__,
                    actual_process_executable=os.environ.get('FACILITY_PROBE_HELPER_EXECUTABLE'),
                    main_bundle_identity='External C embedding helper, not the original FacilityStudio Cocoa launcher',
                    libpython=str(framework/'Python'),
                    tkinter_extension=__import__('_tkinter').__file__,
                    matplotlib_source=matplotlib.__file__,
                    mode=args.mode, requested_switches=args.switches)
    identity['isolated_preferences'] = os.environ['FACILITY_STUDIO_PREFERENCES']
    identity['periodic_dump_seconds'] = args.periodic_dump
    identity['accelerated_diagnostic_stress'] = args.periodic_dump == 1
    emit('runtime.identity', **identity)

    if args.mode == 'runtime':
        phase = 'runtime-validation'
        root = tk.Tk()
        identity.update(tcl_patchlevel=root.tk.call('info', 'patchlevel'),
                        tk_patchlevel=root.tk.call('package', 'provide', 'Tk'),
                        native_window_system=root.tk.call('tk', 'windowingsystem'))
        assert identity['native_window_system'] == 'aqua', 'The selected runtime is not native Tk Aqua'
        from matplotlib.figure import Figure
        canvas = FigureCanvasTkAgg(Figure(figsize=(2, 2)), master=root)
        canvas.figure.add_subplot().plot([0, 1], [0, 1])
        canvas.draw()
        root.after(150, root.quit)
        root.mainloop()
        root.destroy()
        emit('runtime.validation.passed', **identity)
        (args.output/'Diagnostic_Summary.json').write_text(json.dumps(dict(identity, passed=True), indent=2)+'\n')
        cancel_periodic_dump()
        trace.close()
        return 0

    def wrap(owner, name, label):
        original = getattr(owner, name)
        @functools.wraps(original)
        def call(*values, **kwargs):
            depths[label] = depths.get(label, 0)+1
            detail = dict(depth=depths[label])
            if label == 'tk.event_conversion':
                raw = values[1:]
                detail['argument_count'] = len(raw)
                # Do not coerce Tcl objects while diagnosing getint_event.
                for key, index in (('widget', 14), ('type', 15)):
                    if len(raw) > index and isinstance(raw[index], (str, int)):
                        detail[key] = raw[index]
            if label == 'language.set' and values:
                detail['requested'] = values[0]
                detail['listener_order'] = [type(x).__name__ for x in list(i18n._listeners)]
            if values and hasattr(values[0], '_w'):
                detail.setdefault('widget', values[0]._w)
            emit(label+'.begin', **detail)
            try:
                return original(*values, **kwargs)
            except BaseException as error:
                emit(label+'.error', error=type(error).__name__, message=str(error))
                raise
            finally:
                emit(label+'.end', depth=depths[label])
                depths[label] -= 1
        setattr(owner, name, call)

    for owner, name, label in (
        (tk.Misc, '_substitute', 'tk.event_conversion'),
        (LanguagePicker, 'selected', 'language.native_selection'),
        (i18n, 'set_language', 'language.set'),
        (DesktopApp, 'refresh_language', 'workbench.language'),
        (DesktopApp, 'draw', 'workbench.draw'),
        (QuickToolsWindow, 'refresh_language', 'quick.language'),
        (QuickToolsWindow, 'draw', 'quick.draw'),
        (AirChart, 'redraw', 'air_canvas.redraw'),
        (FigureCanvasTkAgg, 'draw_idle', 'tkagg.draw_idle'),
        (FigureCanvasTkAgg, 'draw', 'tkagg.draw'),
        (Figure, 'tight_layout', 'figure.tight_layout'),
        (tk.Misc, 'mainloop', 'tk.mainloop'),
    ):
        wrap(owner, name, label)

    if args.mode == 'selftest':
        phase = 'original-selftest-instrumented'
        from mac_selftest import run
        code = run()
        summary = dict(**identity, passed=code == 0, returncode=code,
                       scope='Original self-test assertions unchanged; external runtime tracing changes timing.')
        (args.output/'Diagnostic_Summary.json').write_text(json.dumps(summary, indent=2)+'\n')
        cancel_periodic_dump()
        trace.close()
        return code

    phase = 'setup'
    i18n.set_language('en', persist=False)
    root = tk.Tk()
    callback_errors = []
    def callback_error(*detail):
        callback_errors.append(''.join(traceback.format_exception(*detail)))
        emit('callback.error', traceback=callback_errors[-1])
        root.quit()
    root.report_callback_exception = callback_error
    app = SimpleToolsApp(root)
    root.geometry('1100x760')
    for tool in ('electrical', 'duct', 'gas', 'lighting', 'water', 'air', 'units', 'cleanroom', 'heat_loads', 'pumps'):
        app.show_tool(tool)
    app.open_equipment()
    workbench = app.open_workbench()
    root.report_callback_exception = callback_error
    for page in range(9):
        workbench.show_page(page)
    quick = QuickToolsWindow(workbench.root, workbench)
    quick.tool.set('濕空氣計算')
    quick.build()
    quick.calculate()
    app.show_tool('air')
    expected_result = copy.deepcopy(quick.result)
    assert expected_result is not None, 'Quick-tools setup failed to calculate'
    expected_project = digest(workbench.snapshot())
    expected_workbench_result = copy.deepcopy(workbench.result)
    completed = 0
    failed = None
    heartbeat_count = 0
    switch_started = None
    switch_seconds = 0
    def heartbeat():
        nonlocal heartbeat_count
        heartbeat_count += 1
        emit('heartbeat', count=heartbeat_count)
        root.after(100, heartbeat)
    root.after(100, heartbeat)

    def choose(code):
        emit('choose.begin', language=code)
        app.language_picker.choice.set(i18n.LANGUAGES[code])
        emit('choose.event_generate.begin', language=code)
        app.language_picker.event_generate('<<ComboboxSelected>>')
        emit('choose.event_generate.end', language=code)

    def verify(code):
        nonlocal completed
        assert i18n.language() == code, 'Language selection did not fire'
        assert quick.result == expected_result, 'Plot redraw changed engineering state'
        assert digest(workbench.snapshot()) == expected_project, 'Workbench project changed'
        assert workbench.result == expected_workbench_result, 'Workbench calculation result changed'
        assert ('空氣' in quick.ax.get_title()) if code == 'zh-Hant' else ('空氣' not in quick.ax.get_title()), 'Plot language mismatch'
        assert not callback_errors, 'Native callback exception'
        completed += 1
        emit('choose.verified', language=code, completed=completed)

    def pump():
        emit('pump.begin', pending_after=list(root.tk.splitlist(root.tk.call('after', 'info'))))
        root.after(150, root.quit)
        before = time.monotonic()
        root.mainloop()
        elapsed = time.monotonic()-before
        emit('pump.end', elapsed_seconds=elapsed)
        assert elapsed <= 5, 'Original interaction timing budget exceeded'

    try:
        phase = 'initial-render'
        pump()
        expected_project = digest(workbench.snapshot())
        expected_workbench_result = copy.deepcopy(workbench.result)
        phase = args.mode+'-language-switches'
        switch_started = time.monotonic()
        if args.mode == 'segmented':
            for index in range(args.switches):
                code = 'zh-Hant' if index % 2 == 0 else 'en'
                choose(code)
                pump()
                verify(code)
        else:
            def step(index=0):
                nonlocal failed
                try:
                    code = 'zh-Hant' if index % 2 == 0 else 'en'
                    choose(code)
                    def settled():
                        nonlocal failed
                        try:
                            verify(code)
                            if completed == args.switches:
                                root.quit()
                            else:
                                root.after(1, lambda: step(index+1))
                        except Exception:
                            failed = traceback.format_exc()
                            emit('verification.error', traceback=failed)
                            root.quit()
                    root.after(300, settled)
                except Exception:
                    failed = traceback.format_exc()
                    emit('selection.error', traceback=failed)
                    root.quit()
            root.after(1, step)
            emit('continuous.mainloop.begin')
            root.mainloop()
            emit('continuous.mainloop.end')
        assert completed == args.switches and failed is None and not callback_errors
    except Exception:
        failed = traceback.format_exc()
        emit('probe.error', traceback=failed)
    finally:
        phase = 'cleanup'
        if switch_started is not None:
            switch_seconds = time.monotonic()-switch_started
        emit('cleanup.begin')
        root.destroy()
        emit('cleanup.end')
        cancel_periodic_dump()
    summary = dict(**identity, passed=failed is None and completed == args.switches,
                   completed_switches=completed, callback_errors=callback_errors,
                   error=failed, heartbeat_count=heartbeat_count,
                   active_language_switch_seconds=switch_seconds,
                   tcl_patchlevel=root.tk.call('info', 'patchlevel'),
                   seconds=time.monotonic()-started,
                   scope='Diagnostic monkeypatch tracing; native events and original modules; no App files or assertions modified.')
    (args.output/'Diagnostic_Summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    trace.close()
    return 0 if summary['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
