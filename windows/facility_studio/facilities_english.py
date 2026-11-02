"""English parity for the simplified workflows; storage remains Traditional Chinese."""
TEXT = {}
for row in """
AHU 模型差異核對	AHU model comparison
一般設計直接使用左側工具；AHU 核對僅用來比較兩個物性模型差異。	Use the tools on the left for design; AHU comparison evaluates differences between two property models.
液體與管材選擇	Liquids and pipe materials
保溫選用：	Insulation selection: 
管徑（外徑×管壁）	Pipe size (outside diameter x wall)
 Pa/m；路徑壓降 	 Pa/m; path pressure drop 
 Pa；水力功率 	 Pa; hydraulic power 
材料資料：	Material reference: 
絕對壓力	Absolute pressure
泵入口抽速 	Pump inlet speed 
此流態／管長未採用分子流導通率，需適用模型及沿程壓力資料。	Molecular conductance is inapplicable to this regime or tube length; use an appropriate model and pressure profile.
依明列基準之總供風換氣次數 	Total supply air changes at the stated basis 
 1/h；另需洩壓／排放 	 1/h; additional relief or discharge required 
保溫外表面 	Insulation outer surface 
°C；每米熱損／得熱 	C; heat loss or gain per metre 
導通率 	Conductance 
 L/s；有效抽速 	 L/s; effective pumping speed 
矩形風管參考鐵皮厚度：	Rectangular duct reference sheet thickness: 
計算管路保溫	Calculate pipe insulation
周圍空氣溫度	Ambient air temperature
周圍相對濕度	Ambient relative humidity
保溫導熱係數	Insulation thermal conductivity
外表面綜合熱傳係數	Combined external surface coefficient
防結露露點裕度	Condensation dew-point margin
每米允許熱損／得熱	Allowed heat loss or gain per metre
契約最小保溫厚度	Contract minimum insulation thickness
液體／純水管路	Liquid / pure water
清水、純水、冷卻液及化學液體；明列材料、實際內徑、物性、壓損與保溫。	Water, purified water, coolant and chemicals with explicit material, actual bore, properties, pressure loss and insulation.
PV 真空快算	PV vacuum calculator
在此頁輸入標準流量與真空絕壓，完成實際流量、管徑、流速與抽速限制檢查。	Enter standard flow and absolute vacuum pressure here to check actual flow, bore, velocity and pumping limits.
保溫計算用實際管外徑	Actual outside diameter for insulation
W/(m·K)；採材料平均使用溫度值	W/(m.K); use the value at mean operating temperature
W/(m²·K)；含對流與輻射，依現場確認	W/(m2.K); includes convection and radiation, verify on site
W/m；專案目標，非通用法規	W/m; project target, not a universal regulation
mm；依實際適用規範填寫，0表示未指定	mm; enter the applicable requirement, 0 means unspecified
mm；無可信外徑表時須填實測，不能以內徑代替	mm; enter measured outside diameter if no reliable table exists; do not substitute bore
外徑系列＋指定 SDR	Outside diameter series and specified SDR
指定外徑及管壁	Specified outside diameter and wall
標準氣體流量	Standard gas flow
管內真空絕對壓力	Absolute vacuum pressure in pipe
氣體操作溫度	Gas operating temperature
所在地大氣絕壓	Local atmospheric absolute pressure
標準流量參考絕壓	Standard-flow reference absolute pressure
管徑模式	Diameter mode
依流速初估	Preliminary sizing by velocity
本案流速警戒	Project velocity warning limit
工況泵入口抽速	Pump inlet speed at operating pressure
供應商物性	Supplier properties
乙醇	Ethanol
甲醇	Methanol
丙酮	Acetone
輸送介質	Conveyed medium
管路材質	Pipe material
液體操作溫度	Liquid operating temperature
液體絕對壓力	Liquid absolute pressure
介質質量濃度	Medium mass concentration
依介質模型	Medium property model
操作工況密度	Operating density
操作工況比熱	Operating specific heat
操作工況動力黏度	Operating dynamic viscosity
物性資料與適用條件	Property reference and applicable conditions
管徑選擇方式	Pipe geometry selection
採用管外徑／管壁 SDR	Selected outside-diameter to wall ratio SDR
管路外徑	Pipe outside diameter
最小實際管壁	Minimum actual wall thickness
本案摩擦壓損警戒	Project friction-gradient warning limit
管內絕對粗糙度	Internal absolute roughness
最不利路徑直管長	Critical-path straight length
管件阻力係數總和	Sum of fitting loss coefficients
下方明列標準狀態氣體量，不是管內實際量	Gas flow at the standard conditions stated below, not actual pipe flow
°C；目前導通率僅空氣模型	C; conductance currently applies to air only
m/s；分子流不得僅憑流速核准管徑	m/s; molecular-flow sizing cannot be approved by velocity alone
m；導通率模型不含彎頭及閥件	m; conductance excludes bends and valves
L/s；須採原廠工作壓力對應曲線	L/s; use the vendor curve at operating pressure
kPa(abs)；用於物性，不代表管材承壓通過	kPa(abs); used for properties, not approval of pipe pressure rating
%；乙／丙二醇水溶液模型採質量百分比	%; glycol solution models use mass percent
Pa·s；不是 cSt	Pa.s; not cSt
供應商／SDS／測試依據，註明濃度與溫度	Supplier, SDS or test reference with concentration and temperature
純幾何初估，須依管材型錄確認	Geometric estimate only; verify against the pipe catalogue
mm；不可填公稱英吋值	mm; do not enter nominal inch size
m/s；非所有化學液體通用安全流速	m/s; not a universal safe velocity for all chemicals
mm；新塑膠管初估，依實際狀態修正	mm; estimate for new plastic pipe, adjust for actual condition
進階工程設定	Advanced engineering settings
乙二醇水溶液	Ethylene glycol solution
丙二醇水溶液	Propylene glycol solution
IPA 異丙醇	IPA isopropanol
污水／混合廢液	Wastewater or mixed waste liquid
鹽酸	Hydrochloric acid
硫酸	Sulfuric acid
氫氟酸	Hydrofluoric acid
氫氧化鈉	Sodium hydroxide
過氧化氫	Hydrogen peroxide
自訂液體	Custom liquid
金屬；耐蝕、焊接、鈍化及潔淨度須依介質確認	Metal; verify corrosion, welding, passivation and cleanliness for the medium
GF PVC-U 參考；升溫必須依產品壓溫曲線降額	GF PVC-U reference; apply product pressure-temperature derating at elevated temperature
須分辨硬質 PVC-U 與含塑化劑軟管，不能只依 PVC 名稱判定	Distinguish rigid PVC-U from plasticized tubing; the PVC name alone is insufficient
CPVC 管材、接著劑、密封件及濃度／溫度須共同查表	Check CPVC pipe, cement, seals, concentration and temperature together
高純度／化學管路候選；實際管壁、滲透及壓溫須依型錄	Candidate for high-purity or chemical service; verify wall, permeation and pressure-temperature rating
GF SYGEF 材料溫區參考，不是任何壓力均可使用	GF SYGEF material temperature reference; not approval at arbitrary pressure
聚酯／聚醚 PU 不可混用；部分聚酯 PU 不建議用於水溶液	Do not interchange polyester and polyether PU; some polyester PU is unsuitable for aqueous solutions
須明確 PP-H／PP-R 等級及產品壓溫、焊接與介質相容性	Specify PP-H or PP-R grade and verify pressure-temperature rating, welding and compatibility
樹脂耐化資料不等於承壓管認證；須指定管材牌號與壓溫資料	Resin chemical resistance is not pressure-pipe certification; specify product grade and pressure-temperature data
材料相容性及承壓待原廠按介質、濃度、溫度、管壁與密封件確認，未自動判為相容。	Vendor confirmation of compatibility and pressure rating is required for the medium, concentration, temperature, wall and seals; compatibility is not automatically approved.
標準流量折算與流速僅為定寸初估；不是泵浦抽速或管網壓降認證。	Standard-flow conversion and velocity provide preliminary sizing only, not approval of pumping speed or network pressure drop.
分子流長直圓管（空氣）	Molecular flow in a long straight round tube (air)
防結露＋明填每米熱損／得熱上限＋明填契約最小厚度；非宣稱現行法規最小厚度	Condensation control plus explicit heat-flow and contract-thickness limits; not a claim of current statutory minimum thickness
物性必須為有限正值	Properties must be finite and positive
外徑系列與 SDR 僅作幾何初估；須按指定材料型錄的最小管壁、實際內徑及壓溫曲線確認，不能當成採購或承壓認證。	Diameter series and SDR provide geometric estimates only. Verify minimum wall, actual bore and pressure-temperature rating in the specified catalogue; this is not a procurement or pressure approval.
管壁須小於外徑一半	Wall thickness must be less than half the outside diameter
液體溫度超出所引用材料產品的參考溫區。	Liquid temperature exceeds the referenced material product's temperature range.
水力物性可用純水模型；高純度適用性仍須材料溶出、表面、焊接及水質驗收，不能由流速判定。	Pure-water properties may be used for hydraulics; high-purity suitability still requires extractables, surface, weld and water-quality acceptance, not a velocity check.
本模式限加壓、滿管、均質牛頓流體；含固體／非牛頓廢液與重力排水不得採用此定寸結果。	This mode requires pressurized full-pipe homogeneous Newtonian flow. Do not use it for solids, non-Newtonian waste or gravity drainage.
保溫條件不可達，不能採用厚度。	Insulation conditions are infeasible; no thickness may be adopted.
內徑＝外徑−2×管壁；v=Q/A；ΔP=(fL/D+ΣK)ρv²/2。	Bore=outside diameter-2xwall; v=Q/A; deltaP=(fL/D+sumK)rho*v^2/2.
流量、管徑、水力及保溫在同一頁完成。數值模型未涵蓋腐蝕、磨蝕、結垢、氣液兩相、泵汽蝕與管材壓溫額定。	Flow, dimensions, hydraulics and insulation are calculated on the same page. Corrosion, erosion, fouling, two-phase flow, cavitation and pipe pressure-temperature rating are outside this model.
PV 必須填低於所在地大氣壓的絕對壓力，不可填表壓或真空度百分比。	PV requires absolute pressure below local atmospheric pressure, not gauge pressure or percent vacuum.
依流速反算管徑超過 3000 mm，已超出初估範圍；請核對標準流量與真空絕壓，或指定實際內徑作抽速校核。	Velocity sizing exceeds 3000 mm and the estimate range. Check standard flow and absolute vacuum pressure, or enter the actual bore to review pumping speed.
黏滯流；需沿程壓力及層流／紊流校核	Viscous flow; review pressure profile and laminar or turbulent regime
過渡流或短管；須使用適用導通率模型	Transition flow or short tube; an applicable conductance model is required
指定氣載所需實際抽速大於管路有效抽速，無法維持所填工作壓力。	Required pumping speed for the specified gas load exceeds effective speed; the specified pressure cannot be maintained.
Qactual=Qstd×Pstd/Pabs×T/Tstd；分子流長直圓管 C=12.1d³/L（cm、L/s、空氣20°C）；1/Seff=1/Sp+1/C。	Qactual=Qstd*Pstd/Pabs*T/Tstd; long round molecular-flow tube C=12.1d^3/L (cm, L/s, air at 20C); 1/Seff=1/Sp+1/C.
PV 在簡易工具內完成，不切換工作台。導通率只限明列適用條件；特氣／混合氣、管件與真空外壓強度另核。	PV runs in the simple tools without switching workbench. Conductance applies only under the stated conditions; specialty gases, mixtures, fittings and external-pressure strength require separate review.
參考選用，非施工核准	Reference selection, not construction approval
內政部106年排煙研究表4.2／4.3中壓參考；須連同補強間距、接縫、正負壓與契約SMACNA表確認。不能套用到腐蝕、排煙耐火或任意圓管構造。	Ministry of Interior year 106 smoke-exhaust research, tables 4.2/4.3, medium-pressure reference. Verify reinforcement spacing, joints, positive/negative pressure and contract SMACNA schedules. Not applicable to corrosive service, smoke fire resistance or arbitrary round construction.
超出 200 mm 搜尋範圍／無可行保溫厚度	Beyond the 200 mm search range or no feasible insulation thickness
以管外表面等於液體溫度保守估算；外表面熱傳係數須含對流與輻射；另須防潮層、接縫、支架熱橋與材料額定溫度確認。	Conservatively assumes pipe outer surface at liquid temperature. The external coefficient includes convection and radiation. Verify vapor barrier, seams, support thermal bridges and material temperature rating separately.
化學液體與混合廢液須填物性來源及適用溫度／濃度，不能沿用水物性。	Chemicals and mixed waste require a property reference at the applicable temperature and concentration; water properties cannot be substituted.
 m/s 超過本案上限 	 m/s exceeds the project limit 
 m/s；須放大管徑或調整工況。	 m/s; increase diameter or revise operating conditions.
分子流中平均漂移流速不可用來核准管徑；應以導通率及有效抽速重新選管。	Mean drift velocity cannot approve molecular-flow sizing; use conductance and effective pumping speed.
外徑 	Outside diameter 
所填溫壓不是液相	Specified temperature and pressure are not liquid phase
液體物性模型不適用此溫壓／濃度：	Liquid property model is inapplicable at this temperature, pressure or concentration: 
管路保溫選用	Pipe insulation selection
初估，須契約／防潮及熱橋覆核	Preliminary; review contract, vapor barrier and thermal bridges
管壁厚度	Pipe wall thickness
工況密度	Operating density
工況比熱	Operating specific heat
雷諾數	Reynolds number
流態及模型適用性	Flow regime and model applicability
保溫厚度	Insulation thickness
保溫外表面溫度	Insulation outer surface temperature
每米熱損／得熱	Heat loss or gain per metre
管路導通率	Pipe conductance
有效抽速	Effective pumping speed
另需洩壓／排放量	Additional relief or discharge flow required
明列基準總供風換氣次數	Total supply air changes at the stated basis
採用 ACH（基準見條件）	Selected ACH (see stated basis)
矩形風管鐵皮選用厚度	Rectangular duct sheet thickness selection
板厚為明列來源的中壓矩形風管參考；須另核補強、接縫、壓力等級與契約規範，不自動核准施工。	Thickness is a medium-pressure rectangular-duct reference from the stated source. Review reinforcement, joints, pressure class and contract specification; construction is not automatically approved.
設計風速超過本案 10 m/s 提醒值，請覆核噪音、用途與壓損；此值不是通用法規上限。	Design velocity exceeds the project advisory value of 10 m/s. Review noise, service and pressure drop; this is not a universal statutory limit.
另需洩壓／回風排放 	Additional relief or return discharge required 
 CMH；未設排放路徑時，不能保證指定室壓。	 CMH; specified room pressure is not assured without a discharge path.
PV 留在簡易工具，未建立完整工作台	PV stays in the simple tools without creating a workbench
真空換單位保持原絕壓	Vacuum unit changes preserve absolute pressure
工程單位換算合併至同一頁	Engineering conversion uses one page
材料與液體計算留在簡易頁	Material and liquid calculations stay on the simple page
高流速在同頁警告	High velocity warns on the same page
化學液體缺物性不沿用水	Missing chemical properties do not fall back to water
具來源之液體物性參與計算	Referenced liquid properties participate in calculation
變更物性工況必須重新確認來源	Changed operating conditions require renewed property reference
GEMINI 案例總風不重複	GEMINI case does not double-count total supply
超額外氣洩壓量明列	Excess outdoor-air relief is explicit
風管板厚聯動至選管結果	Duct sheet thickness follows selected dimensions
液體頁保溫聯動成功	Liquid-page insulation is linked
 計算與匯出按鈕可用	 Calculation and export actions available
 既有核心仍可計算	 Existing core remains calculable
合成案例20°C20wt%	Synthetic case 20C20wt%
_簡易工具.png	_simple_tools.png
濕空氣計算模型	Psychrometric model
盤管熱質平衡模型	Coil heat and mass model
熱物性模型	Thermophysical model
流體壓損模型	Fluid pressure-loss model
工程單位換算	Engineering unit conversion
Facility Studio 五庫融合測試版	Facility Studio Test Edition
Facility Studio 測試版	Facility Studio Test Edition
五庫核心融合	Engineering calculations
工程計算	Engineering calculations
純水溫壓物性	Water properties at specified temperature and pressure
幾何盤管性能計算	Geometric coil performance calculation
測試版	Test edition
五庫融合	Engineering calculations
""".strip('\n').splitlines():
    source, translated = row.split('\t', 1)
    TEXT[source] = translated.replace('v^2', 'v²').replace('d^3', 'd³').replace('m2.', 'm².')

TEXT.update({
    '冷熱水流量帶入液體原頁': 'Water flow transfers into the existing liquid page',
    '上游水量改動阻擋過期液體匯出': 'Upstream flow changes block stale liquid exports',
    '明確重新帶入後液體流量恢復': 'Explicit reimport restores current liquid flow',
    '查看設計參考資料': 'View design reference',
    '冷熱水採用確認之外徑作保溫': 'Heating and cooling water insulation uses the confirmed outside diameter',
    '變更自動選管條件使舊外徑失效': 'Changing automatic sizing conditions invalidates the previous outside diameter',
    '液體絕壓 ': 'Liquid absolute pressure ',
    ' kPa(abs)；質量濃度 ': ' kPa(abs); mass concentration ',
    '%；流速警戒 ': '%; velocity limit ',
    '流速警戒 ': 'Velocity limit ',
    ' m/s；壓損警戒 ': ' m/s; friction-gradient limit ',
    '保溫使用的管外徑必須大於目前所選管內徑；管徑變更後請重新確認外徑。': 'Insulation outside diameter must exceed the selected bore; reconfirm outside diameter after changing pipe size.',
    '標準流量參考 ': 'Standard-flow reference ',
    ' Pa(abs)；操作 ': ' Pa(abs); operating ',
    '°C；所在地大氣 ': 'C; local atmosphere ',
    ' Pa(abs)；直管長 ': ' Pa(abs); straight length ',
    '保溫設計條件：周圍 ': 'Insulation design conditions: ambient ',
    ' W/(m²·K)；露點裕度 ': ' W/(m².K); dew-point margin ',
    ' K；熱損上限 ': ' K; heat-flow limit ',
    ' W/m；契約厚度下限 ': ' W/m; contract minimum thickness ',
})
