"""Independent lumen-method checks and actual-widget regressions for F07."""

from decimal import Decimal, ROUND_CEILING
import math
import random

from .simple_engines import lighting
from .simple_schema import defaults


def run_checks():
    from .engine import lighting as workbench_lighting
    from .schema import default_project

    checks = []
    rng = random.Random(20261018)
    for index in range(500):
        length = Decimal(rng.randint(4, 200)) / 2
        width = Decimal(rng.randint(4, 200)) / 2
        area = length * width
        lux = Decimal(rng.choice([100, 300, 500, 750, 1000]))
        lumens = Decimal(rng.choice([2000, 3000, 4000, 6400, 8000]))
        u = Decimal(rng.choice(['0.35', '0.6', '0.75', '0.9']))
        m = Decimal(rng.choice(['0.6', '0.8', '0.9']))
        expected = int((lux * area / (lumens * u * m)).to_integral_value(rounding=ROUND_CEILING))
        for mode in ('面積 m²', '面積 坪', '長×寬', '體積 m³'):
            value = area * Decimal(121) / 400 if mode == '面積 坪' else area * 3 if mode == '體積 m³' else area
            inputs = dict(defaults('lighting'), mode='反算燈數', area_mode=mode,
                          length=str(length), width=str(width), area=str(value), height='3',
                          lumen_mode='燈具型錄流明', lumens=str(lumens), target=str(lux),
                          utilization=str(u), maintenance=str(m))
            actual = lighting(inputs)['quantity']
            if actual != expected:
                raise AssertionError((index, mode, actual, expected))
            checks.append(dict(name=f'lighting formula {index}/{mode}', passed=True))
        project = default_project()
        project['inputs'].update(en_L_A=str(length), en_W_A=str(width), en_L_B='0', en_W_B='0',
                                 light_lux=str(lux), light_lm=str(lumens), light_u=str(u), light_m=str(m))
        actual = workbench_lighting(project['inputs'])['qty']
        if actual != expected:
            raise AssertionError((index, 'workbench', actual, expected))
        checks.append(dict(name=f'lighting workbench formula {index}', passed=True))
    return checks


def run_ui(root, app, check, pump):
    """Use the delivered button; check accepts a name and a zero-argument action."""
    from . import i18n
    from .simple_reports import tool_report

    language = i18n.language()
    current = app.current
    try:
        app.show_tool('lighting')
        page = app.active_page()
        for lang in ('zh-Hant', 'en'):
            i18n.set_language(lang, persist=False)
            for name, mode, area in (('m2', '面積 m²', '75'), ('ping', '面積 坪', '22.6875'),
                                     ('volume', '體積 m³', '225'), ('geometry', '長×寬', None)):
                page.reset()
                # Batch drafts as a user-completed form; actual button invokes
                # all production validation and calculation paths below.
                page.suspended = True
                try:
                    values = dict(mode='反算燈數', area_mode=mode, height='3', target='500',
                                  lumen_mode='燈具型錄流明', lumens='4000', utilization='.6', maintenance='.8')
                    if area is None:
                        values.update(length='15', width='5')
                    else:
                        values.update(area=area, length='bad hidden draft', width='0')
                    for key, value in values.items():
                        page.variables[key].set(value)
                    page.previous = page.data()
                finally:
                    page.suspended = False
                page.update_visibility()
                page.calculate()
                pump()
                before = page.data()
                prefix = f'F07 {lang}/{name}'
                check(prefix + ' baseline is 75 m2 / 20 fixtures',
                      lambda: page.result is not None and page.result['area_m2'] == 75 and page.result['quantity'] == 20)
                for repeat in range(2):
                    page.dialux_button.invoke()
                    pump()
                    check(prefix + f' repeat {repeat} preserves every engineering input',
                          lambda: all(value == page.data()[key] for key, value in before.items() if key != 'u_mode'))
                    check(prefix + f' repeat {repeat} retains 75 m2 / 20 fixtures / 512 lux',
                          lambda: page.result is not None and page.result['area_m2'] == 75
                          and page.result['quantity'] == 20 and page.result['illuminance_lux'] == 512)
                    check(prefix + f' repeat {repeat} only enables K with actual geometry',
                          lambda: (page.result['room_index_k'] is not None) == (area is None))
                text = str(tool_report(page.result, page.data(), language=lang))
                check(prefix + ' exported TXT retains the adopted area and count',
                      lambda: '75' in text and '20' in text and ('8 盞' not in text if lang == 'zh-Hant' else True))

            # The action also must not silently replace watts-derived lumens
            # with an old catalogue draft or change estimation into count mode.
            page.reset()
            page.variables['area_mode'].set('長×寬')
            page.variables['length'].set('15')
            page.variables['width'].set('5')
            page.variables['watts'].set('60')
            page.variables['efficacy'].set('150')
            page.variables['lumens'].set('stale invalid catalogue draft')
            page.calculate()
            before = dict(page.result)
            page.dialux_button.invoke()
            pump()
            check(f'F07 {lang} preserves LED source and estimate mode',
                  lambda: page.result is not None and page.result['lumen_mode'] == 'LED功率初估'
                  and page.variables['mode'].get() == '估算照度' and page.result['lumens_per_lamp'] == 9000
                  and page.result['illuminance_lux'] == before['illuminance_lux'])
            check(f'F07 {lang} K uses the entered dimensions and mounting heights',
                  lambda: math.isclose(page.result['room_index_k'], 75 / (2.2 * 20), rel_tol=1e-12))

            page.variables['mount_h'].set('0.8')
            page.dialux_button.invoke()
            pump()
            check(f'F07 {lang} invalid geometry clears results', lambda: page.result is None)
    finally:
        i18n.set_language(language, persist=False)
        app.show_tool('lighting')
        app.active_page().reset()
        app.show_tool(current)
