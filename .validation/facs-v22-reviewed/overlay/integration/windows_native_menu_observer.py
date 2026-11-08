"""Read-only native/Tk menu observations; owner-drawn labels are Tk metadata.

Tk 8.6.15 win/tkWinMenu.c installs string menubar entries but owner-drawn
popup entries. No internal pointers are dereferenced and no labels are changed.
"""
import ctypes
from ctypes import wintypes

EXPECTED = {
    'en': (['Facility Studio', 'File', 'Edit', 'Window', 'Help'],
           [['About Facility Studio'], ['Close window'],
            ['Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Select all'], ['Minimize'],
            ['Verification purpose and scope']]),
    'zh-Hant': (['Facility Studio', '檔案', '編輯', '視窗', '說明'],
                [['關於 Facility Studio'], ['關閉視窗'], ['復原', '重做', '剪下', '複製', '貼上', '全選'],
                 ['縮到最小'], ['驗證用途與範圍']]),
}


def validate_observation(native, metadata, language):
    """Fail closed on an unfamiliar shape, foreign menu or unclassified label."""
    top_expected, child_expected = EXPECTED[language]
    assert native['hwnd'] and native['menu']
    assert metadata['attached_menu'] == metadata['authored_menu'] and metadata['attached_menu']
    tk_top = list(metadata['top'])
    offset = 0
    # Tk's master menu defaults to a tearoff, omitted by its native MENUBAR.
    if tk_top and tk_top[0]['type'] == 'tearoff':
        assert tk_top[0]['index'] == 0
        tk_top = tk_top[1:]
        offset = 1
    assert len(native['top']) == len(tk_top) == len(top_expected)
    ids, pointers, handles = set(), set(), set()
    for position, (os_top, tk_entry) in enumerate(zip(native['top'], tk_top)):
        assert tk_entry['index'] == position + offset and tk_entry['type'] == 'cascade'
        assert tk_entry['label'] == os_top['label'] == top_expected[position]
        assert os_top['ftype'] == 0 and os_top['state'] == 0
        handle = os_top['submenu']
        assert handle and handle == os_top['queried_submenu'] and handle not in handles
        handles.add(handle)
        assert tk_entry['submenu'] in metadata['authored_submenus']
        assert tk_entry['submenu'] == metadata['authored_submenus'][position]
        assert len(os_top['children']) == len(tk_entry['children']) == len(child_expected[position])
        for index, (item, entry) in enumerate(zip(os_top['children'], tk_entry['children'])):
            assert entry['index'] == index and entry['type'] == 'command'
            assert entry['command'] and entry['label'] == child_expected[position][index]
            assert entry['state'] in ('normal', 'disabled')
            assert item['state'] == (3 if entry['state'] == 'disabled' else 0)
            assert item['submenu'] == 0
            assert 0 < item['id'] < 0xffffffff and item['id'] not in ids
            ids.add(item['id'])
            if item['ftype'] == 0x100:  # MFT_OWNERDRAW, not separator/bitmap/etc.
                assert item['data'] and item['data'] not in pointers
                pointers.add(item['data'])
                assert item['native_text'] == ''
                assert item['label_source'] == 'tk.entrycget(-label);win32.MFT_OWNERDRAW'
            else:
                assert item['ftype'] == 0  # Explicit string-backed alternative only.
                assert item['native_text'] == entry['label']
                assert item['label_source'] == 'win32.GetMenuStringW'
            assert item['observed_label'] == entry['label']
    return top_expected, child_expected


def observe_native_menus(root, language):
    api = ctypes.WinDLL('user32', use_last_error=True)
    class MenuItemInfo(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.UINT), ('fMask', wintypes.UINT),
                    ('fType', wintypes.UINT), ('fState', wintypes.UINT),
                    ('wID', wintypes.UINT), ('hSubMenu', wintypes.HMENU),
                    ('hbmpChecked', wintypes.HBITMAP), ('hbmpUnchecked', wintypes.HBITMAP),
                    ('dwItemData', ctypes.c_size_t), ('dwTypeData', wintypes.LPWSTR),
                    ('cch', wintypes.UINT), ('hbmpItem', wintypes.HBITMAP)]
    definitions = {
        'GetAncestor': ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
        'GetMenu': ([wintypes.HWND], wintypes.HMENU),
        'GetSubMenu': ([wintypes.HMENU, ctypes.c_int], wintypes.HMENU),
        'GetMenuItemCount': ([wintypes.HMENU], ctypes.c_int),
        'GetMenuStringW': ([wintypes.HMENU, wintypes.UINT, wintypes.LPWSTR, ctypes.c_int, wintypes.UINT], ctypes.c_int),
        'GetMenuItemInfoW': ([wintypes.HMENU, wintypes.UINT, wintypes.BOOL, ctypes.POINTER(MenuItemInfo)], wintypes.BOOL),
    }
    for name, (args, result) in definitions.items():
        fn = getattr(api, name)
        fn.argtypes, fn.restype = args, result
    def info(handle, index):
        item = MenuItemInfo(cbSize=ctypes.sizeof(MenuItemInfo), fMask=0x100 | 0x1 | 0x2 | 0x4 | 0x20)
        assert api.GetMenuItemInfoW(handle, index, True, ctypes.byref(item)), 'GetMenuItemInfoW failed'
        buf = ctypes.create_unicode_buffer(512)
        length = api.GetMenuStringW(handle, index, buf, len(buf), 0x400)
        assert 0 <= length < len(buf) - 1
        return {'ftype': int(item.fType), 'state': int(item.fState), 'id': int(item.wID),
                'submenu': int(item.hSubMenu or 0), 'data': int(item.dwItemData), 'native_text': buf.value}
    def tk_rows(path):
        end = root.tk.call(path, 'index', 'end')
        result = []
        for index in range(0 if str(end) == 'none' else int(end) + 1):
            kind = str(root.tk.call(path, 'type', index))
            row = {'index': index, 'type': kind}
            if kind not in ('tearoff', 'separator'):
                row.update({key: str(root.tk.call(path, 'entrycget', index, '-' + key))
                            for key in ('label', 'state')})
                if kind == 'cascade':
                    row['submenu'] = str(root.tk.call(path, 'entrycget', index, '-menu'))
                    row['children'] = tk_rows(row['submenu'])
                elif kind == 'command':
                    row['command'] = str(root.tk.call(path, 'entrycget', index, '-command'))
            result.append(row)
        return result
    authored = root._sandbox_menu
    # Registration order is authored, not inferred from current displayed labels.
    registered = [str(child) for child in authored._sandbox_command_labels]
    path = str(root.cget('menu'))
    metadata = {'attached_menu': path, 'authored_menu': str(authored),
                'authored_submenus': registered, 'top': tk_rows(path),
                'tk_version': str(root.tk.call('package', 'provide', 'Tk'))}
    hwnd = api.GetAncestor(root.winfo_id(), 2)
    handle = api.GetMenu(hwnd)
    assert hwnd and handle
    native = {'hwnd': int(hwnd), 'menu': int(handle), 'top': []}
    tk_top = metadata['top']
    if tk_top and tk_top[0]['type'] == 'tearoff':
        tk_top = tk_top[1:]
    count = api.GetMenuItemCount(handle)
    assert count == len(tk_top) == 5
    for index in range(count):
        row = info(handle, index)
        row['label'] = row['native_text']
        row['queried_submenu'] = int(api.GetSubMenu(handle, index) or 0)
        assert row['submenu'] and row['submenu'] == row['queried_submenu']
        child_count = api.GetMenuItemCount(row['submenu'])
        tk_children = tk_top[index].get('children', [])
        assert child_count == len(tk_children)
        row['children'] = []
        for child_index in range(child_count):
            item = info(row['submenu'], child_index)
            tk_label = tk_children[child_index].get('label', '')
            if item['ftype'] == 0x100:
                item['observed_label'] = tk_label
                item['label_source'] = 'tk.entrycget(-label);win32.MFT_OWNERDRAW'
            else:
                item['observed_label'] = item['native_text']
                item['label_source'] = 'win32.GetMenuStringW'
            row['children'].append(item)
        native['top'].append(row)
    validate_observation(native, metadata, language)
    # Return observed values, never the expected-list constants.
    return ([item['label'] for item in native['top']],
            [[child['observed_label'] for child in item['children']] for item in native['top']],
            {'native': native, 'tk_metadata': metadata, 'popup_pixels_verified': False})
