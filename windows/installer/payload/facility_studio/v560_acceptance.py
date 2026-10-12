"""V5.6 engineering boundaries and actual delivered navigation / gas widgets."""
import copy
import math
import random
import re

from .data import HVAC_PIPES, HVAC_PIPE_REFERENCES
from .errors import ValidationError
from .gas_catalog import GAS_OPTIONS, CUSTOM_GAS, reference_velocity, switched_velocity
from .simple_schema import defaults, active_field
from .simple_engines import compressed_air, water
from .simple_reports import tool_report
from .schema import default_project, V556_INPUT_KEYS, FIELDS
from .engine import calculate, migrate_project, gas_from_inputs
from .utils import gas_result, water_selection
from .reports import report
from .version import VERSION


def run_checks():
    checks = []

    def check(name, value):
        if not value:
            raise AssertionError(name)
        checks.append(dict(name=name, passed=True))

    def close(name, actual, expected):
        check(name, math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9))

    def error(name, action, field=None):
        try:
            action()
        except ValidationError as exc:
            check(name, field is None or exc.field_name == field)
        else:
            raise AssertionError(name + ': accepted invalid input')

    check('Version 5.6.0', VERSION == '5.6.0')
    check('50 named gases plus custom / mixture', len(GAS_OPTIONS) == 51 and len(set(GAS_OPTIONS)) == 51)
    check('Legacy gas order / compatibility', GAS_OPTIONS[:9] == ('N2','CDA','O2','Ar','He','H2','CO2','GN2','PN2'))
    for size, od, expected_id in ((14,355.6,336.6), (16,406.4,387.4), (18,457.2,438.2), (20,508.0,489.0), (22,558.8,539.8), (24,609.6,590.6)):
        row = HVAC_PIPES[-6 + (size-14)//2]
        ref = HVAC_PIPE_REFERENCES[row['size']]
        close('Water ID %s inches' % size, row['id_mm'], expected_id)
        close('Water OD %s inches' % size, ref['outside_mm'], od)
        close('Water wall subtraction %s inches' % size, row['id_mm'], ref['outside_mm'] - 2*ref['wall_mm'])
    for flow, velocity, expected in ((100,1.5,40.9), (7000,1,387.4), (16000,2,438.2), (20000,1.5,539.8), (30000,2,590.6)):
        row = water_selection(flow, velocity)
        check('Single water pipe %s LPM / %s m/s' % (flow,velocity), row['runs'] == 1 and row['id_mm'] == expected)
    area24 = math.pi * (590.6 / 1000)**2 / 4
    capacity = area24 * 60000 * 2
    close('24 inch velocity boundary', water_selection(capacity, 2)['velocity_mps'], 2)
    check('Above 24 inch capacity requires parallel', water_selection(capacity*(1+1e-7), 2)['runs'] == 2)
    check('Zero water demand', water_selection(0, 1)['runs'] == 0)
    manual = water_selection(30000, 2, manual_id=574.6)
    close('Actual Sch40 ID is respected', manual['id_mm'], 574.6)
    check('Custom pipe keeps one run', manual['runs'] == 1 and 'reference' not in manual)
    error('Manual undersized pipe rejected', lambda: water_selection(30000, 1, manual_id=574.6))
    error('Above 32 parallel runs rejected', lambda: water_selection(area24*60000*2*32*1.001, 2))
    rng = random.Random(56020261012)
    for index in range(100):
        flow, velocity = rng.uniform(100, 100000), rng.uniform(.5, 3)
        row = water_selection(flow, velocity)
        independently_required_runs = math.ceil(flow / (area24*60000*velocity) - 1e-12)
        check('Random water minimal run count %s' % index, row['runs'] == independently_required_runs)
        close('Random water continuity %s' % index, row['velocity_mps']*row['area_m2']*row['runs']*60000, flow)
        check('Random water velocity bound %s' % index, row['velocity_mps'] <= velocity + 1e-10)
    legacy = water_selection(30000, 10, mode='原專案流量表')
    check('Legacy flow table also uses large single pipe', legacy['runs'] == 1 and legacy['id_mm'] > 303.2)
    inp = defaults('water'); inp.update(flow='30000', velocity='2')
    check('Simple water report gives wall and ID', '590.6' in str(tool_report(water(inp), inp)) and '9.5mm' in str(tool_report(water(inp), inp)))
    check('CDA to NF3 clears carried preset', switched_velocity('CDA', 'NF3', '15') == '')
    check('CDA to N2 updates known preset', switched_velocity('CDA', 'N2', '15') == '12')
    check('Explicit legacy custom velocity retained', switched_velocity('CDA', 'N2', '5') == '5')
    check('Return from blank process gas restores known preset', switched_velocity('NF3', 'N2', '') == '12')
    from . import i18n
    old_language = i18n.language()
    try:
        for gas in GAS_OPTIONS:
            for pressure in (0, 5, 30):
                inputs = defaults('gas')
                inputs.update(gas=gas, gas_name='5% H2 / 95% N2', velocity='7', flow='84', pressure=str(pressure), temperature='65', reference_t='0', z_ratio='2.1')
                simple = compressed_air(inputs)
                expected = 84 * 101.325/(101.325+pressure*100) * (65+273.15)/273.15 * 2.1
                close('Gas T/P/Z flow %s / %s' % (gas,pressure), simple['actual_lpm'], expected)
                actual = dict(inputs, flow_basis='管內實際流量', flow_unit='ALPM', flow=str(expected))
                close('Gas reverse basis %s / %s' % (gas,pressure), compressed_air(actual)['standard_lpm'], 84)
                base = default_project()['inputs']
                base.update(gas1_type=gas, gas1_name='5% H2 / 95% N2', gas1_q='84', gas1_pressure_mode='本路管內壓力', gas1_barg=str(pressure), gas1_v_mode='自訂流速', gas1_velocity='7', gas_barg='30', gas_std_t='0', gas_temp='65', gas_z_ratio='2.1')
                full = gas_from_inputs(base)['1']
                close('Main / simple gas agreement %s / %s' % (gas,pressure), full['actual_lpm'], simple['actual_lpm'])
                close('Main / simple gas diameter %s / %s' % (gas,pressure), full['selected_id_mm'], simple['pipe']['id'])
                check('Gas velocity ceiling %s / %s' % (gas,pressure), full['velocity_mps'] <= 7 + 1e-10)
            if reference_velocity(gas) is None:
                bad = dict(base, gas1_v_mode='依氣體參考')
                error('New gas requires explicit velocity ' + gas, lambda d=bad: gas_from_inputs(d), 'gas1_v_mode')
                zero = dict(bad, gas1_q='0', gas1_velocity='bad', gas1_name='bad\nname')
                check('Unused new gas draft is neutral ' + gas, gas_from_inputs(zero)['1']['velocity_limit_mps'] == 0)
            for language in ('zh-Hant', 'en'):
                i18n.set_language(language, persist=False)
                text = str(tool_report(simple, inputs))
                check('Named gas report ' + gas + '/' + language, bool(text) and ('5% H2 / 95% N2' in text if gas == CUSTOM_GAS else gas in text))
                if language == 'en':
                    check('Gas report English coverage ' + gas, not re.search(r'[\u3400-\u9fff]', text))
    finally:
        i18n.set_language(old_language, persist=False)
    inactive = defaults('gas')
    inactive['gas_name'] = 'bad\nname'
    check('Inactive custom name ignored', compressed_air(inactive)['custom_name'] is None and not active_field('gas', 'gas_name', inactive))
    zero = dict(inactive, gas=CUSTOM_GAS, flow='0.00')
    check('Zero custom name ignored', compressed_air(zero)['custom_name'] is None and not active_field('gas', 'gas_name', zero))
    active = dict(inactive, gas=CUSTOM_GAS)
    error('Active custom name validates line breaks', lambda: compressed_air(active), 'gas_name')
    for z in ('0', 'NaN', '3.01', 'abc'):
        error('Invalid Z rejected ' + z, lambda value=z: compressed_air(dict(inactive, z_ratio=value)), 'z_ratio')
    new = default_project()
    old = copy.deepcopy(new)
    old['schema_version'] = 10
    old['inputs'] = {k: v for k,v in old['inputs'].items() if k in V556_INPUT_KEYS}
    old['provenance'] = {k: v for k,v in old['provenance'].items() if k in V556_INPUT_KEYS}
    untouched = copy.deepcopy(old)
    migrated = migrate_project(old)
    check('V5510 project migrates without mutation', old == untouched and migrated['schema_version'] == 11 and set(migrated['inputs']) == set(FIELDS))
    check('Migration preserves every engineering input', all(migrated['inputs'][k] == v for k,v in old['inputs'].items()))
    check('Migration full calculation', bool(calculate(old)))
    check('Repeated migration is deterministic', migrate_project(old) == migrated)
    check('Old-project calculation identity is stable', calculate(old)['hash'] == calculate(old)['hash'])
    large = default_project(); large['inputs'].update(chw_link='獨立輸入', chw_q='30000', water_velocity_max='2')
    large_result = calculate(large)
    check('Main large CHW selects one 24 inch pipe', large_result['water']['CHW']['runs'] == 1 and large_result['water']['CHW']['id_mm'] == 590.6)
    check('Main pressure calculation retains large pipe ID', large_result['pressure']['CHW']['total_pa'] >= 0)
    close('Main large CHW hydraulic area', large_result['water']['CHW']['area_m2'], area24)
    malformed = copy.deepcopy(old); malformed['inputs'].pop('gas1_type')
    error('Incomplete old project refused', lambda: migrate_project(malformed))
    custom = default_project()
    custom['inputs'].update(gas1_type=CUSTOM_GAS, gas1_name='氣體：5% H2 / 95% N2', gas1_q='84', gas1_v_mode='自訂流速', gas1_velocity='5')
    result = calculate(custom)
    i18n.set_language('en', persist=False)
    try:
        check('Custom main report preserves user name', '氣體：5% H2 / 95% N2' in str(report(result)))
    finally:
        i18n.set_language(old_language, persist=False)
    return dict(version=VERSION, passed=True, checks=checks, scope='Source calculations; native widgets checked separately')


def run_ui(root, app, main, check, pump):
    from . import i18n
    from .simple_schema import TOOLS
    original_geometry, original_language, original_tool = root.geometry(), i18n.language(), app.current
    saved = {key: page.data() for key,page in app.pages.items()}
    original_main = copy.deepcopy(main.snapshot())
    try:
        root.geometry('780x560+0+0')
        root.deiconify()
        root.lift()
        pump()
        for lang in ('zh-Hant', 'en'):
            i18n.set_language(lang, persist=False)
            for tool in TOOLS:
                def navigate(name=tool):
                    app.nav[name].invoke()
                    pump()
                    button = app.nav[name]
                    return app.current == name and button.winfo_ismapped() and button.winfo_y() >= 0 and button.winfo_y()+button.winfo_height() <= app.tutorial_button.winfo_y()
                check('V560 direct sidebar button at minimum window %s/%s' % (lang,tool), navigate)
            check('V560 complete direct navigation ' + lang, lambda: set(app.nav) == set(TOOLS) and not hasattr(app, 'more'))
            check('V560 author visible ' + lang, lambda: app.author_credit.winfo_ismapped() and 'ANDY HUANG' in app.author_credit.cget('text'))
            app.nav['gas'].invoke(); pump()
            page = app.active_page(); page.reset()
            check('V560 all factory gases in native combo ' + lang, lambda: tuple(page.widgets['gas'].cget('values')) == GAS_OPTIONS)
            page.variables['gas'].set('NF3'); page.calculate(); pump()
            check('V560 process gas requires entered velocity ' + lang, lambda: page.variables['gas'].get() == 'NF3' and page.variables['velocity'].get() == '' and page.result is None and app.export_button.instate(['disabled']))
            page.variables['velocity'].set('7'); page.calculate(); pump()
            check('V560 process gas native calculation ' + lang, lambda: page.result is not None and page.result['gas'] == 'NF3')
            page.variables['gas'].set(CUSTOM_GAS); page.variables['gas_name'].set('5% H2 / 95% N2'); page.variables['velocity'].set('5'); page.calculate(); pump()
            check('V560 custom mixture native field ' + lang, lambda: page.rows['gas_name'].winfo_manager() == 'grid' and page.result is not None and page.result['custom_name'] == '5% H2 / 95% N2')
            page.variables['gas'].set('N2'); page.calculate(); pump()
            check('V560 custom draft retained while inactive ' + lang, lambda: not page.rows['gas_name'].winfo_manager() and page.variables['gas_name'].get() == '5% H2 / 95% N2' and page.result is not None)
            app.nav['water'].invoke(); pump(); water_page = app.active_page(); water_page.reset()
            water_page.variables['flow'].set('30000'); water_page.variables['velocity'].set('2'); water_page.calculate(); pump()
            check('V560 native large single water pipe ' + lang, lambda: water_page.result is not None and water_page.result['pipe']['runs'] == 1 and water_page.result['pipe']['id_mm'] == 590.6)
            main.apply_project(default_project()); pump()
            check('V560 workbench gas choices ' + lang, lambda: tuple(main.widgets['gas1_type'].cget('values')) == GAS_OPTIONS)
    finally:
        main.apply_project(original_main)
        for key, values in saved.items():
            page = app.pages[key]
            page.suspended = True
            for name, value in values.items(): page.variables[name].set(value)
            page.suspended = False
            page.previous = dict(values)
            page.update_visibility(); page.calculate()
        i18n.set_language(original_language, persist=False)
        root.geometry(original_geometry)
        app.show_tool(original_tool)
        pump()
