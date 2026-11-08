"""Portable behavior contracts, not a claim of native Windows execution."""
from copy import deepcopy
import pytest
from windows_native_menu_observer import EXPECTED, validate_observation


def fixture(language='en', tearoff=True):
    top, children = EXPECTED[language]
    native = {'hwnd': 100, 'menu': 200, 'top': []}
    meta = {'attached_menu': '.menu', 'authored_menu': '.menu', 'top': [],
            'authored_submenus': ['.menu.' + str(i) for i in range(5)]}
    if tearoff:
        meta['top'].append({'index': 0, 'type': 'tearoff'})
    ident = 1
    for index, label in enumerate(top):
        os_entry = {'label': label, 'ftype': 0, 'state': 0, 'submenu': 300+index,
                    'queried_submenu': 300+index, 'children': []}
        tk_entry = {'index': index + int(tearoff), 'type': 'cascade', 'label': label,
                    'submenu': meta['authored_submenus'][index], 'children': []}
        for pos, child in enumerate(children[index]):
            os_entry['children'].append({'ftype': 0x100, 'state': 0, 'submenu': 0, 'id': ident,
                'data': 1000+ident, 'native_text': '', 'observed_label': child,
                'label_source': 'tk.entrycget(-label);win32.MFT_OWNERDRAW'})
            tk_entry['children'].append({'index': pos, 'type': 'command', 'label': child,
                                        'state': 'normal', 'command': 'callback'+str(ident)})
            ident += 1
        native['top'].append(os_entry)
        meta['top'].append(tk_entry)
    return native, meta


@pytest.mark.parametrize('language', ['en', 'zh-Hant'])
@pytest.mark.parametrize('tearoff', [False, True])
def test_actual_validator_accepts_owner_drawn_metadata(language, tearoff):
    native, meta = fixture(language, tearoff)
    before = deepcopy((native, meta))
    validate_observation(native, meta, language)
    assert (native, meta) == before


def test_explicit_string_backed_and_disabled_alternatives():
    native, meta = fixture()
    item = native['top'][0]['children'][0]
    item.update(ftype=0, data=0, native_text='About Facility Studio', label_source='win32.GetMenuStringW', state=3)
    meta['top'][1]['children'][0]['state'] = 'disabled'
    validate_observation(native, meta, 'en')


@pytest.mark.parametrize('fault', [
    'no_hwnd', 'no_menu', 'foreign_attached', 'foreign_submenu', 'wrong_order',
    'empty_native_top', 'wrong_top_label', 'unknown_top_type', 'unknown_top_state',
    'missing_handle', 'handle_mismatch', 'duplicate_handle', 'top_count',
    'top_command', 'extra_tearoff', 'child_count', 'child_type', 'child_index',
    'empty_label', 'foreign_label', 'empty_callback', 'unknown_state', 'state_mismatch',
    'unknown_native_type', 'separator', 'no_data', 'no_id', 'duplicate_id', 'duplicate_data',
    'child_submenu', 'foreign_observed_label', 'false_label_source', 'unexpected_owner_string',
    'empty_string_backed',
])
def test_real_validator_rejects_corrupt_or_unproven_observations(fault):
    native, meta = fixture()
    top = native['top'][0]
    item = top['children'][0]
    tk_top = meta['top'][1]
    child = tk_top['children'][0]
    mutations = {
        'no_hwnd': lambda: native.update(hwnd=0),
        'no_menu': lambda: native.update(menu=0),
        'foreign_attached': lambda: meta.update(attached_menu='.foreign'),
        'foreign_submenu': lambda: tk_top.update(submenu='.foreign'),
        'wrong_order': lambda: meta['authored_submenus'].reverse(),
        'empty_native_top': lambda: top.update(label=''),
        'wrong_top_label': lambda: top.update(label='Description'),
        'unknown_top_type': lambda: top.update(ftype=0x100),
        'unknown_top_state': lambda: top.update(state=128),
        'missing_handle': lambda: top.update(submenu=0, queried_submenu=0),
        'handle_mismatch': lambda: top.update(queried_submenu=999),
        'duplicate_handle': lambda: native['top'][1].update(submenu=300, queried_submenu=300),
        'top_count': lambda: native['top'].pop(),
        'top_command': lambda: tk_top.update(type='command'),
        'extra_tearoff': lambda: tk_top.update(type='tearoff'),
        'child_count': lambda: top['children'].clear(),
        'child_type': lambda: child.update(type='separator'),
        'child_index': lambda: child.update(index=1),
        'empty_label': lambda: child.update(label=''),
        'foreign_label': lambda: child.update(label='Wrong action'),
        'empty_callback': lambda: child.update(command=''),
        'unknown_state': lambda: child.update(state='active'),
        'state_mismatch': lambda: item.update(state=3),
        'unknown_native_type': lambda: item.update(ftype=4),
        'separator': lambda: item.update(ftype=0x900),
        'no_data': lambda: item.update(data=0),
        'no_id': lambda: item.update(id=0),
        'duplicate_id': lambda: native['top'][1]['children'][0].update(id=item['id']),
        'duplicate_data': lambda: native['top'][1]['children'][0].update(data=item['data']),
        'child_submenu': lambda: item.update(submenu=500),
        'foreign_observed_label': lambda: item.update(observed_label='Wrong action'),
        'false_label_source': lambda: item.update(label_source='win32.GetMenuStringW'),
        'unexpected_owner_string': lambda: item.update(native_text='unclassified'),
        'empty_string_backed': lambda: item.update(ftype=0, label_source='win32.GetMenuStringW'),
    }
    mutations[fault]()
    with pytest.raises(AssertionError):
        validate_observation(native, meta, 'en')
