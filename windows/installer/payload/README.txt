廠務簡易工具 V5.5.4｜通用版｜2026-10-05

本版更新
• 右側數字鍵盤小數點統一輸入「.」，支援選取文字取代；一般Delete及左側小數點保留正常行為。
• 溫度差與溫度分開說明；Kv／Cv明列為閥門通流係數，不是管徑。
• 空氣狀態工具直接顯示即時線圖、RH曲線及目前點位；無效輸入會清除舊點位。
• 照明體積模式明列「m³ ÷ 同一空間淨高＝地板面積m²」；切換面積／坪／長寬／體積保持同一面積。
• 新增設備表範本與Excel／CSV匯入：電力、PCW、CDA、N2、EXHAUST、DI、PV。
首頁四項工具及完整工程工作台保留。新版驗證詳Changes_and_Verification.html與evidence。

安裝與開啟
1. 解壓縮 Facility_Studio_V5_5_4_OneClick.zip。
2. 雙擊 Facility_Studio_V5_5_4_Setup.exe。
3. 首次安裝保持連網，等候建立程式及桌面FY圖示捷徑。
4. 從「Facility Studio V5.5」開啟，畫面應顯示V5.5.4。日常計算可離線使用。

Setup.exe是Windows線上安裝器，會下載官方Python 3.13.15 x64與套件，在您的Windows建立應用EXE。目標Windows 10/11 Intel/AMD x64。本次完成Linux數值、真實Tk視窗及Windows PE安裝器檢查；尚未完成Windows實機安裝驗收。
原有Projects／Examples保留。安裝記錄：%LOCALAPPDATA%\Facility_Studio_V5_5\Setup.log；Python安裝記錄：bootstrap\Python_Setup.log。

先選工具，不必先建立廠房
首頁只有電力、風管、CDA／特氣、照明，各自獨立計算，預設值摘要保持可見。

電力配線
填設備kW，選供電及使用方式，得NFB候選、每相銅線與電流。支援單相110／220V、三相208／220／380／400／480V。
kW是電氣輸入；馬達銘牌軸功率不能直接當輸入功率。
預設PF=0.85、單程30m、XLPE、端子60°C、環溫35°C、同管3根、壓降上限3%，進階可改。
I三相=P×1000/(√3VPF)；I單相=P×1000/(VPF)。連續／馬達初估採125%；候選需設計電流≤AT≤有效載流量，並核配線壓降。
原專案線表僅初估，缺75°C端子表時保守採60°C表。馬達啟動、獨立過載、接地、中性線、短路及保護協調另核。

風管尺寸
填風量與可用管路靜壓，同時列方管、圓管及各自實際風速。預設風速上限8m/s、寬高比上限2，進階可改。
靜壓不能唯一決定尺寸；基本結果只定寸，不宣告壓力足夠。
已知路徑時，可勾選進階檢查並填直管長度、ΣK及設備壓降，再比較路徑阻力與可用靜壓。各段視為同一尺寸；ΣK=4、設備100Pa是待確認的起點值。
A=CMH/3600/v；圓D=√(4A/π)；方管Dh=2WH/(W+H)。阻力=fL/Dh×ρv²/2+ΣK×ρv²/2+設備壓降。v由實際面積計算，方管50mm、圓管2英吋級距。
可用管路靜壓應先扣除不包含於本路徑的機組內部阻力；這不是完整風機性能選型。

CDA／特氣管徑
填標準流量、管內表壓及流速上限，得參考管徑、ALPM及實際管速。僅壓力和流速不能算管徑。
CDA預設15m/s、N2／Ar參考12m/s；手動修改流速後切氣體會保留自訂值。
支援SLPM／SCFM／Sm³/h與bar(g)／kPa(g)／kgf/cm²(g)／MPa(g)，切單位保持物理量。
預設管內／標準溫度25°C、標準壓力101.325kPa(abs)、Z=1；進階可改標準溫度等條件，須與原廠流量基準一致。
Q實際=Q標準×P標準/(P大氣+P表壓)×T管內(K)/T標準(K)；D內=√(4Q實際/πv)。
參考內徑須與實供材質核對；長管路另算可壓縮壓降，危險氣體材質及控制系統需正式設計。

照明照度
「估算照度」填空間面積、每盞W及盞數，得平均Lux與用電。
「反算燈數」填目標Lux，得向上取整盞數及採用後照度。
空間可填m²、坪、長×寬，或m³配合淨高；照度使用地板面積。
預設LED光效100lm/W、利用率U=0.6、維護M=0.8，進階可改係數或填型錄每盞lm。
平均Lux=盞數×每盞lm×U×M/面積m²。
Lux是空間照度，燈具光通量單位是lm；瓦數不能直接等於流明。此為平均照度初估，未核均勻度、眩光及配光。

更多工具
• 冷熱水：水量／熱量與溫差→水量、管徑、水速、kW、US RT。ρ=1000kg/m³、cp=4.1868kJ/(kg·K)、預設水速1.5m/s，未算泵揚程。
• 空氣狀態／線圖：乾球與RH→濕球、露點、焓、含濕比及即時點位，曲線隨當地大氣壓更新。RH=0%不捏造有限露點。
• 單位換算：溫度差換算升降溫幅度，5°C差＝5K＝9°F差，不加32或273.15；溫度本身另外換算。
• 閥門流量係數：Kv是水在壓差1bar下的m³/h；Cv(US)是水在壓差1psi下的US GPM，Kv≈0.865Cv。通常查閥門型錄。
• 其餘換算：風量、水量、壓力、冷熱功率、長度。壓力只換單位，保持原表壓／絕壓基準。

設備表匯入（右上角）
1. 按「設備表匯入」→「1 匯出Excel範本」，或直接開懶人包內的Equipment_Template.xlsx。
2. 閱讀「填寫說明」，各系統填實際設備；要納入的設備設「啟用(1/0)」為1。範例預設0，不會混入需求。
3. 功率、流量及插座填每台資料，台數另填。同一設備可在不同系統使用相同編號；同一系統不得重複。
4. 「2 匯入設備表」會讀七張Excel工作表。CSV每檔一個系統，先選CSV系統再開檔。
5. 上表按供應群組分開彙總；點選一列可看條件、公式與設備明細。下方可匯出全部TXT／數值JSON。
Excel預留100列。更多設備請在下方「欄位／填寫提示」之前插入設備列，最多每系統10,000筆；整列排序，保留工作表名與第5列欄名。
黃色欄填實際值；灰色欄只做原單位初算。程式重新計算，忽略灰色欄公式快取。輸入欄公式需貼上值，巨集／.xls不接受。
必填欄空白會指出系統、列號及欄位；零與空白分開。選填欄帶入預設時，明細列出採用值。
同時使用率是瞬間需求初估係數，非每小時開機分鐘比例。全開需求另列；安全排氣與常時供應量需另核同時率依據。

設備表各系統的結果
電力：按配電盤、相數及電壓分組。合計P與Q後算S，不能把各設備電流或kVA無條件相加。插座數僅統計點位，不再乘功率。
支路依單台額定功率；盤進線候選按同時需求、連續負載125%、馬達群最大單台25%初估，且不低於同時率>0的最大單台支路設計電流。
進線壓降採設計電流與R/X阻抗上界保守初估；進線距離暫採組內最大已填距離。正式進線需核實際路徑。
輸出總連接／同時kW、分組kVA、電流、NFB／線徑候選、支路候選及插座數；不同電壓分開列，未合併成總盤電流。
PCW：單台水量×台數×同時率，各列溫差分別算熱量再加總；列主管水量、熱量及參考管徑。
CDA／N2：支援標準量與ALPM；統一標準流量溫壓後加總，再依最低管內絕壓、最高溫度、最低流速上限定寸。不同壓力級次需核減壓與供應架構。
EXHAUST：一般／酸／鹼／有機／熱排分開。列方管、圓管及已知設備端最高靜壓。設備靜壓未填仍保留未知，不當成0Pa，也不相加成風機ESP。
DI：製程需求可乘同時率；額外持續循環量按台數納入、不折減。列實際內徑需求，未套碳鋼名目管徑。
PV：支援Torr(abs)／kPa(abs)／mbar(abs)，模型限1~760Torr；列標準量、實際量、管徑初估及製程端有效抽速，未完成真空導通與泵曲線選型。
尚未自動完成正式盤體尺寸、短路遮斷容量、相別分配、接地、全管網壓損或原廠選型。
設備表分析獨立於完整工作台，不暗中覆寫既有主案。

操作方式
改數值後自動計算，或按計算／F5。各工具保留本次開啟期間輸入；恢復預設只重設目前工具。
結果可複製或匯出簡短TXT，包含本工具條件、結果、公式及範圍。錯誤輸入會立即清除舊結果、停用匯出並指出欄位。
常用輸入保持可見，其餘放在「調整預設值／進階條件」。小視窗可捲動，主要按鈕固定在底部。

完整工程工作台
右上角入口保留主案、多台空調箱、夏冬逐段預熱／預冷／水洗／再冷／再熱、回收熱水／電熱／並用、蒸汽與電極給水、純水、真空、壓損矩陣、來源、A/B、整案儲存及復原。
簡易工具不暗中改主案。要回傳主案，使用完整工作台內既有工程快算與回傳預覽。
主案有未儲存資料時，關閉簡易工具仍會詢問是否保存主案。
原工程邊界保留：需求線圖不是原廠盤管選型，水洗循環量及設備阻力需原廠資料；水質是規格紀錄，非產水保證。
冬季是明列負荷的穩態模型，未包含逐時氣象、熱蓄積或完整多區耦合。來源註記不驗證文件真偽；A/B不自動評判方案。
測試通過不表示正式廠房設計已核准。

原始碼與驗證
Source_and_Verification.zip包含全部程式、工程表、FY圖示、測試、數值JSON、案例報告及截圖。
入口Facility_Studio_V5_5.py與facility_studio資料夾必須放在一起。
CMD（已有Python 3.13 x64）：
  cd /d "你的解壓縮資料夾"
  py -3.13 -m pip install "matplotlib>=3.8,<4"
  py -3.13 Facility_Studio_V5_5.py
匯出設備範本：
  py -3.13 Facility_Studio_V5_5.py --export-equipment-template "Equipment_Template.xlsx"
設備表分析：
  py -3.13 Facility_Studio_V5_5.py --equipment "你填好的設備表.xlsx" --report "Equipment_Demand.txt" --result "Equipment_Demand.json"
直接開完整工作台：
  py -3.13 Facility_Studio_V5_5.py --full
獨立電力工具：
  py -3.13 Facility_Studio_V5_5.py --tool electrical --report power.txt --result power.json
測試：tests\simple_features.py、tests\simple_gui.py，以及既有regression.py、v55_features.py、v552_core.py、gui_features.py、v551_fixes.py、v552_interactions.py、packaging_checks.py。
自動建立Windows應用EXE：雙擊installer\START.cmd。外層Setup.exe重建另需NSIS 3.x，再執行build_release.py。
手動建立Windows EXE：
  py -3.13 -m pip install "pyinstaller>=6,<7" "matplotlib>=3.8,<4"
  py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed --name Facility_Studio_V5_5_4 --icon facility_studio\resources\app.ico --add-data "facility_studio\resources:facility_studio/resources" --hidden-import matplotlib.backends.backend_tkagg --collect-submodules facility_studio Facility_Studio_V5_5.py

依據與記錄
工程表是原專案初估表，以下用於核對公式，不宣稱已符合完整法規。
濕空氣／PsychroLib：https://psychrometrics.github.io/psychrolib/_modules/psychrolib.html
風管／ASHRAE：https://handbook.ashrae.org/Handbooks/F17/SI/f17_ch21/f17_ch21_si.aspx
保護與載流關係／Schneider Electric：https://www.se.com/us/en/faqs/FAQ000283711/
Python：https://www.python.org/downloads/release/python-31315/
PyInstaller：https://pyinstaller.org/en/stable/usage.html
溫度差／NIST：https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-8
Kv／Cv／Spirax Sarco：https://www.spiraxsarco.com/learn-about-steam/control-hardware-electric-pneumatic-actuation/control-valve-sizing-for-water-systems
標準與實際壓縮空氣流量／NRCan：https://natural-resources.canada.ca/energy-efficiency/energy-star/energy-efficiency-reference-guide-compressed-air
各項實際結果見Changes_and_Verification.html與evidence。安裝器無商業程式碼簽章。
DESIGNED BY ANDY HUANG ©
