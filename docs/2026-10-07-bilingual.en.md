# V5.5.5 bilingual interface and delivery verification

[繁體中文](2026-10-07-bilingual.md) · [English home / downloads](../README.en.md) · [Documentation](README.en.md)

Select **English** or **繁體中文** at the top right. Open workbench, AHU and equipment windows change together without re-entering numbers or restarting. The language preference is saved.

## Translation and data

Translation covers seven independent tools, the full workbench, individual AHU stages and equipment analysis; field labels, readonly choices, units, assumptions, validation errors and help; psychrometric/workbench charts and TXT/HTML reports; newly exported Excel/CSV templates, including guidance and choices. Chinese and English templates are accepted.

Only presentation text changes. Input numbers, unit reference conditions, formulas, validation rules and project schema stay consistent. User-entered equipment names, project names and notes retain their original text. Existing Chinese projects/schedules remain readable. Invalid input continues to block export after a language change; it does not revive an old valid result.

## Twenty bilingual parity scenarios

Each platform's `tests/bilingual.py` checks numeric outputs, input preservation and report-number consistency:

| # | Tool | Condition |
| --- | --- | --- |
| 1 | Electrical | Default three-phase general load |
| 2 | Electrical | Single-phase 220 V, 5 kW, continuous, PF 1 |
| 3 | Electrical | 30 kW motor, 45°C ambient |
| 4 | Duct | Default flow and velocity |
| 5 | Duct | 2,000 CFM, route enabled, 300 Pa |
| 6 | Duct | Zero flow |
| 7 | CDA | Default pressure and standard flow |
| 8 | N2 | 100 Sm³/h, 600 kPa(g) |
| 9 | Lighting | Default luminaires and room |
| 10 | Lighting | 90 m³ / 3 m → 30 m² |
| 11 | Lighting | 30 m² / 500 lux; count from manufacturer lumens |
| 12 | Water | Default known flow |
| 13 | Water | Known 100 kW, ΔT 5°C |
| 14 | Psychrometrics | Default temperature/RH |
| 15 | Psychrometrics | 35°C / 70% RH |
| 16 | Psychrometrics | 80 kPa(abs) atmospheric pressure |
| 17 | Psychrometrics | 0% RH boundary |
| 18 | Units | Default airflow conversion |
| 19 | Units | 5°C temperature difference, no absolute offset |
| 20 | Units | Kv 10 to Cv |

Both source distributions passed **3,502 checks each**, including dynamic fields, preference persistence, seven-system English Excel/CSV import, old Chinese schedules, full-workbench/AHU reports, HTML language attributes and preservation/escaping of user names. Existing numerical, grouping and import-security regressions are separate from these language checks. The [20 worked engineering scenarios](guides/README.en.md) are another documented set; counts are not added together as distinct conditions.

## Native delivery acceptance

| Delivery | Native host | GUI checks per execution | Evidence |
| --- | --- | --- | --- |
| Windows EXE / ZIP | Windows Server 2022 x64 | 82 passed | [JSON](evidence/v5.5.5-win-2022.json) |
| Same Windows EXE / ZIP | Windows Server 2025 x64 | 82 passed | [JSON](evidence/v5.5.5-win-2025.json) |
| macOS Universal App / ZIP / DMG | Apple Silicon macOS 15.7.9 | 74 passed | [JSON](evidence/v5.5.5-mac-arm64.json) |
| Same macOS App / ZIP / DMG | Intel macOS 15.7.9 | 74 passed | [JSON](evidence/v5.5.5-mac-intel.json) |

Windows acceptance executed the standalone EXE, the extracted ZIP EXE and a Unicode-path copy. External Python was removed from PATH; outbound connectivity was blocked during the offline delivery checks. Seven quick tools, equipment schedules and the full workbench passed. macOS checked deep integrity signatures, native Tk Aqua, NumPy/Pillow, Matplotlib, cold GUI startup, Launch Services, extracted ZIP and mounted DMG execution.

Completed native workflows: [Windows](https://github.com/azx4121/facility-studio/actions/runs/37583708397), [macOS](https://github.com/azx4121/facility-studio/actions/runs/37584093485). Windows release source is `68f2815`; macOS source is `f7294a4`, which also adds Mac diagnostic timing records. Engineering calculations and translation features are consistent. Later repository documentation updates do not change the published executable bytes.

| Public download | SHA-256 |
| --- | --- |
| Windows EXE | `746e967e0889295e7638bd11649f40d753873f19e43923c0a664e49a4d72dff3` |
| Windows ZIP | `d1fe13a1adb3d6e228209dd83c90735d4ce11e5262baa1ba1dc261d6f5378645` |
| macOS DMG | `b249b8272928fa35d092a634e6d4d06a17725d765a3fe46c7f5aba53d72acfd3` |
| macOS ZIP | `9b3f66d5fe937fea7457ebc963c48ce87a5f21ac540371436cc4c887c4308796` |

All four public downloads were downloaded in full and matched both Release `SHA256SUMS.txt` and GitHub asset digests. Both ZIPs passed CRC; the Windows embedded EXE matched the standalone file. Mac bundle version, launcher and bilingual source were present. [Public-byte verification](evidence/v5.5.5-public-packages.json).

## Actual native English screens

![Windows electrical sizing](images/windows-electrical-en.png)

![macOS electrical sizing](images/macos-electrical-en.png)

![macOS psychrometric chart](images/macos-psychrometrics-en.png)

The version also fixes startup dimensions/bottom actions on small displays and macOS sidebar contrast, using ttk buttons with controlled backgrounds. Diagnostic startup failures log and exit instead of waiting for unattended error dialogs. Windows geometry checks wait for native layout to settle and still fail for missing/off-screen actions.

Mac diagnostics separate two initial GUI layouts (20-second event-processing limit) from later interaction cycles (5-second limit). Actual timings are recorded in `Native_UITiming.json` and acceptance JSON. These are event-processing thresholds, not a total application-startup guarantee; initial font-cache creation can add load time.

Hosted checks establish the tested hosts and delivery files. Windows 10/11 are support targets; hosted execution used Windows Server 2022/2025 x64. Mac tests used Apple Silicon and Intel macOS 15. Other OS versions, physical keyboards, Retina rendering and enterprise policies need device testing.

Windows has no commercial Authenticode signature. macOS uses ad-hoc integrity signing without Developer ID/notarization. See [installation and first launch](../README.en.md#installation-and-first-launch). Existing safety, Mac runtime and Windows offline fixes remain included; historical commits, releases and assets remain, and license terms are unchanged.
