"""Reviewed English display messages. Chinese values remain the storage schema."""

TEXT = {}


def _add(rows):
    for row in rows.strip("\n").splitlines():
        key, value = row.split("\t", 1)
        TEXT[key.replace("\\n", "\n")] = value.replace("\\n", "\n")


_add("""
無需求	No demand
管內表壓	Pipe gauge pressure
一般設備	General load
組	 sets
連續運轉	Continuous load
馬達	Motor
水量	Water flow
方管	Rectangular duct
圓管	Round duct
熱量 kW	Heat load (kW)
流量 LPM	Flow (LPM)
流量 m³/h	Flow (m³/h)
壓差 bar	Pressure drop (bar)
風量	Airflow
乾球＋RH	Dry bulb + RH
溫差 K	Temperature difference (K)
乾球＋濕球	Dry bulb + wet bulb
乾球＋露點	Dry bulb + dew point
焓＋含濕比	Enthalpy + humidity ratio
含濕比 g/kg乾空氣	Humidity ratio (g/kg dry air)
計算	Calculate
複製結果	Copy results
請修正「	Correct “
無有限露點	No finite dew point
維護係數 M	Maintenance factor M
管內氣體溫度	Gas temperature in pipe
長度	Length
設計風速上限	Maximum design air velocity
溫度含零點位移；壓力換算保持原有表壓／絕對壓基準	Temperature conversions include the zero-point offset. Pressure conversions preserve the gauge or absolute basis.
電力配線	Electrical sizing
輸入設備kW，查看NFB候選、每相線徑與電流。	Enter equipment input kW to estimate a circuit breaker (NFB), conductor size per phase and current.
風管尺寸	Duct sizing
輸入風量與可用靜壓，同時查看方管、圓管。	Enter airflow and available static pressure to compare rectangular and round ducts.
CDA／特氣管徑	CDA / gas piping
壓力填管內壓力表讀值；流量、壓力、流速一起決定管徑。	Enter pipe gauge pressure. Flow, pressure and velocity together determine the required internal diameter.
照明照度	Lighting
填空間與燈具，估平均Lux；也可用目標Lux反算幾盞燈。	Enter room and luminaire data to estimate average illuminance, or size the luminaire count for a target lux level.
冷熱水快算	Water / heat load
已知水量或熱量，就能估管徑、水速、冷熱容量。	Use water flow or heat load to estimate pipe size, water velocity and thermal capacity.
空氣狀態／線圖	Psychrometrics
填乾球與濕度，數值及線圖點位即時更新；曲線依目前大氣壓計算。	Enter dry-bulb temperature and RH. Properties and the chart point update live at the selected atmospheric pressure.
單位換算	Unit converter
選物理量、填數值與原單位，即可查看其他常用單位。	Choose a quantity, enter a value and its unit, then read the equivalent values.
採用：PF 	Assumptions: PF 
｜銅線	 | Copper 
｜單程	 | One-way length 
m｜環溫	m | Ambient 
°C｜端子	°C | Terminal 
°C｜同管	°C | Loaded conductors in conduit: 
根｜壓降≤	 | Voltage drop ≤ 
採用：風速≤	Assumptions: air velocity ≤ 
m/s｜寬高比≤	m/s | Aspect ratio ≤ 
｜方管50mm、圓管2英吋級距｜	 | Rectangular: 50 mm increments; round: 2 in increments | 
採用：管內	Assumptions: gas temperature 
°C｜標準流量	°C | Standard flow reference 
kPa(abs)｜理想氣體Z=1	kPa(abs) | Ideal gas, Z = 1
採用：	Assumptions: 
｜利用率U=	 | Utilization U = 
｜維護M=	 | Maintenance M = 
｜均勻一般照明初估	 | Uniform general-lighting estimate
採用：水速≤	Assumptions: water velocity ≤ 
m/s｜清水ρ=1000、cp=4.1868｜依實際參考內徑選型	m/s | Water ρ = 1000, cp = 4.1868 | Sizing uses reference internal diameters
採用：大氣壓	Assumptions: atmospheric pressure 
kPa(abs)，以kg乾空氣為基準	kPa(abs), per kg of dry air
估算照度	Estimate illuminance
反算燈數	Size luminaire count
長×寬	Length × width
體積 m³	Volume (m³)
LED功率初估	Estimate from LED watts
燈具型錄流明	Manufacturer lumens
已知水量	Known water flow
已知熱量	Known heat load
lm/W初估	Estimated lm/W
型錄	Manufacturer data
lm/盞	lm per luminaire
設備用電功率	Electrical input power
供電方式	Power supply
三相 380V	Three-phase 380 V
三相 220V	Three-phase 220 V
三相 208V	Three-phase 208 V
三相 400V	Three-phase 400 V
三相 480V	Three-phase 480 V
單相 220V	Single-phase 220 V
單相 110V	Single-phase 110 V
使用方式	Load type
功率因數 PF	Power factor PF
單程配線距離	One-way cable length
銅線絕緣	Copper cable insulation
設備端子溫度	Terminal temperature rating
周圍溫度	Ambient temperature
同管載流導線數	Loaded conductors in conduit
允許電壓降	Maximum voltage drop
需要的風量	Required airflow
可用管路靜壓	Available duct static pressure
方管寬高比上限	Maximum rectangular aspect ratio
我已知路徑，檢查壓力預算	Check a known duct path
最不利路徑直管長度	Critical-path straight length
管件阻力係數加總	Sum of fitting loss coefficients
設備及末端壓降	Equipment / terminal pressure drop
氣體	Gas
所需標準流量	Required standard flow
設計流速上限	Maximum design velocity
所在地大氣壓	Local atmospheric pressure
標準流量參考溫度	Standard-flow reference temperature
標準流量參考壓力	Standard-flow reference pressure
我要計算	Calculation mode
我手上的空間資料	Room measurement method
面積 m²	Area (m²)
面積 坪	Area (Taiwan ping)
空間面積	Room area
空間長度	Room length
空間寬度	Room width
同一空間的淨高（m）	Clear height of the same room (m)
每盞燈具功率	Power per luminaire
已裝燈具數量	Installed luminaire count
目標平均照度	Target average illuminance
燈具流明來源	Source of luminaire lumens
LED初估光效	Estimated LED efficacy
型錄每盞光通量	Manufacturer lumens per luminaire
照明利用率 U	Utilization factor U
我已知道	Known quantity
循環水量	Circulating water flow
冷熱負荷	Heating / cooling load
供回水溫差	Supply / return temperature difference
設計水速上限	Maximum design water velocity
空氣乾球溫度	Air dry-bulb temperature
相對濕度	Relative humidity
要換算什麼	Quantity to convert
原數值	Input value
原單位	Input unit
已啟用路徑阻力檢查	Path resistance check enabled
僅定寸，靜壓是否足夠待路徑資料	Sizing only; pressure adequacy needs path data
kW，填電氣輸入功率	kW; enter electrical input power
m；壓降計算會自動處理相數	m; voltage drop calculation accounts for the phase count
m/s；噪音與用途會影響取值	m/s; select for the application and noise limit
m；此路徑各段視為相同尺寸	m; this estimate assumes one size along the path
ΣK；依實際彎頭與管件確認	ΣK; confirm for the actual elbows and fittings
Pa；包含此路徑的濾網、風口等	Pa; include filters, outlets and other path equipment
m/s；CDA初估15，N2／Ar初估12	m/s; starting estimates: CDA 15, N2 / Ar 12
°C，應與原廠流量基準一致	°C; match the manufacturer's flow reference
依上方選擇，填m²、坪或m³	Enter m², Taiwan ping or m³ as selected above
只用來將m³換算為m²；請填同一空間的淨高。	Used only to convert volume to floor area. Enter this room's clear height.
盞	 luminaires
lm/W，初估假設，非燈具保證值	lm/W; an estimate, not a guaranteed luminaire value
lm；燈具不是用Lux標示光通量	lm; luminaire light output is measured in lumens, not lux
°C溫差	°C temperature difference
輸入已變更，等待計算…	Inputs changed. Recalculating…
廠務簡易工具 V5.5.5	Facility Studio V5.5.5
更多工具…	More tools…
各工具獨立計算	Each tool calculates independently
匯出TXT	Export TXT
已複製本工具結果	Results copied
地板照明面積（m²）	Illuminated floor area (m²)
地板照明面積（坪）	Illuminated floor area (Taiwan ping)
空間體積（m³，立方公尺）	Room volume (m³)
地板照明面積＝	Illuminated floor area = 
m³ ÷ 淨高	m³ ÷ clear height 
已匯出本工具結果	Results exported
未能匯出	Export failed
啟用此路徑檢查	Enable this path check
恢復本工具預設	Reset tool defaults
公式：	Formula: 
已計算｜路徑壓力預算不足，請核對	Calculated | Path pressure budget is insufficient; review required
已計算｜本工具可獨立使用，結果為初估	Calculated | Independent preliminary estimate
輸入	Input
其他常用快算	More quick tools
選工具 → 填條件 → 看結果	Choose a tool → Enter data → Read results
完整工程工作台	Full workbench
設備表匯入	Equipment schedules
調整預設值／進階條件	Adjust defaults / advanced settings
冷熱功率	Thermal power
填地板面積。例如長6m×寬5m＝30m²；不需填淨高。	Enter floor area, e.g. 6 m × 5 m = 30 m². Clear height is not required.
填地板坪數，1坪＝3.305785m²；不需填淨高。	Enter floor area in Taiwan ping (1 ping = 3.305785 m²). Clear height is not required.
這格填m³，不是m²。例：90m³ ÷ 淨高3m＝地板照明面積30m²。	Enter volume in m³. For example, 90 m³ ÷ 3 m clear height = 30 m² floor area.
文字結果	Text results
輸入條件	Input conditions
公式	Formula
採用範圍	Scope / assumptions
廠務簡易工具 5.5.5｜	Facility Studio 5.5.5 | 
結果	Results
NFB候選	Circuit breaker (NFB)
每相銅線	Copper conductor per phase
運轉電流	Operating current
設計電流 	Design current 
AT ≤ 有效載流 	AT ≤ effective ampacity 
單程 	One-way length 
m｜電壓降 	m | Voltage drop 
線徑	Conductor size
電流	Current
設計風量	Design airflow
方管實際風速 	Rectangular air velocity 
m/s｜圓管 	m/s | Round duct 
m/s｜上限 	m/s | Limit 
可用管路靜壓 	Available duct static pressure 
未核總路徑阻力，不把靜壓數字當成風管或風機已合格。	Total path resistance has not been checked. Static pressure alone does not verify a duct or fan selection.
是	Yes
否	No
預算足夠	Within pressure budget
預算不足	Pressure budget insufficient
參考管徑	Reference pipe size
實際流量	Actual flow
管內流速	Pipe velocity
標準流量 	Standard flow 
 SLPM｜最低所需內徑 	 SLPM | Minimum internal diameter 
管內表壓 	Pipe gauge pressure 
bar(g)｜絕對壓 	bar(g) | Absolute pressure 
路徑阻力 	Path resistance 
Pa｜餘壓 	Pa | Pressure margin 
參考內徑 	Reference internal diameter 
mm；內徑與材料依實供產品核對。	mm; verify internal diameter and material against the supplied product.
平均照度	Average illuminance
燈具數量	Luminaire count
照明用電	Lighting power
照明面積 	Illuminated area 
m²｜每盞 	m² | Per luminaire 
流明來源：	Lumens source: 
目標 	Target 
Lux；盞數向上取整後採用上述平均照度。	Lux; the displayed illuminance uses the rounded-up luminaire count.
冷熱容量	Thermal capacity
容量 	Capacity 
 US RT｜供回水溫差 	 US RT | Supply / return temperature difference 
實際內徑 	Actual internal diameter 
mm｜每路水速 	mm | Water velocity per run 
並聯	 parallel runs
濕球溫度	Wet-bulb temperature
露點溫度	Dew-point temperature
空氣焓值	Air enthalpy
乾球 	Dry bulb 
°C｜濕度 	°C | RH 
含濕比 	Humidity ratio 
g/kg乾空氣｜比容 	g/kg dry air | Specific volume 
m³/kg乾空氣	m³/kg dry air
 kJ/kg乾空氣	 kJ/kg dry air
壓力	Pressure
溫度差（升溫／降溫）	Temperature difference (heating / cooling)
閥門流量係數（Kv／Cv）	Valve flow coefficient (Kv / Cv)
溫度	Temperature
溫差	Temperature difference
換算升溫／降溫的幅度。例如冰水12→7°C，溫差5°C＝5K＝9°F差；不加32或273.15。若要換算某個溫度，請選『溫度』。	Convert a temperature change, e.g. chilled water from 12 to 7°C: a 5°C difference = 5 K = 9°F difference. Do not add 32 or 273.15. For an actual temperature, select Temperature.
Kv／Cv表示閥門通流能力，通常查閥門型錄。Kv：水在壓差1bar下的m³/h；Cv(US)：水在壓差1psi下的US GPM。Kv≈0.865×Cv(US)，不是管徑或壓力。	Kv / Cv are valve flow coefficients from the valve catalogue. Kv is water flow in m³/h at 1 bar differential; Cv (US) is US GPM at 1 psi differential. Kv ≈ 0.865 × Cv (US). They are neither pipe sizes nor pressures.
換算溫度本身，例如25°C＝77°F＝298.15K；若要換算升溫或降溫的幅度，請選『溫度差（升溫／降溫）』。	Convert an actual temperature, e.g. 25°C = 77°F = 298.15 K. For a rise or fall, choose Temperature difference.
只換算單位，保持原來的表壓／絕對壓基準；表壓轉絕對壓需另外加當地大氣壓。	Only units change; gauge / absolute basis is preserved. Add local atmospheric pressure separately to convert gauge to absolute pressure.
日本冷凍噸	Japanese refrigeration ton
°C差	°C difference
°F差	°F difference
不支援的換算單位	Unsupported conversion unit
不支援的空氣狀態組合	Unsupported air property pair
兩股風量不可同時為零	Both air streams cannot have zero flow
各股輸入 CMH 以各自狀態為基準；乾空氣質量守恆	Each CMH input is referenced to its own state. Mixing conserves dry-air mass.
正值為加入空氣；此為兩點淨變化，不能代替分段冷量與再熱容量	Positive means added to the air. This is a net change between two states, not separate cooling and reheat capacities.
v=Q/(πD內²/4)；名目 DN／英吋不能代替實際內徑	v = Q / (π ID² / 4). Nominal DN / inch sizes do not replace actual internal diameters.
q[m³/h]=Kv√(Δp[bar]/SG)；僅不可壓縮液體、非汽化／阻塞流初估	q [m³/h] = Kv √(Δp [bar] / SG). Preliminary incompressible-liquid estimate; excludes flashing and choked flow.
電量=輸入kW×每日小時×天數×平均負載比例；費用=電量×自填單價，不含需量／時間電價	Energy = input kW × hours/day × days × average load fraction. Cost = energy × entered tariff; excludes demand and time-of-use charges.
溫度不可低於絕對零度	Temperature cannot be below absolute zero
反算 Kv 時壓差需大於零	Pressure drop must be positive when calculating Kv
露點不能高於乾球	Dew point cannot exceed dry-bulb temperature
露點水蒸氣分壓不得達到總壓	Dew-point vapor pressure must remain below total pressure
反算流量時溫差必須大於零	Temperature difference must be positive when calculating flow
未知反算目標	Unknown calculation target
濕球必須介於零濕度濕球下限與乾球之間	Wet bulb must be between its zero-humidity limit and dry-bulb temperature
反算溫差時流量必須大於零	Flow must be positive when calculating temperature difference
Kv 必須大於零	Kv must be positive
目前 	Current state 
填入有效溫濕度後，線圖會即時標示目前狀態。	Enter valid temperature and humidity to show the current state on the chart.
乾球溫度（°C）	Dry-bulb temperature (°C)
空氣線圖  P=	Psychrometric chart  P = 
請選擇有效選項	Select a valid option
三相 I=P×1000/(√3×V×PF)；單相 I=P×1000/(V×PF)。連續／馬達初估採125%；候選需滿足設計電流≤AT≤有效載流量。	Three-phase I = P×1000/(√3×V×PF); single-phase I = P×1000/(V×PF). Continuous / motor estimates use 125%. Candidates must satisfy design current ≤ breaker AT ≤ effective ampacity.
kW 是電氣輸入。線徑使用原專案初估表；缺少75°C端子表時採60°C表。馬達NFB仍須核啟動與獨立過載保護；中性線、接地及短路容量另核。	kW is electrical input. Cable sizing uses the project's reference table; a 60°C table substitutes where a 75°C terminal table is unavailable. Verify motor starting and separate overload protection. Neutral, grounding and short-circuit rating need separate checks.
A=風量/3600/風速；圓管D=√(4A/π)。路徑阻力=f×L/Dh×ρv²/2＋ΣK×ρv²/2＋設備壓降。	A = airflow/3600/velocity; round D = √(4A/π). Path resistance = f×L/Dh×ρv²/2 + ΣK×ρv²/2 + equipment pressure drop.
靜壓是可用於管路的壓力預算，不能單獨決定尺寸。未勾選已知路徑時不判定壓力是否足夠；圓管依2英吋級距選取。	Static pressure is the duct pressure budget; it does not determine size alone. Pressure adequacy is assessed only with a known path. Round ducts use 2-inch size increments.
表壓超出300 bar初估範圍	Gauge pressure exceeds the 300 bar estimate range
需求超過參考管徑表，不能把最大管徑當成符合。	Demand exceeds the reference pipe table. Its largest size must not be treated as adequate.
實際流量=標準流量×P標準/P絕對×T管內(K)/T標準(K)；D內=√(4Q實際/πv)。	Actual flow = standard flow × standard pressure / absolute pressure × pipe temperature (K) / standard temperature (K); ID = √(4 actual flow / πv).
壓力採管內表壓，另加所在地大氣壓。理想氣體Z=1，僅流速定寸；參考內徑需依實供管材核對，長管路另算壓降。	Enter pipe gauge pressure; local atmospheric pressure is added. Ideal-gas Z = 1. Sizing is by velocity only; confirm actual pipe ID and calculate pressure drop separately for long runs.
平均照度Lux=盞數×每盞流明lm×利用率U×維護係數M/面積m²；所需盞數向上取整。	Average lux = luminaire count × lumens per luminaire × utilization U × maintenance M / area m². Required count is rounded up.
Lux是空間照度，燈具光通量使用lm。體積須除以淨高換算面積；LED功率初估使用假設光效，不能代替型錄流明或照度均勻度模擬。	Lux is room illuminance; luminaire light output uses lm. Divide volume by clear height to obtain floor area. Estimated LED efficacy does not replace manufacturer lumens or an illuminance-uniformity simulation.
水物性採ρ=1000 kg/m³、cp=4.1868 kJ/(kg·K)；管徑按流速上限初估。未計水泵揚程與設備壓降。	Water properties: ρ = 1000 kg/m³, cp = 4.1868 kJ/(kg·K). Pipe size is estimated by the velocity limit. Pump head and equipment pressure drops are excluded.
w=0.621945×Pw/(P−Pw)；h=1.006T＋w(2501＋1.86T)，以kg乾空氣為基準。	w = 0.621945×Pw/(P−Pw); h = 1.006T + w(2501 + 1.86T), per kg of dry air.
濕度0%時露點無有限值；顯示為無有限露點，不以假數值代替。	At 0% RH the dew point has no finite value. It is displayed as No finite dew point, not as a fabricated number.
沒有這個簡易工具	Unknown quick tool
相數限1或3	Phase count must be 1 or 3
目前參考表找不到符合電流及壓降的線徑；請調整長度或在完整工作台評估。	No reference conductor meets both current and voltage-drop limits. Adjust the length or evaluate it in the full workbench.
設計電流與R/X阻抗上界	Design current and upper-bound R/X impedance
運轉電流及輸入PF	Operating current and input PF
反算燈數時，每盞光通量必須大於零。	Lumens per luminaire must be positive when sizing the count.
依所選物理量進行等值換算；溫度本身包含零點位移。	Equivalent conversion for the selected quantity. Actual temperatures include the zero-point offset.
依所選單位等值換算。	Equivalent conversion between the selected units.
三相	Three-phase
單相	Single-phase
乾空氣	dry air
淨高	clear height
體積	volume
坪	Taiwan ping
上限	limit
下限	lower limit
有效載流量	effective ampacity
最低所需內徑	minimum required ID
標準流量	Standard flow
管內	in pipe
絕對壓	absolute pressure
表壓	gauge pressure
露點	dew point
濕球	wet bulb
乾球	dry bulb
比容	specific volume
含濕比	humidity ratio
溫濕度	temperature / humidity
流速	velocity
流量	flow
靜壓	static pressure
寬高比	aspect ratio
每盞	per luminaire
地板照明面積	illuminated floor area
照明	lighting
平均	average
燈具	luminaire
路徑	path
內徑	internal diameter
「	“
」	”
：	: 
｜	 | 
；	; 
，	, 
、	 / 
（	 (
）	)
＝	 = 
／	 / 
＋	 + 
。	.
【	[
】	]
尚未連動	Not linked
等待計算	Awaiting calculation
啟用	Enable
停用	Disabled
夏季	Summer
冬季	Winter
預冷	Precooling
預熱	Preheating
再冷	Secondary cooling
再熱	Reheat
加熱	Heating
冷卻	Cooling
加濕	Humidification
除濕	Dehumidification
凝結水	Condensate
熱水	Hot water
電熱	Electric heat
電極式	Electrode
水洗	Air washer
濕膜	Wetted media
供水	Supply water
回水	Return water
送風	Supply air
回風	Return air
外氣	Outdoor air
室內	Room
潛熱	Latent heat
顯熱	Sensible heat
乾盤管	Dry coil
負荷	Load
設備	Equipment
需求	Demand
容量	Capacity
餘裕	Margin
摘要	Summary
參數	Parameters
條件	Conditions
來源	Source
備註	Notes
欄位	Field
填寫提示	Instructions
檔案	File
通過	Passed
未達	Failed
待資料	Data required
未提供	Not provided
未知	Unknown
錯誤	Error
初估	Preliminary estimate
系統	System
一般負載	General load
連續負載	Continuous load
馬達負載	Motor load
主系統	Main system
電力	Electrical
進階模式	Advanced mode
基本模式	Basic mode
簡易估算	Simple estimate
詳細計算	Detailed calculation
自動參考值	Automatic reference values
系統預設	System default
自訂	Custom
手動	Manual
手填	Entered manually
連動	Linked
人工指定	User-specified
自動需求	Automatic demand
旁通	Bypass
指定出口乾球	Set leaving dry bulb
指定出口 T/RH	Set leaving T / RH
熱水＋電熱	Hot water + electric heat
回收熱水	Recovered hot water
開式系統	Open system
閉式系統	Closed system
已知設備壓差	Known equipment pressure drop
計算_全開kW	Calculated_connected_kW
計算_同時kW	Calculated_demand_kW
計算_全開量(原單位)	Calculated_connected_flow(original_unit)
計算_同時量(原單位)	Calculated_demand_flow(original_unit)
設備編號	Equipment ID
設備名稱	Equipment name
供應群組	Supply group
設備台數	Equipment quantity
同時使用率(%)	Simultaneous use (%)
流量單位	Flow unit
每台需求流量	Required flow per unit
定寸流速上限(m/s)	Sizing velocity limit (m/s)
電力設備範例	Electrical equipment example
真空設備範例	Vacuum equipment example
範例	Example
匯出	Export
匯入	Import
儲存	Save
還原	Restore
取消	Cancel
刪除	Delete
新增	Add
套用	Apply
返回	Back
關閉	Close
全部	All
驗證	Validate
檢查	Check
檢核	Validation
校核	Verification
提示	Hint
顯示	Display
輸出	Output
有效	Valid
空白	Blank
數字	Number
整數	Integer
負值	Negative value
正值	Positive value
有限	Finite
不支援	Unsupported
支援	Supported
選項	Option
單位	Unit
組合	Combination
原因	Reason
內容	Content
目前	Current
估算	Estimate
管徑	Pipe size
標示	Label
尺寸	Size
定寸	Sizing
名目	Nominal
實際	Actual
目標	Target
候選	Candidate
配線	Wiring
電壓	Voltage
功率	Power
絕緣	Insulation
端子	Terminal
阻抗	Impedance
照度	Illuminance
光通量	Luminous flux
流明	Lumens
維護	Maintenance
利用率	Utilization
光效	Efficacy
清水	Water
物性	Fluid properties
冷熱	Heating / cooling
面積	Area
高度	Height
壓差	Pressure drop
阻力	Resistance
摩擦	Friction
管件	Fittings
熱量	Heat load
溫升	Temperature rise
最小	Minimum
最大	Maximum
最低	Minimum
最高	Maximum
回收	Recovery
蒸汽	Steam
""")

TEXT["廠務簡易工具\nV5.5.5"] = "FACILITY\nSTUDIO 5.5.5"

_add("""
洩壓需求	Relief demand
需求初估	Preliminary demand estimate
設備阻力	Equipment resistance
""")

_add(r"""
啟用(1/0)	Enabled (1/0)
CDA／N2填表壓，程式另加大氣壓。合計前會把各台標準量換到共同基準。	CDA / N2: enter gauge pressure; atmospheric pressure is added by the tool. Standard flows normalize to a shared reference before summing.
GEX、SEX、AEX、VEX、HEX各別統計。設備端靜壓只列最大已知要求，不能當風機總ESP。	GEX, SEX, AEX, VEX and HEX remain separate. Equipment static pressure lists only the maximum known requirement, not total fan ESP.
待填需求	Demand missing
PF空白採0.85，類型採一般設備，距離採30m。線表初估：XLPE、60°C端子、35°C、同管3根、壓降≤3%。	Blank defaults: PF 0.85, general load, length 30 m. Cable estimate: XLPE, 60°C terminals, 35°C ambient, 3 conductors, voltage drop ≤3%.
PV抽速	PV pumping speed
公式欄	Calculated columns
功率／流量都填每台數據，台數另填。插座數只統計點位，不再乘功率。	Enter power / flow per unit and quantity separately. Socket count only totals connection points; it does not multiply power.
可列NFB／線徑候選、分組kW／kVA／電流與點位；盤體尺寸、遮斷容量、相別平衡及接地需再補資料。	Produces breaker / conductor candidates, grouped kW / kVA / current and connection counts. Panel dimensions, interrupting ratings, phase balance and grounding require more data.
右方灰色欄提供該列原單位初算。匯入程式從黃色輸入欄重新計算，不依賴Excel快取結果。	Gray columns provide row estimates in original units. The importer recalculates yellow inputs and does not rely on Excel cached results.
同時使用率	Simultaneous use
在各系統分頁填設備，啟用設1，保留第5列欄名；回軟體右上「設備表匯入」開檔。	Fill the system sheets, enable actual equipment with 1 and keep row 5 headers. Open the file through Equipment schedules in the app.
填0~100的瞬間同時需求係數。空白採100%。不能用每小時運轉比例替代安全系統的設計量。	Enter instantaneous simultaneous demand 0–100; blank defaults to 100%. Hourly operating fractions cannot replace safety-system design demand.
填供應盤或共用主管，例如UP-01、CDA-01。不同群組分開定寸。	Enter the supply panel or shared main, e.g. UP-01 / CDA-01. Different groups are sized separately.
填寫方式與計算意義	Entry method / calculation meaning
填每台循環水量及流量單位；溫差預設5K。合計水量與熱量，未計泵揚程。	Enter circulating flow per unit and its unit. ΔT defaults to 5 K. Flow and heat are summed; pump head is excluded.
填每台所需插座點位。未知插座負荷請先估接入kW，不能只靠插座數決定NFB。	Enter socket points per unit. Estimate connected kW for unknown socket loads; socket count alone cannot size a breaker.
填每台電氣輸入kW、設備兩端電壓、1或3相、PF與台數。三相電壓填線間電壓。	Enter electrical input kW per unit, supply voltage, 1 / 3 phases, PF and quantity. Three-phase voltage is line-to-line.
必填欄不可空白。可用0的欄位請明確填0。選填欄採預設時，匯入明細會列出採用值。	Required fields cannot be blank. Enter explicit 0 where valid. Imported details list defaults adopted for optional fields.
所需抽速是在製程端的有效抽速；要選泵仍需泵曲線、氣體與真空管導通資料。	Required pumping speed is effective speed at the process. Pump selection still needs curves, gas data and pipe conductance.
插座	Sockets
操作順序	Workflow
支路按單台額定負載；主管依同時需求初估，盤進線不低於已納入最大單台支路設計電流。另列全開需求。	Branches use rated unit loads. Mains use simultaneous demand; panel feeders are at least the largest included unit's branch design current. Full connected demand is listed separately.
支路與主管	Branches / mains
數值填數字，單位另選。輸入欄不接受公式；若來源是公式，請貼上值。保留工作表名稱。	Enter numbers and choose units separately. Input formulas are not accepted; paste values from formula-based sources. Keep worksheet names.
新增與排序	Adding / sorting rows
標準量需對應溫壓，預設25°C／101.325kPa(abs)。ALPM是所填管內溫壓的實際L/min。	Standard flow needs a T/P reference; defaults are 25°C / 101.325 kPa(abs). ALPM is actual L/min at entered pipe T/P.
每台與台數	Per unit / quantity
每台製程用量可乘同時率；每台額外循環LPM持續納入，不乘同時率。避免重複填已包含的循環量。	Process flow per unit is multiplied by simultaneous use. Additional continuous circulation LPM per unit is not reduced. Avoid double-counting included circulation.
流量可填標準量或ALPM；壓力填絕壓，支援Torr、kPa、mbar。模型限1~760Torr。	Flow may be standard or ALPM. Pressure is absolute: Torr / kPa / mbar. Model range: 1–760 Torr.
盤體設計邊界	Panel-design boundary
空白與零	Blank / zero
第6列是示範，啟用為0。可改成自己的設備，或從第7列新增。	Row 6 is a disabled example (0). Replace it with actual equipment or add equipment from row 7.
設備需求表填寫說明	Equipment schedule instructions
資料格式	Data format
電力預設	Electrical defaults
項目	Item
預留100列。更多設備請在下方「欄位／填寫提示」之前插入列並複製輸入格式，最多10,000筆。按整列排序，設備編號不得重複。	100 rows are provided. Insert more before Field / Instructions below and copy input formatting; maximum 10,000 rows. Sort entire rows. Equipment IDs must be unique.
黃色填實際設備；灰色為原單位初算。範例啟用0，納入時改1。欄位詳細說明見下方。	Yellow: actual equipment inputs. Gray: estimates in original units. Examples are disabled (0); enable actual equipment with 1. Field instructions are below.
""")

_add(r"""
工程資料表版本、來源或欄位不完整	Engineering table version, provenance or fields incomplete.
NFB 額定排序不合法	Invalid breaker-rating order.
潔淨參考表不可空白且須為對照表	Cleanliness references must be a nonempty mapping.
工程資料表無法讀取；請確認檔案存在、UTF-8 編碼及 JSON 格式	Cannot read engineering tables. Check file existence, UTF-8 encoding and JSON format.
潔淨參考表不合法	Invalid cleanliness reference table.
 資料表不可空白	 table must not be empty
 資料不合法	 invalid data
 欄位或尺寸排序不合法	 invalid fields or size order
 規格名稱必須為非空白文字	 specification name must be nonblank text
 數值必須有限且大於零	 values must be finite and positive
室內產濕 kg/h	Room moisture generation (kg/h)
外氣 CMH（室內基準）	Outdoor air CMH (room reference)
處理風量 CMH（室內基準）	Treated airflow CMH (room reference)
夏季水側冷量 kW	Summer water-side cooling (kW)
DCC 設計需求 kW	DCC design demand (kW)
分段空調箱主案連動目前限全外氣 MAU；混風 AHU 的回風路徑不能當成全外氣箱。	Main-project linking supports 100% OA MAU only. A mixed AHU return path cannot be treated as a 100% OA box.
蒸汽設備電力未知，不能回傳成零負荷	Steam equipment power unknown; it cannot be transferred as zero load.
本空調箱未採用回收熱水；主案 HW 保持原值，避免清除其他服務負荷。	This AHU does not use recovered hot water. Main-project HW remains unchanged to preserve other served loads.
回傳值為取代所列欄位，不是疊加；其他廠務設備須另列。	Transferred values replace the listed fields; they are not added. List other facility equipment separately.
水側採純水 1000 kg/m³、4.1868 kJ/(kg·K)、黏度 0.001 Pa·s 初估；回傳會影響主案全部水迴路，應確認水溫與水質。	Water estimate: 1000 kg/m³, 4.1868 kJ/(kg·K), viscosity 0.001 Pa·s. Transfer affects all main-project water loops; confirm water temperature and quality.
電力採已填額定值，不是由冷量直接換成耗電；仍需確認 PF、同時使用及馬達保護。	Electrical power uses entered ratings, not cooling load converted to consumption. Confirm PF, simultaneous use and motor protection.
空調箱與主案保留各自計算邊界；回傳水量後需重新確認主案服務範圍。	AHU and main-project boundaries remain separate. Reconfirm the main project's served boundary after transferring water flows.
水洗泵電力未知：主案 NP 水泵值維持不變，仍需補確認。	Washer-pump power unknown: main-project NP pump value remains unchanged and needs confirmation.
H1/H2 熱水供回水條件不同：不合併成單一 HW，主案 HW 保持原值。	H1 / H2 hot-water conditions differ. They are not combined into one HW loop; main-project HW remains unchanged.
\n一、設計條件	\n1. Design conditions
\n二、空調分工與狀態	\n2. HVAC duties and states
點位             乾球°C    RH%       w(g/kg乾空氣)       h(kJ/kg乾空氣)	Point            Dry bulb °C   RH%     w(g/kg dry air)      h(kJ/kg dry air)
\n三、管路／流速／壓差	\n3. Piping / velocity / pressure drop
\n四、配電候選	\n4. Electrical candidates
\n五、主要公式與簡短說明	\n5. Key formulas and explanation
h=1.006T+w(2501+1.86T)；盤管 Qair=m_da(hin−hout)；Qwater=Qair−m凝結水×cp水×T凝結水。	h = 1.006T+w(2501+1.86T); coil Qair = m_da(hin−hout); Qwater = Qair−m_condensate×cp_water×T_condensate.
三相 I=1000P/(√3VLL·PF)；HP 為軸輸出，先乘 0.7456999/η 換輸入 kW；一般候選需滿足設計電流≤AT≤有效載流與小線保護上限。	Three-phase I = 1000P/(√3 VLL·PF). HP is shaft output; multiply by 0.7456999/η for input kW. General candidates require design current ≤ AT ≤ effective ampacity and small-conductor protection limit.
盤管為需求／ADP 近似，非廠商性能選定；電纜沿用專案表並加保守條件，端子、短路、接地及馬達啟動仍需覆核。	Coils use demand / ADP approximations, not manufacturer selections. Cables use project tables with conservative limits; terminals, fault rating, grounding and motor starting still need review.
資料依據：隨附版本化工程表為初估參考，並非已確認適用的法規載流表。參數來源另存於專案 JSON／HTML 附錄。	Basis: bundled versioned engineering tables are estimate references, not confirmed applicable statutory ampacity tables. Parameter provenance is stored in project JSON / HTML appendices.
此表為需求反算；未達額定檢核時，表列目標狀態不代表已配置設備實際可達。	This table calculates requirements. When rated-capacity checks fail, target states do not represent achievable installed-equipment performance.
\n水洗循環與風機	\nAir-washer circulation and fans
\n主要公式：m_da=V(CMH)/(3600×v_da)；Q=m_daΔh；純加熱 w 不變；水洗以 h_out≈h_in、T_out=T_in−ε(T_in−T_as)；蒸發 G=m_daΔw×3600；盤管水侧扣除凝結水液態焓。	\nKey formulas: m_da = V(CMH)/(3600×v_da); Q = m_da Δh; sensible heating keeps w constant. Washer h_out ≈ h_in, T_out = T_in−ε(T_in−T_as); evaporation G = m_da Δw×3600. Coil water-side duty deducts condensate liquid enthalpy.
計算限制：濕膜採循環水近似絕熱模型，忽略液態補水顯熱、泵入水熱及水溫調控；不保證飽和或 AMC 去除率。回收盤管能力須由廠商依同工況提供，端差只作必要條件篩選。	Limits: the recirculating wetted-media model is approximately adiabatic, excluding makeup-water sensible heat, pump heat to water and water-temperature control. Saturation / AMC removal is not guaranteed. Manufacturer recovery-coil capacity at design conditions is required; approach only screens necessary conditions.
送風 T/RH 是本單機邊界；若它其實是室內設定，須先扣室內產濕求所需送風含濕量。風量基準、膜有效度、C1 出口、風機熱與額定能力需原始送審資料核對。	Supply T/RH defines this AHU boundary. If these are room setpoints, first account for room moisture to calculate required supply humidity ratio. Verify airflow reference, media effectiveness, C1 outlet, fan heat and ratings against original submittals.
\n逐段控制與選用熱源（V5.5.5）	\nStage controls / selected heat sources (V5.5.5)
蒸汽與水洗分開：Δh_air=ṁsteam×hsteam/ṁda；Psteam=ṁsteam(hsteam−cp水×T補水)/η。電極式需導電水，給水及原廠電導率範圍未確認時不判定合格。	Steam is separate from washing: Δh_air = ṁsteam×hsteam/ṁda; Psteam = ṁsteam(hsteam−cp_water×T_feedwater)/η. Electrode humidifiers require conductive water. Compliance is not assumed without confirmed feedwater and manufacturer conductivity limits.
（通過僅指已知條件的初估，非原廠性能認證）\n	 (passed means estimates under known conditions, not manufacturer performance certification)\n
｜設計條件與計算摘要	 | Design conditions / calculation summary
；設備台數為需求候選，未達條件不可直接選用。	; equipment counts are demand candidates. Do not select directly when checks fail.
%RH（精確目標）。	%RH (exact target).
補償外氣下限 	Makeup outdoor-air minimum 
 CMH；额外洩壓需求 	 CMH; additional relief demand 
 CMH（均以室內狀態基準）。	 CMH (both at room conditions).
 kW；潛熱參考 	 kW; reference latent load 
 kW；產濕 	 kW; moisture generation 
產濕來源：人員 	Moisture sources: occupants 
＋額外製程 	 + additional process 
 kg/h；製程方式：	 kg/h; process input method: 
。外氣水氣由盤管另算，不重複加進室內。	. Outdoor moisture is calculated at the coils, not added again to the room.
一段供水 	First-stage supply water 
 K；二段 	 K; second stage 
處理風量 	Treated airflow 
 CMH（室內基準）；	 CMH (room reference); 
一段出口	First-stage outlet
二段出口	Second-stage outlet
最終送風	Final supply air
 kg/h（空氣側 	 kg/h (air-side 
氣體標準體積：	Gas standard-volume reference: 
°C，Z 比 	°C, Z ratio 
；僅流速初估。	; velocity-based estimate only.
；HP 換算效率 	; HP conversion efficiency 
 m；排序 	 m; selection order 
 kW；產濕 G=3600×m_da(wr−ws)=	 kW; moisture G = 3600×m_da(wr−ws) = 
\n本案待確認：	\nItems to confirm: 
侧	-side
側	-side
｜MAU 分段需求與額定容量校核	 | MAU stage demand / rated-capacity verification
 CMH，基準：	 CMH, reference: 
；大氣 	; atmospheric pressure 
 kW 完整保留；回收熱水 	 kW retained in full; recovered hot water 
°C，情境：	°C, scenario: 
C1 水溫 	C1 water temperature 
°C；濕膜有效度 	°C; wetted-media effectiveness 
（初估／待選型），容量餘裕 	 (estimate / selection pending), capacity margin 
循環泵揚程：	Circulation-pump head: 
最大蒸發補水約 	Maximum evaporative makeup approximately 
 L/h；另加輸入的飛水／排污後 	 L/h; including entered carryover / blowdown: 
 L/h，未包含未提供的排污或啟動補槽量。	 L/h, excluding unspecified blowdown or startup tank fill.
已填空氣側壓差 	Entered air-side pressure drop 
）；EC 配置 	); installed EC fans 
按所填壓差／效率的風機電力需求 	Fan input power required at entered pressure / efficiency 
 kW；電熱＋EC 已配置名目電力 	 kW; installed nominal electric-heater + EC power 
 kW，未含循環泵與附屬設備。	 kW, excluding circulation pump and auxiliaries.
。保留的名目電熱欄位不代表停用熱源仍在供熱。	. A retained nominal heater rating does not mean a disabled source is supplying heat.
本案選用設備名目電力 	Selected equipment nominal electrical power 
 kW（未含水洗泵／附屬設備）；未自動加進整廠 NP，避免重複。	 kW (excluding washer pump / auxiliaries); not automatically added to plant NP to avoid duplication.
整體狀態：	Overall status: 
 區 	 zone 
 CMH；潔淨紀錄 	 CMH; cleanliness record 
：空氣側 	: air-side 
 kW；水側 	 kW; water-side 
 kW；含餘裕 	 kW; including margin 
無設備需求	No equipment demand
冬季室內熱濕平衡：顯熱 	Winter room heat / moisture balance: sensible 
DCC 夏冬較大需求 	DCC maximum summer / winter demand 
 kW；冬季為明列負荷的穩態估算，非逐時建築模擬。	 kW; winter is a steady-state estimate of specified loads, not hourly building simulation.
冬季外氣處理基準：同設計質量流量處理至室內 T/RH，未扣冬季室內得熱；加熱 	Winter outdoor-treatment reference: design mass flow treated to room T/RH, without subtracting winter internal gains; heating 
（絕壓）；等值 	 (absolute); equivalent 
水質規格紀錄：	Water-quality specification record: 
 管件等效長度餘裕；Δp＝直管摩擦×(1＋餘裕)＋已知設備壓差＋適用靜揚程。	 fitting equivalent-length allowance; Δp = straight friction×(1+allowance) + known equipment pressure drop + applicable static head.
 A，設計 	 A, design 
 A，壓降 	 A, voltage drop 
%；接地紀錄：	%; grounding record: 
；來源主案 	; source main project 
%RH，乾空氣流率 	%RH, dry-air mass flow 
水洗蒸發需求 	Washer evaporation demand 
 kg/h（非循環泵流量）；本季水洗	 kg/h (not circulation-pump flow); seasonal washer 
額定／必要條件檢核：	Rated-capacity / necessary-condition checks: 
待廠商提供有效淋水面積及淋水密度，不套用蒸發量固定倍數。	Manufacturer effective wetted area and irrigation density required. No fixed evaporation multiplier is assumed.
待噴頭工作壓力、高差及管路／濾網阻力，不自動定為 20 m。	Nozzle operating pressure, elevation and piping / filter losses required. Head is not automatically assumed to be 20 m.
需求点	Demand state
需求點	Demand state
外氣於空調入口混合	Outdoor air mixed at HVAC inlet
 bar(g)，絕壓 	 bar(g), absolute pressure 
壓損簡易初估：	Simple pressure-loss estimate: 
额外	Additional
額外	Additional
分季送風目標：	Seasonal supply targets: 
%；總熱需求 	%; total heat demand 
 kW；热水 	 kW; hot water 
 kW；無回收時電力需求 	 kW; electrical demand without recovery 
：水側 	: water-side 
 US RT；需水 	 US RT; required water 
 LPM＝有效淋水面積×原廠單位面積水量	 LPM = effective wetted area × manufacturer flow per area
 m＝噴頭水頭＋高差＋管路／濾網損失	 m = nozzle head + elevation + pipe / filter losses
資料已標記完整，仍需風機曲線	Data marked complete; fan curves still required
資料未完整，不可據以完成選機	Data incomplete; equipment selection cannot be finalized
未超出名目電力；仍需風機曲線／運轉點	Within nominal power; fan curve / operating point still required
超出名目電力，需重選／核對	Exceeds nominal power; reselect / verify
热	heat
熱	heat
 kg/h；入空氣熱 	 kg/h; heat to air 
 kW；發生器電力 	 kW; generator electrical power 
運轉	Operating
 採用熱水 	 adopted hot water 
°C，端差 	°C, approach 
 K，電熱效率 	 K, electric-heater efficiency 
 尚無已選熱源供應的熱需求：	 demand not supplied by the selected heat source: 
 kW；圖表該點為未供應的需求點。	 kW; this chart point is an unsupplied demand state.
FFU 循環另計 	FFU circulation calculated separately 
；帶入 	; imported 
 CMH（送風狀態）／	 CMH (supply state) / 
：未達／需修正	: failed / correction required
冬季邊界	Winter boundary
室內產濕	Room moisture generation
補償外氣	Makeup outdoor air
處理風量	Treated airflow
夏季兩段水側冷量	Summer two-stage water-side cooling
DCC 設計顯熱	DCC design sensible duty
 CMH（室內基準）	 CMH (room reference)
 kW（未加餘裕）	 kW (before margin)
計算附錄	Calculation appendix
專案雜湊	Project hash
主要公式	Key formulas
產濕	Moisture generation
盤管空氣側	Coil air-side
水側扣除凝結水液態焓	water-side duty deducts condensate liquid enthalpy
需確認的條件	Conditions to confirm
容量與分工	Capacities and duties
需求初估，待原廠同工況及工程覆核	Demand estimate; manufacturer performance at design conditions and engineering review required
設計摘要	Design summary
列印／另存 PDF	Print / save PDF
簡易工具輸入含未知欄位或不是JSON物件	Quick-tool input has unknown fields or is not a JSON object.
尚不清楚	Unknown
原廠同工況性能	Manufacturer performance at design conditions
名目 RT／kW 與必要條件檢核不能替代同工況盤管、風機與加濕設備性能。	Nominal RT / kW and necessary-condition checks do not replace coil, fan and humidifier performance at matching conditions.
待補資料	Data required
DCC 循環風量與能力	DCC circulation airflow / capacity
DCC 回水必要條件	DCC return-water necessary condition
製程產濕	Process moisture generation
目前只計人員產濕，需確認製程水氣。	Only occupant moisture is included. Confirm process moisture.
設備同工況選型	Equipment selection at design conditions
本工具計算需求，仍需盤管／末端原廠選型與實際風機曲線。	This tool calculates demand. Manufacturer coil / terminal selections and actual fan curves are still required.
配電候選覆核	Electrical-candidate review
原表僅供初估；需敷設方式、短路、接地及馬達保護資料。	Tables are estimates only. Installation, fault, grounding and motor-protection data required.
氣體供壓／真空性能	Gas supply pressure / vacuum performance
目前為流速截面初估，需管路壓降與幫浦／調壓器性能。	Velocity-based cross-section estimate only; piping pressure loss and pump / regulator performance required.
冬季室內與電力範圍	Winter room / electrical boundary
風機壓差完整度	Fan pressure-drop data completeness
尚缺同風量各段終阻力。留空代表未知，明確 0 代表已知無此阻力。	Final stage resistances at matching airflow are missing. Blank means unknown; explicit 0 means a confirmed zero.
已配置元件阻力	Installed-component resistance
濾網、HEPA、盤管仍為 0；現有拓樸配置了這些元件，需提供阻力或改設計。	Filters, HEPA and coils remain 0 despite being present in the topology. Provide resistances or revise the design.
風機入氣流熱	Fan heat to airflow
入風 	Inlet air 
°C，供水必須低於入風。	°C; supply water must be colder than inlet air.
採 	Adopted 
 CMH；按最小端差的空氣側上限 	 CMH; air-side maximum at the minimum approach 
 kW。仍需原廠同工況性能。	 kW. Manufacturer performance at these conditions is still required.
供／回水 	Supply / return water 
°C，回水須低於 	°C; return water must be colder than 
°C 入風。	°C inlet air.
僅列管路小計；詳細與簡易模式皆未將未知阻力當成零。	Piping subtotal only. Neither Simple nor Detailed mode treats unknown resistance as zero.
依明列負荷完成穩態室內熱濕收支；NP 仍須實際設備電力。	Steady-state room heat / moisture balance uses specified loads. NP still requires actual equipment electrical power.
冬季目前為外氣處理基準；需另核室內熱濕與 NP 設備電力。	Winter currently uses an outdoor-treatment reference. Verify room heat / moisture and NP equipment power separately.
依本季需求與已填資料檢核；表列狀態為需求點。	Checks use seasonal demand and entered data. Listed states are requirements.
所需 	Required 
 kW；配置 	 kW; installed 
 kW。尚須曲線運轉點。	 kW. Fan curve and operating point still required.
入氣流熱 	Heat to airflow 
 kW 大於配置電力 	 kW exceeds installed electrical power 
目前採 0 kW 試算；需實際運轉電力、馬達位置及入氣流熱。	Currently estimated at 0 kW. Actual operating power, motor location and heat to airflow required.
需有效淋水面積與原廠淋水密度。	Effective wetted area and manufacturer irrigation density required.
水洗循環泵揚程	Washer circulation-pump head
需噴頭水頭、高差與管路損失；可填合法的 0m 高差。	Nozzle head, elevation and piping losses required. A confirmed 0 m elevation is valid.
 回水必要條件	 return-water necessary condition
°C；入口空氣 	°C; inlet air 
°C。水量公式成立仍須滿足換熱溫差。	°C. A valid flow formula still requires a feasible heat-transfer temperature difference.
 獨立水量	 independent water flow
水量可承擔 	Flow can carry 
僅目前已知阻力就需 	Known resistance alone requires 
 kW，已超出配置 	 kW, already exceeds installed 
給水	Feedwater
SUS白鐵管	Stainless-steel pipe
PVDF (超純水專用)	PVDF (ultrapure-water grade)
""")

_add(r"""
銅XLPE、端子60°C、環溫35°C、同管3根、壓降≤3%；參考表初估。	Copper XLPE, 60°C terminals, 35°C ambient, 3 loaded conductors, voltage drop ≤3%; reference-table estimate.
尚無設備端靜壓資料	Equipment static-pressure data unavailable
，未核風機總ESP。	; total fan ESP not checked.
設備需求分析 V5.5.5	Equipment demand analysis V5.5.5
設備列別明細	Equipment row details
沒有啟用的設備。請把實際設備的啟用欄設為1；範例預設0	No enabled equipment. Set actual equipment to enabled = 1; examples default to 0.
未自動產出正式盤體尺寸、遮斷容量、相別平衡、接地或管路壓損結論；需補單線圖／短路資料／配線及管路路徑／原廠性能。	No final panel dimensions, interrupting ratings, phase balance, grounding or piping-loss conclusions are generated. Supply single-line diagrams, fault data, wiring / piping routes and manufacturer performance.
；未核總ESP	; total ESP not checked
mm；圓Ø	mm; round Ø
V；等效PF=	V; equivalent PF =
；進線暫採單程	; provisional one-way feeder length 
定寸絕壓	Sizing absolute pressure
mm；各設備溫差／循環量見明細。	mm; see details for each unit's ΔT / circulation flow.
已知設備端最高要求	Highest known equipment requirement
全檔啟用	Enabled in file: 
筆；略過	 rows; skipped 
筆	 rows
全檔連接電力 	Total connected electrical power 
全檔供電分組kVA合計 	Sum of supply-group apparent power 
kVA；插座點位 	kVA; socket points 
PV模型限1~760Torr絕壓；更低壓力需真空導通模型	PV model range: 1–760 Torr absolute. Lower pressures require vacuum-conductance modelling.
管內絕對壓力	Pipe absolute pressure
表壓超過300bar初估範圍	Gauge pressure exceeds the 300 bar estimate range
同時率為輸入的初估係數；全開需求另列。常時排氣、吹掃及安全需求不得只用平均運轉率折減。	Simultaneous-use fractions are input assumptions; full connected demand is listed separately. Continuous exhaust, purge and safety requirements must not be reduced solely by average operating fractions.
A；設計	A; design 
路	 lines
含循環	Including circulation
設備資料完整	Equipment data complete
部分資料待補	Some data required
，連接	, connected 
kW／同時	kW / simultaneous 
功率因數(PF)	Power factor (PF)
每台額外循環量(LPM)	Additional circulation per unit (LPM)
請填數字1或0，不使用公式	Enter numeric 1 or 0, without a formula.
同一系統的設備編號重複；多台相同設備請填設備台數	Duplicate equipment ID in this system. Use quantity for multiple identical units.
超出管徑表，需另選管	Outside the pipe table; select another pipe
馬達群進線初估另加最大單台馬達25%；支路NFB仍需FLC、啟動與過載保護資料。	Motor-group feeder estimate adds 25% of the largest individual motor. Branch breakers still require FLC, starting and overload-protection data.
同時需求低於最大單台負載；進線候選至少採該單台支路設計電流。同時率與實際最大需求仍須確認。	Simultaneous demand is below the largest unit load. The feeder candidate uses at least that unit's branch design current. Confirm the use fraction and actual maximum demand.
P=Σ台數×單台kW×同時率；Q=ΣP×tan(arccosPF)，S=√(P²+Q²)。連續負載125%，馬達群加最大單台25%。進線不低於同時率>0的最大單台支路設計電流。	P = Σ quantity×unit kW×simultaneous fraction; reactive Q = ΣP×tan(arccos PF), S = √(P²+Q²). Continuous loads use 125%; motor groups add 25% of the largest motor. Feeder current is at least the largest enabled unit's branch design current.
單相分組未指派A/B/C相；不可把這個電流當三相總盤電流。	Single-phase groups have no A/B/C phase assignment. This current is not the three-phase main-panel current.
含多種供電方式，已分開列候選；總盤進線需單線圖、變壓器及相別分配，未合併電流。	Different supply types are listed separately. Main feeders require a single-line diagram, transformer and phase allocation; currents are not combined.
  全開：	  Connected: 
kW；插座	kW; sockets 
Torr(abs)，製程端有效抽速≥	Torr(abs), required effective pumping speed at process ≥ 
m³/h（未核泵曲線）	m³/h (pump curve not checked)
  待確認：	  Confirm: 
；每台支路	; branch per unit 
／同時	 / simultaneous 
    空白欄採預設：	    Defaults adopted for blank fields: 
輸入儲存格含Excel錯誤值，請修正或貼上實際值	Input cell contains an Excel error. Correct it or paste actual values.
輸入欄位請填實際數字／文字，不接受公式；請貼上值	Input fields require actual numbers / text, not formulas. Paste values.
請填數字或選項，不使用TRUE／FALSE	Enter numbers or listed choices, not TRUE / FALSE.
\n其餘	\nAdditional 
項請修正後重試	 issues; correct and retry
PF採落後、正弦及平衡負載。進線壓降採設計電流與R/X上界；長度暫採群組已填最大配線距離，實際進線路徑另核。	Assumes lagging PF and sinusoidal balanced loads. Feeder voltage drop uses design current and upper-bound R/X. Length provisionally uses the group's maximum entered cable distance; verify the actual feeder route.
必填；未知資料不能當成零	Required; unknown data cannot be treated as zero.
主管量=Σ台數×每台LPM×同時率＋持續循環量；Q熱=ΣLPM×ρcp×ΔT/60000。	Main flow = Σquantity×unit LPM×simultaneous fraction + continuous circulation. Heat load = ΣLPM×ρcp×ΔT/60000.
主管量=Σ台數×每台LPM×同時率＋Σ台數×額外循環LPM；D內=√(4Q/πv)。	Main flow = Σquantity×unit LPM×simultaneous fraction + Σquantity×extra circulation LPM; ID = √(4Q/πv).
PCW採清水ρ=1000、cp=4.1868；未核泵揚程／換熱器。	PCW assumes water ρ = 1000, cp = 4.1868. Pump head / heat exchangers not checked.
DI按實際內徑定寸；未套用碳鋼名目管徑。循環量不乘同時率，水質與供回水路徑另核。	DI sizing uses actual ID, not nominal carbon-steel size. Circulation is not reduced by simultaneous use. Verify water quality and supply / return routes.
標準量按參考溫壓統一後加總；實際量=SLPM×P標準/P絕對×T管內(K)/T標準(K)；D內=√(4Q實際/πv)。	Normalize standard flows to a common T/P before summing. Actual flow = SLPM×reference pressure/absolute pressure×pipe T(K)/reference T(K); ID = √(4 actual Q/πv).
流量統一至25°C／101.325kPa(abs)。同一群組採最低已填絕壓、最高溫度、最低流速上限定寸；僅流速初估，Z=1。	Flows normalize to 25°C / 101.325 kPa(abs). Each group uses its lowest entered absolute pressure, highest temperature and lowest velocity limit. Velocity-only estimate, Z = 1.
同群組設備的管內壓力不同；定寸採最低壓力，供應壓力級次及支路減壓器仍須確認。	Group pipe pressures differ. Sizing uses the lowest pressure; confirm supply-pressure levels and branch regulators.
列出的抽速是製程端所需有效抽速；未核真空管導通、氣體種類、洩漏、放氣及泵曲線，不能當泵銘牌選型。	Listed pumping speed is the effective speed required at the process. Conductance, gas type, leaks, outgassing and pump curves are not checked; do not use it as a pump nameplate selection.
需求超出管徑表；不以最大表列管徑假裝符合。	Demand exceeds the pipe table. The largest listed size is not assumed adequate.
風量=Σ台數×單台CMH×同時率；A=CMH/3600/v。不同排氣類型分開彙總。	Airflow = Σquantity×unit CMH×simultaneous fraction; A = CMH/3600/v. Exhaust types are summed separately.
靜壓只列已知設備端最大要求，沒有相加為風機ESP；全路徑阻力、洗滌塔及末端另核。	Static pressure lists the maximum known equipment-end requirement, not a sum for fan ESP. Verify full-path resistance, scrubber and terminals.
部分設備靜壓未填，保留待資料，不當成0Pa。	Some equipment static pressures are blank. They remain unknown, not 0 Pa.
  全開含循環：	  Connected including circulation: 
文字過長或含換行／控制字元	Text is too long or contains newlines / control characters.
可用選項：	Allowed choices: 
JSON 不接受 NaN 或無限大	JSON does not accept NaN or infinity.
JSON 數值超過有限範圍	JSON number exceeds the finite range.
JSON 檔案超過允許大小	JSON file exceeds the allowed size.
JSON 格式、編碼或巢狀結構不合法	Invalid JSON format, encoding or nesting.
JSON 欄位重複：	Duplicate JSON key: 
JSON 結構超過 64 層，請使用本工具匯出的檔案	JSON nesting exceeds 64 levels. Use a file exported by this tool.
Excel XML 不接受 DTD 或實體宣告	Excel XML does not accept DTD or entity declarations.
Excel XML 內容過大	Excel XML content is too large.
Excel儲存格位置損壞	Invalid Excel cell reference.
輸入欄位超過支援範圍（128欄）	Input exceeds the 128-column limit.
檔案不存在或超過20MB	File missing or larger than 20 MB.
安裝缺少設備Excel範本	Equipment Excel template is missing from the installation.
第	 row 
列	 row
Excel XML 結構過深或節點過多	Excel XML is too deep or has too many nodes.
Excel封存內容損壞、加密或壓縮方式不支援	Excel archive is damaged, encrypted or uses unsupported compression.
Excel XML內容損壞	Damaged Excel XML content.
不是有效.xlsx檔；請另存為Excel活頁簿	Not a valid .xlsx file. Save as an Excel workbook.
Excel解壓內容過大	Expanded Excel content is too large.
Excel含重複封存項目	Excel has duplicate archive entries.
不接受含巨集的活頁簿，請另存無巨集.xlsx	Macro-enabled workbooks are not accepted. Save as macro-free .xlsx.
找不到電力／PCW／CDA／N2／EXHAUST／DI／PV工作表；請使用公版範本	No Electrical / PCW / CDA / N2 / EXHAUST / DI / PV worksheet found. Use the supplied template.
未知或公式欄名；請保留範本欄名	Unknown or formula header. Keep template headers.
欄名重複	Duplicate header.
缺少欄位：	Missing fields: 
無欄名的欄位含資料	Data exists in a column without a header.
僅接受.xlsx或.csv；.xls／巨集檔請另存.xlsx	Only .xlsx / .csv accepted. Save .xls / macro files as .xlsx.
Excel缺少必要內容：	Excel is missing required content: 
Excel含不安全的工作表路徑	Excel contains an unsafe worksheet path.
系統工作表重複	Duplicate system worksheet.
工作表連結缺少或為外部連結	Worksheet link missing or external.
每張系統表最多	Maximum rows per system sheet: 
筆資料	 records
CSV必須指定系統	Select a system for CSV import.
CSV輸入欄位超過支援範圍（128欄）	CSV exceeds the 128-column limit.
工作表列號重複	Duplicate worksheet row number.
CSV最多	Maximum CSV rows: 
工作表列號損壞	Invalid worksheet row number.
儲存格與所在列號不一致	Cell reference does not match its row.
同一列的儲存格位置重複	Duplicate cell reference in a row.
CSV請使用UTF-8或繁體中文編碼	Use UTF-8 or Traditional Chinese encoding for CSV.
共用文字索引損壞	Invalid shared-string index.
冬季定風量不足，所需送風含濕比小於零	Winter constant airflow is insufficient; required supply humidity ratio is negative.
零送風無法完成冬季室內熱濕平衡	Zero supply airflow cannot satisfy winter room heat / moisture balance.
冬季送風需求超出物性範圍或超飽和；需調整風量或負荷：	Winter supply demand exceeds the property range or is supersaturated. Adjust flow or load: 
指定	Specified
蒸汽產量額定	Rated steam output
蒸汽電力額定	Rated steam electrical power
主案結構或版本不符	Main-project structure or version does not match.
主案欄位不完整	Main-project fields incomplete.
壓損資料不完整	Pressure-loss data incomplete.
草稿必須為有長度限制的文字，不能包含執行物件	Drafts must be length-limited strings, without executable objects.
不是專案物件	Not a project object.
不支援的整案保存格式	Unsupported workspace format.
專案識別碼不合法	Invalid project ID.
軟體版本不合法	Invalid software version.
保留草稿格式不符	Invalid retained-draft format.
單機清單過大或格式不符	AHU list too large or invalid.
方案比較格式不符	Invalid scenario-comparison format.
來源快照清單過大或不合法	Source-snapshot list too large or invalid.
整案檔案不得超過 15 MB	Workspace file must not exceed 15 MB.
壓損欄位不完整	Pressure-loss fields incomplete.
單機記錄格式不符	Invalid AHU record format.
單機識別碼重複或空白	Duplicate or blank AHU ID.
單機草稿欄位不完整	AHU draft fields incomplete.
方案快照不完整	Scenario snapshot incomplete.
方案快照與其輸入雜湊不一致	Scenario snapshot does not match its input hash.
方案快照缺少計算依據	Scenario snapshot lacks a calculation basis.
來源快照格式不符	Invalid source-snapshot format.
來源快照目標欄位不符	Source-snapshot target fields do not match.
單機來源識別不符	AHU source ID does not match.
方案快照的比較數值不完整	Scenario comparison values incomplete.
S表示標準狀態流量；ALPM是下方管內溫壓的實際L/min。	S denotes standard flow. ALPM is actual L/min at the pipe temperature and pressure below.
標準流量絕壓(kPa)	Standard-flow absolute pressure (kPa)
當地大氣壓(kPa絕壓)	Local atmospheric pressure (kPa absolute)
1納入計算，0不納入。範例預設0。	1 includes the row, 0 excludes it. Examples default to 0.
同一系統內不得重複。	Must be unique within the same system.
填配電盤或共用主管名稱。不同群組分開定寸。	Enter a panel or shared-main name. Different groups are sized separately.
瞬間同時需求的估算係數，填0~100；不是每小時運轉分鐘數。支路仍按額定負載。	Enter 0–100 for instantaneous simultaneous demand, not operating minutes per hour. Branches still use rated loads.
製程設備範例	Process equipment example
水冷機台範例	Water-cooled equipment example
氣動設備範例	Pneumatic equipment example
氮氣設備範例	Nitrogen equipment example
洗滌設備範例	Washing equipment example
每台輸入功率(kW)	Input power per unit (kW)
供電電壓(V)	Supply voltage (V)
供電相數(1/3)	Supply phases (1/3)
每台所需插座數	Required sockets per unit
排氣類型	Exhaust type
設備要求靜壓(Pa)	Equipment required static pressure (Pa)
電氣輸入kW；馬達軸輸出或HP需先換算並考慮效率。插座數不再乘功率。	Electrical input kW. Convert shaft power / HP with motor efficiency first. Socket count does not multiply power.
三相填線間電壓；單相填設備兩端電壓。不同供電方式分組，不直接合併電流。	Three-phase: line-to-line voltage. Single-phase: voltage across the equipment. Different supplies remain separate; do not add their currents.
僅統計點位。每台功率已包含該設備需求，不再乘插座數。	Connection-point count only. Unit power already includes equipment demand; do not multiply by socket count.
一般／酸性／鹼性／有機／機台熱排分開彙總，不能自行混接。	General, acid, alkaline, organic and equipment heat exhaust remain separate. Do not combine them without engineering review.
設備端要求，僅列最大值；不是全路徑風機ESP。未知填空白保留待資料。	Equipment-end requirement; only the maximum is listed, not full-path fan ESP. Leave unknown values blank.
額外持續循環量不乘同時使用率。避免把已含循環的流量重複填入。	Additional continuous circulation is not reduced by simultaneous use. Avoid counting circulation already included in flow.
來源快照識別，不能手動修改	Source-snapshot ID; manual editing is blocked.
本模式不使用 MAU／DCC／FFU	This mode does not use MAU / DCC / FFU.
本模式不使用 FCU	This mode does not use FCU.
本模式不使用 RCU	This mode does not use RCU.
一段旁通，保留備用設定	First stage bypassed; backup settings retained.
未採用的循環風量計算方式	Inactive circulation-airflow method
目前不以 kW 輸入製程水氣	Process moisture is not currently entered as kW.
目前不以 kg/h 輸入製程水氣	Process moisture is not currently entered as kg/h.
採用水型的初估電阻率參考	Using the water-type resistivity reference.
使用分季目標與各季送風狀態實際風量	Using seasonal targets and actual airflow at each supply state.
使用共用送風目標	Using shared supply target.
分季指定／旁通優先，此為自動模式備用目標	Seasonal specified / bypass control takes priority; this is the automatic-mode backup target.
目前未使用蒸汽加濕	Steam humidification inactive.
目前未採用水洗加濕，設備記錄保留	Air-washer humidification inactive; equipment record retained.
沒有啟用共用回收熱水的段落	No stage uses shared recovered hot water.
設計條件	Design conditions
出口濕度由盤管過程計算	Leaving RH calculated from the coil process.
採用負荷反算水量，手填值僅保留	Water flow calculated from load; manual value retained but inactive.
採用共用最低管內壓力	Using shared minimum pipe pressure.
採用氣體種類的流速參考	Using gas-type velocity reference.
目前不是馬達群負載	Not currently a motor-group load.
目前不是電極式蒸汽	Not currently electrode steam.
本段不採用直接電熱，配置資料保留	This stage does not use direct electric heat; installed data retained.
二期	Phase 2
本段目前不採用熱回收水	This stage does not currently use recovered hot water.
本段不採用独立熱水條件	This stage does not use independent hot-water conditions.
出口由自動需求或旁通決定	Leaving state determined by automatic demand or bypass.
濕度由盤管物理過程決定	Humidity determined by the coil's physical process.
一段盤管	First-stage coil
二段盤管	Second-stage coil
全期外氣	100% outdoor air
全外氣	100% outdoor air
專案檔案超過 15 MB	Project file exceeds 15 MB.
專案 JSON 必須為物件	Project JSON must be an object.
製程產濕尚未提供，目前只計人員；有開放水槽、濕洗或蒸汽洩漏時需補填，勿當作已完成除濕設計。	Process moisture missing; only occupants are included. Add open-tank, wet-process or steam-leak moisture. This is not a completed dehumidification design.
加熱與加濕的空氣側需求尚未自動併入 NP；請按設備型式、效率與實際輸入功率填列。	Air-side heating / humidification demands are not automatically included in NP. Enter actual input power by equipment type and efficiency.
V5.4 欄位不完整，無法移轉	V5.4 fields incomplete; migration blocked.
舊專案輸入	Legacy project input
V5.4 或更早版本移轉；未推定原廠來源	Migrated from V5.4 or earlier; no manufacturer provenance assumed.
本模型限 1～760 Torr 絕壓（約 0.133322～101.325 kPa）；請確認單位	Model range: 1–760 Torr absolute (about 0.133322–101.325 kPa). Check units.
專案格式需要 V5.5.4；支援完整 V5.0～5.2 自動移轉	Project schema requires V5.5.4; complete V5.0–5.2 projects migrate automatically.
專案輸入欄位缺漏或含未知欄位	Project input fields missing or unknown.
壓損系統資料缺漏	Pressure-loss system data missing.
 不可產生未配置的加熱或加濕	 cannot provide unconfigured heating or humidification
 水側負荷不合理	 water-side load is invalid
二段冷卻溫度低於可達 ADP	Second-stage cooling temperature below achievable ADP.
送風需要未配置的額外冷卻	Supply air requires additional unconfigured cooling.
此工況需要加熱／再熱，請啟用或調整設計條件	This condition requires heating / reheat. Enable it or adjust the design.
此工況需要加濕，請啟用或調整設計條件	This condition requires humidification. Enable it or adjust the design.
PCW 與直接排氣帶走熱量超過同工況設備總發熱	PCW plus direct-exhaust heat removal exceeds equipment heat generation at the same condition.
指定外氣 	Specified outdoor airflow 
 低於補償下限 	 below makeup minimum 
FCU／RCU 採外氣於入口混入的等效控制體；實際外氣另接 MAU 時需另設系統拓樸。	FCU / RCU use an equivalent control volume with outdoor air mixed at the inlet. A separate MAU requires a different system topology.
冬季室內守恆檢核失敗	Winter room conservation check failed.
乾盤管進水未達露點＋安全裕度	Dry-coil supply water fails dew point + safety margin.
 未含設備阻力，僅為管路小計；選泵／風機前須補盤管、濾網、處理設備等壓差。	 excludes equipment resistance: piping subtotal only. Add coil, filter and treatment-equipment pressure drops before selecting pumps / fans.
內部守恆檢核失敗，報告已停止	Internal conservation check failed; report blocked.
V5.0 專案欄位缺漏或含未知欄位	V5.0 project fields missing or unknown.
V5.0 壓損欄位不完整	V5.0 pressure-loss fields incomplete.
V5.1/5.2 欄位缺漏或不同來源格式，不能以相同版本號誤載	V5.1/5.2 fields missing or from a different format. Matching version numbers do not establish compatibility.
V5.3 專案欄位不完整，不能自動移轉	V5.3 project fields incomplete; automatic migration blocked.
專案值必須為文字	Project values must be strings.
 壓損欄位缺漏	 pressure-loss fields missing
壓損欄位必須是有長度限制的文字	Pressure-loss fields must be length-limited strings.
二段所需露點低於供水＋ADP 裕度；需增加可用除濕風量或降低供水溫度	Required second-stage dew point is below supply water + ADP approach. Increase dehumidification airflow or lower supply-water temperature.
有面積時淨高必須大於零	A room with area must have positive clear height.
有人員時區域不可為零面積	An occupied zone cannot have zero area.
開門總時間不可超過一小時	Total door-open duration cannot exceed one hour per hour.
可達含濕量不足以處理室內產濕，請降低二段 ADP	Achievable humidity ratio cannot handle room moisture. Lower the second-stage ADP.
指定外氣不足以在二段 ADP 下維持室內濕度	Specified outdoor airflow cannot maintain room humidity at the second-stage ADP.
MAU 過冷或室內淨熱損，需要室內加熱控制；請調整送風溫度或改混合空調模式	MAU overcooling or net room heat loss requires room heating. Adjust supply temperature or choose a mixing HVAC mode.
無法求得滿足顯熱／濕度與供水條件的送風量	No supply airflow satisfies sensible heat, humidity and supply-water constraints.
 獨立水量容量 	 independent-flow capacity 
 kW，低於同範圍需求 	 kW, below demand in the same boundary 
 kW；請確認服務範圍或改連動。	 kW; confirm the served boundary or enable load linking.
壓損 	Pressure loss 
盤管能量檢核失敗，報告已停止	Coil energy check failed; report blocked.
一段指定出口低於供水＋ADP 裕度	First-stage leaving target below supply water + ADP approach.
一段除濕露點低於可達 ADP	First-stage dehumidification dew point below achievable ADP.
零外氣無法處理產濕	Zero outdoor airflow cannot remove moisture generation.
 自訂 ID 只適用圓管，請切換風管形狀或設 0	 custom ID applies only to round ducts. Change shape or enter 0.
文字不可空白且不得超過 500 字	Text must be nonblank and at most 500 characters.
 指定內徑超過流速上限	 specified ID exceeds the velocity limit
參數來源欄位不完整	Parameter-source fields incomplete.
復原檔案過大	Recovery file too large.
不是本工具的復原檔	Not this tool's recovery file.
參數來源格式不合法	Invalid parameter-source format.
原廠資料必須註記文件或選型編號	Manufacturer data must have a document or selection reference.
來源版本資料不合法	Invalid source-version data.
H1 電熱全載備援	H1 all-electric full-load backup
H2 電熱全載備援	H2 all-electric full-load backup
H1 當前熱源情境	H1 current heat-source scenario
H2 當前熱源情境	H2 current heat-source scenario
C1 總表候選容量	C1 schedule candidate capacity
C2 總表候選容量	C2 schedule candidate capacity
C2 可達 ADP	C2 achievable ADP
濕膜總表候選能力	Wetted-media schedule candidate capacity
送風含濕量目標	Supply humidity-ratio target
逐段指定／自動混合需求	Mixed specified / automatic stage demand
初／中效濾網	Pre / medium filters
單機專案欄位缺漏或含未知欄位	AHU project fields missing or unknown.
蒸汽給水已確認	Steam feedwater confirmed
通用單機專案欄位缺漏或含未知欄位	Generic AHU fields missing or unknown.
熱水供水必須高於回水	Hot-water supply must exceed return temperature.
C1 出口需求低於供水＋ADP 裕度	C1 leaving demand below supply water + ADP approach.
C1 需求的旁通因子超出物理範圍	C1 required bypass factor outside the physical range.
回水端差不足，熱回收未採計	Return-water approach insufficient; recovered heat excluded.
電熱在前時不滿足指定供回水端差，熱回收未採計	Electric-first order fails the specified water approaches; recovered heat excluded.
風機熱過大，所需風機前溫度低於送風露點	Excess fan heat makes the required pre-fan temperature lower than supply dew point.
水洗後含濕量不足，無法以再熱補水氣	Humidity ratio after washing is insufficient. Reheat cannot add moisture.
分段熱濕守恆檢核未通過	Stage heat / moisture conservation check failed.
原廠電導率上限不得低於下限	Manufacturer maximum conductivity must not be below its minimum.
檔案過大	File too large.
請使用通用單機專案格式	Use the generic AHU project format.
不支援的單機專案版本	Unsupported AHU project version.
冷卻出口不得加熱或增加水氣；請檢查 T/RH	Cooling outlet cannot add heat or moisture. Check T/RH.
送風狀態實際風量	Actual airflow at the supply state
自動目標需求	Automatic target demand
所需風機前狀態低於送風露點	Required pre-fan state below supply dew point.
H2 加熱段不可降低乾球	H2 heating stage cannot lower dry bulb.
 當前熱源情境	 current heat-source scenario
 總表候選容量	 schedule candidate capacity
 可達 ADP	 achievable ADP
電極給水電導率	Electrode feedwater conductivity
分段熱濕守恆未通過	Stage heat / moisture conservation failed.
請以文字保存欄位	Save fields as strings.
冷卻水回水必須高於供水	Cooling-water return must exceed supply temperature.
外氣水分不足而水洗停用，無法達成送風含濕量	Outdoor moisture insufficient and washer disabled; supply humidity ratio cannot be reached.
在 80°C 預熱範圍仍無法達到所需含濕量	Required humidity ratio cannot be reached within the 80°C preheat range.
本段熱水供水必須高於回水	Stage hot-water supply must exceed return temperature.
效率限 0 沿用共同或 0.1～1	Efficiency must be 0 (shared value) or 0.1–1.
舊單機專案欄位不完整	Legacy AHU project fields incomplete.
蒸汽注入後超飽和，需提高 H1 出口或減少注入需求	Steam injection causes supersaturation. Raise H1 leaving temperature or reduce injection demand.
H1 加熱段不可降低乾球	H1 heating stage cannot lower dry bulb.
 電熱全載備援	 all-electric full-load backup
冷卻段不可把空氣加熱	Cooling stage cannot heat air.
專案名稱不可空白或過長	Project name cannot be blank or too long.
80°C 範圍仍無法達標	Target cannot be reached within the 80°C range.
 未供應熱量（需求點）	 supplies no heat (demand state)
80°C 預熱仍無法防止蒸汽過飽和	80°C preheat still cannot prevent steam supersaturation.
廠務估算專案	Facility estimate project
需求工況（待選機）	Required conditions (equipment selection pending)
精確設定值	Exact setpoint
TW 專案表初估（非完整合規）	Taiwan project-table estimate (not full compliance)
CHW (空調冰水)	CHW (HVAC chilled water)
DCCW (乾盤管水)	DCCW (dry-coil water)
PCW (製程冷卻水)	PCW (process cooling water)
HW (熱水盤管水)	HW (hot-water coil water)
HEX (機台熱排)	HEX (equipment heat exhaust)
數量	Quantity
開關	Switch
空氣乾球	Air dry bulb
最大風速	Maximum air velocity
水流速上限	Water velocity limit
水管選型模式	Water-pipe selection mode
設備壓降	Equipment pressure drop
手動單位阻力率	Manual loss rate per unit length
壓損單位	Pressure-loss unit
壓損模式	Pressure-loss mode
K 值加總	Sum of K coefficients
電纜絕緣	Cable insulation
電纜排序	Cable selection order
選型依據	Selection basis
NP 負載來源	NP load source
濕空氣公式與乾空氣質量基準（ASHRAE 2017 對照）	Psychrometric formulas / dry-air mass basis (ASHRAE 2017 reference)
盤管 ADP/BF 模型及限制	Coil ADP / BF model and limits
用戶用電設備裝置規則；實案仍須確認適用版本及表格	Taiwan electrical-installation rules; confirm the applicable edition and tables.
周圍溫度修正表 25-7	Ambient-temperature correction table 25-7
同管載流導線數修正表 25-6	Loaded-conductor correction table 25-6
ISO 14644-1 潔淨分類；不以固定 ACH 取代粒子測試	ISO 14644-1 cleanliness classification; fixed ACH does not replace particle testing.
氧氣配管要求與壓力／流速適用條件	Oxygen piping requirements / applicable pressure and velocity conditions
真空壓力單位與範圍	Vacuum pressure units / range
美制冷凍噸單位	US refrigeration-ton unit
日本冷凍噸定義	Japanese refrigeration-ton definition
Darcy-Weisbach 管路方法	Darcy-Weisbach piping method
原專案流量表	Original project flow table
電氣採三相平衡及同一等效 PF。kW 為電氣輸入，HP 為軸輸出並除效率；不同設備不得重複填入。	Electrical model assumes balanced three-phase loads and one equivalent PF. kW is electrical input; HP is shaft output divided by efficiency. Do not duplicate equipment.
原電纜表缺少安裝方式／來源，完整保留但僅作專案初估；2.0 欄位量綱可疑，保留原資料但不參與選型。	Original cable table lacks installation / provenance data. It is retained for estimates only. The 2.0 entry has questionable dimensions and is excluded from selection.
缺少 75°C 端子表時保守用原 60°C 表限制。環溫及同管設定取兩輸入中較不利值。	When the 75°C terminal table is missing, use the original 60°C limit conservatively. Apply the less favorable ambient / conductor-count setting.
一般保護候選要求設計電流 ≤ AT ≤ 有效載流／小線保護上限；未自動套用上調一級例外。	General protection candidates require design current ≤ AT ≤ effective ampacity / small-conductor protection limit. No next-size-up exception is applied automatically.
尚需確認短路電流、Icu/Ics、選擇協調、接地、中性線與諧波；本報告不構成配電施工核定。	Still verify fault current, Icu/Ics, coordination, grounding, neutral and harmonics. This report is not approval for electrical construction.
遠端最低表壓不得高於供氣表壓	Remote minimum gauge pressure must not exceed source gauge pressure.
特氣／PV 採指定標準溫壓與 Z 比值換算實際流量；只做流速截面初估，未算可壓縮壓降及遠端供壓。	Gas / PV actual flow uses specified reference T/P and Z ratio. This is velocity-based cross-section sizing only; compressible pressure drop and remote supply pressure are not solved.
O2／H2 等原流速表不是材料相容、點火風險或氣體安全核定；管件、潔淨度、洩漏與連鎖須另設計。	Reference O2 / H2 velocities do not certify material compatibility, ignition risk or gas safety. Design fittings, cleanliness, leak protection and interlocks separately.
PV 使用絕對壓，未計真空導通率、泵曲線與抽氣時間；材質必須另外核對外壓屈曲。	PV uses absolute pressure. Vacuum conductance, pump curves and evacuation time are excluded. Verify material resistance to external-pressure buckling.
不可為空白、NaN 或無限值	must not be blank, NaN or infinite
不可小於 	must be at least 
不可大於 	must not exceed 
必須為整數	must be an integer
必須為 0 或 1	must be 0 or 1
空氣狀態超飽和：	Supersaturated air state: 
水蒸氣分壓大於總壓，超出模型範圍	Vapor pressure exceeds total pressure; outside the model range.
儲存資料夾不存在	Save folder does not exist.
找不到符合面積與寬高比的風管	No duct meets the area and aspect-ratio requirements.
指定實際內徑超過水流速上限	Specified actual ID exceeds the water-velocity limit.
閉式循環不可直接加樓高；靜揚程請設 0	Do not add building height to a closed loop. Set static head to 0.
風管不使用水泵靜揚程，請設 0	Ducts do not use pump static head. Set it to 0.
管槽降載	Conduit / grouping derating
PV 絕對壓不得高於所在地大氣壓	PV absolute pressure must not exceed local atmospheric pressure.
PV 低於此連續介質流速初估模型的壓力下限；需真空導通率與幫浦曲線	PV pressure is below the continuum velocity model's limit. Use vacuum conductance and pump curves.
必須為有效數字	must be a valid number
水管需求超過 32 組並聯範圍	Water-pipe demand exceeds the 32-parallel-run limit.
 最大馬達 HP 不得大於明列的 HP 合計	 largest motor HP must not exceed the listed total HP
 沒有符合載流、保護上限及壓降的候選電纜（最多 8 組並聯）	 has no cable candidate meeting ampacity, protection and voltage-drop limits (maximum 8 parallel runs)
 含馬達：目前用 kW／HP 估算電流，最大馬達未填時保守用全負荷 125%；斷路器僅候選，須另核啟動、過載與短路保護。	 includes motors: current estimated from kW / HP. Without the largest motor, use 125% of total load conservatively. Breakers are candidates; verify starting, overload and short-circuit protection.
 並聯需核同長同材同截面、均流、各相配置；同管載流根數依實際路由設定。	 Parallel cables require matched length, material and area, current sharing and phase arrangement. Set loaded-conductor count for the actual route.
PV 請填專用真空欄；特氣欄只接受正壓氣體	Enter PV in the vacuum fields. Gas fields accept positive-pressure gases only.
本路管內表壓高於供氣表壓	This line's pipe gauge pressure exceeds source pressure.
 超過原始管材表範圍；不可把最大管徑當作符合	 exceeds the original pipe table; its largest size is not assumed adequate
""")

_add("""
負載類型	Load type
獨立輸入	Independent input
獨立输入	Independent input
額外製程潛熱（不含人員／外氣）	Additional process latent load (excluding occupants / outdoor air)
電阻率參考（25°C）	Reference resistivity (25°C)
室內模式以明列得熱、外牆、樓板與產濕作穩態收支；沿用夏季設計風量。並非逐時建築負荷或多室模型。	Room mode balances specified heat gains, envelope conduction and moisture at steady state using the summer design airflow. It is not an hourly building-load or multi-zone model.
總覽與空氣線圖	Overview / psychrometrics
空調與空間	HVAC / rooms
熱負荷與照明	Heat loads / lighting
特氣與真空	Gases / vacuum
動力配電	Electrical distribution
排氣風管	Exhaust ducts
水系統與純水	Water / pure water
壓損矩陣	Pressure losses
設計報告	Design report
專案與共同氣候（圖表／空調共用）	Project / climate (shared by chart and HVAC)
系統分工與設備	System duties / equipment
漏氣、排氣補充與人員外氣	Leakage / exhaust makeup / occupant outdoor air
兩段盤管／再熱／加濕	Two-stage coils / reheat / humidification
照度與燈具（啟動即計算）	Illuminance / luminaires (calculated at startup)
設備散熱與製程產濕	Equipment heat / process moisture
圍護與其他入室熱	Envelope / other room heat gains
溫壓基準與真空	Temperature / pressure references / vacuum
電源、線材與候選排序	Power supply / cable / selection order
風管共同條件	Shared duct conditions
水側物性（按實際流體修訂）	Water properties (adjust for the actual fluid)
純水循環與水質規格	Pure-water circulation / quality specifications
室內產濕／除濕需求	Room moisture / dehumidification demand
水質參考值來源	Source of water-quality references
UPW (超純水)	UPW (ultrapure water)
DI (去離子水)	DI (deionized water)
RO (逆滲透水)	RO (reverse-osmosis water)
18.2 MΩ·cm @25°C（參考目標）	18.2 MΩ·cm @25°C (reference target)
≥ 1.0 MΩ·cm @25°C（初估參考）	≥ 1.0 MΩ·cm @25°C (estimate reference)
≥ 0.05 MΩ·cm @25°C（初估參考）	≥ 0.05 MΩ·cm @25°C (estimate reference)
工作面平均照度；燈具數量會自動計算。	Average working-plane illuminance; luminaire count is calculated automatically.
填設備總發熱，非一律把銘牌電力當成入室熱。	Enter total equipment heat generation. Nameplate electrical power is not necessarily heat released into the room.
同時開機台數；水帶走的熱不可再次算入室內。	Number of operating units at the same time. Do not count water-removed heat again as a room gain.
全部為絕對壓力；150 Torr ≈ 20.00 kPa ≈ 199.98 mbar。	All values are absolute pressures: 150 Torr ≈ 20.00 kPa ≈ 199.98 mbar.
水型只提供初估參考，RO／DI 製法本身不保證此值。	Water type supplies an estimate reference only. RO / DI treatment alone does not guarantee this value.
每小時實際散入室內的水；已由密閉排氣帶走的部分不要算入。	Water actually released into the room per hour. Exclude moisture already removed by enclosed exhaust.
只填額外製程水氣負荷；人員與外氣已另外計算。	Enter additional process moisture only. Occupants and outdoor air are calculated separately.
PV｜進階定寸條件	PV | Advanced sizing conditions
DCC 空氣側可達條件	DCC air-side achievable conditions
冬季設計邊界	Winter design boundary
廠務設計試算	Facility design estimate
自動旁通因子估算	Automatic bypass-factor estimate
待核	Verification pending
3根以下 (標準)	Up to 3 conductors (reference)
一般	General
酸性	Acid
鹼性	Alkaline
有機	Organic
熱排	Heat exhaust
尚不清楚（暫不計製程）	Unknown (process moisture temporarily excluded)
PV 管內絕對壓力	PV pipe absolute pressure
所選單位	Selected unit
依製程確認	Confirm for the process
直管長度	Straight length
彎頭	Elbows
只	Only
三通	Tees
大小頭	Reducers
閥件	Valves
指定單位	Specified unit
壓差／阻力率單位	Pressure drop / loss-rate unit
計算方式	Calculation method
手動阻力率	Manual loss rate
指定單位/m	Specified unit / m
管件模式	Fitting method
管件 K 加總	Sum of fitting K
彎頭 L/D	Elbow L/D
三通 L/D	Tee L/D
大小頭 L/D	Reducer L/D
閥件 L/D	Valve L/D
自訂圓管 ID，0 自動	Custom round-pipe ID (0 = automatic)
系統邊界	System boundary
開式靜揚程	Open-system static head
泵／風機效率	Pump / fan efficiency
比例	Fraction
尚無資料（不含設備）	Data unavailable (equipment excluded)
共用的定寸最低管內表壓。各路進階可改本路值；不是已完成壓降反算。	Shared minimum pipe gauge pressure for sizing. Advanced settings can override each line; this is not a solved pressure-drop calculation.
共同供氣源表壓。各路管內定寸表壓不得高於此值。	Common gas-source gauge pressure. Each line's sizing gauge pressure must not exceed this value.
沿用 FFU 循環	Use FFU circulation
一般廠房初估範例	General factory example
AHU (OA+RA 混合)	AHU (OA + RA mixing)
無 (None)	None
沒有額外產濕	No additional moisture
室內熱濕平衡（定風量）	Room heat / moisture balance (constant airflow)
專案名稱	Project name
文字	Text
大氣壓	Atmospheric pressure
空調系統	HVAC system
冷凍噸基準	Refrigeration-ton reference
MAU 最終送風溫度	MAU final supply-air temperature
單台 DCC 同工況顯熱能力	DCC sensible capacity per unit at design conditions
單台 RCU 同工況冷量	RCU cooling capacity per unit at design conditions
單台 FCU 室內基準風量	FCU airflow per unit at room conditions
單台 FCU 同工況冷量	FCU cooling capacity per unit at design conditions
單台 FFU 室內基準風量	FFU airflow per unit at room conditions
單台 FFU 入室發熱	FFU heat to room per unit
容量安全餘裕	Capacity safety margin
 區空間／循環需求	 zone / circulation demand
A 區門縫總長	Zone A total door-gap length
A 區門縫寬	Zone A door-gap width
A 區單門面積	Zone A area per door
A 區每小時開門次數	Zone A door openings per hour
B 區門縫總長	Zone B total door-gap length
B 區門縫寬	Zone B door-gap width
B 區單門面積	Zone B area per door
B 區每小時開門次數	Zone B door openings per hour
每次開門時間	Duration per door opening
漏氣流量係數	Leakage discharge coefficient
額外 PRD 洩壓量	Additional PRD relief flow
每人外氣設定	Outdoor air per occupant
CMH/人	CMH / person
指定外氣，0 為自動	Specified outdoor airflow (0 = automatic)
室內基準 CMH	CMH at room conditions
PV 從室內抽取比例	Fraction of PV drawn from room
一段盤管控制	First-stage coil control
一段供水溫度	First-stage supply-water temperature
一段 ADP 高於供水	First-stage ADP above supply-water temperature
一段目標出口乾球	First-stage target leaving dry bulb
指定一段出口相對濕度	Specified first-stage leaving RH
二段供水溫度	Second-stage supply-water temperature
二段最低 ADP 高於供水	Second-stage minimum ADP above supply water
允許加熱／再熱	Allow heating / reheat
允許加濕	Allow humidification
乾盤管露點安全裕度	Dry-coil dew-point safety margin
單盞光通量	Lumens per luminaire
單盞輸入功率／入室熱	Input power / room heat per luminaire
利用係數 U	Utilization factor U
同範圍設備總發熱	Total heat from equipment within the boundary
設備運轉率	Equipment operating fraction
運轉熱由排氣帶走比例	Fraction of operating heat removed by exhaust
同工況 PCW 開機台數	Operating PCW equipment count at design conditions
台	 units
單機 PCW 水量	PCW flow per unit
PCW 機台水溫差	PCW equipment water temperature difference
其他未重複計入烤箱熱	Other oven heat not counted elsewhere
製程潛熱參考值	Process latent-load reference
人體顯熱	Occupant sensible heat
W/人	W / person
人體潛熱	Occupant latent heat
外牆面積	External wall area
外牆 U 值	External wall U-value
樓板面積	Floor area
樓板 U 值	Floor U-value
U 值單位	U-value unit
樓板相鄰空間溫度	Temperature of space adjacent to floor
日射入室熱	Solar heat gain to room
其他未重複計入風機熱	Other fan heat not counted elsewhere
特氣 	Gas 
供氣表壓	Gas-source gauge pressure
定寸採用最低表壓	Minimum gauge pressure used for sizing
標準體積參考溫度	Standard-volume reference temperature
標準體積參考絕壓	Standard-volume reference absolute pressure
PV 標準抽氣量	PV standard extraction flow
真空管材（規格紀錄）	Vacuum pipe material (specification record)
三相線電壓	Three-phase line-to-line voltage
等效功率因數	Equivalent power factor
HP 換算的馬達效率	Motor efficiency for HP conversion
絕緣型式	Insulation type
環溫區間	Ambient-temperature range
同管載流線數區間	Loaded-conductor count in conduit
端子溫度額定	Terminal temperature rating
單程配線長度	One-way cable length
壓降上限	Voltage-drop limit
合格候選排序	Order of eligible candidates
 配電盤	 distribution board
排氣	Exhaust
採用形狀	Duct shape
方管長寬比上限	Maximum rectangular aspect ratio
排氣設計風量餘裕	Exhaust airflow design margin
風管空氣密度	Duct air density
風管空氣動力黏度	Duct air dynamic viscosity
風管粗糙度	Duct roughness
 水側負荷與水量	 water-side load / flow
密度	Density
比熱	Specific heat
動力黏度	Dynamic viscosity
水管流速上限	Water-pipe velocity limit
水管粗糙度	Water-pipe roughness
純水型式	Pure-water type
循環流量	Circulation flow
流速限制	Velocity limit
流速限制意義	Meaning of velocity limit
管材規格	Pipe material specification
電阻率／導電度	Resistivity / conductivity
TOC 規格	TOC specification
DO 規格	DO specification
溫度規格	Temperature specification
製程水氣資料	Process moisture data
額外進入室內的水氣	Additional moisture released into room
PV 壓力單位（自動換算）	PV pressure unit (automatic conversion)
電阻率參考來源	Source of resistivity reference
Darcy 自動	Darcy automatic
等效長 L/D	Equivalent length L/D
直接 K 值	Direct K coefficients
閉式循環	Closed circulation loop
壓損計算方式	Pressure-loss calculation method
管件等效長度餘裕	Fitting equivalent-length allowance
設備壓差資料	Equipment pressure-drop data
共用最低壓力	Shared minimum pressure
依氣體參考	Gas reference
｜進階定寸條件	 | Advanced sizing conditions
DCC 循環風量來源	Source of DCC circulation airflow
DCC 獨立循環風量	Independent DCC circulation airflow
出風高於供水的最小溫差	Minimum leaving-air approach above supply water
冬季計算範圍	Winter calculation boundary
冬季樓板相鄰溫度	Winter adjacent-floor temperature
冬季室內顯熱來源比例	Winter internal sensible-gain fraction
% 夏季內部得熱	% of summer internal gains
冬季室內產濕比例	Winter room-moisture fraction
% 夏季產濕	% of summer moisture generation
冬季另計日射／其他顯熱	Additional winter solar / other sensible gains
MAU+FFU+DCC (全外氣/無塵室)	MAU + FFU + DCC (100% OA / cleanroom)
FCU (風機盤管+外氣)	FCU (fan coil + outdoor air)
RCU (機房空調箱+外氣)	RCU (room cooling unit + outdoor air)
US RT (美制 3024 kcal/hr)	US RT (3024 kcal/hr)
JIS RT (日制 3320 kcal/hr)	JIS RT (3320 kcal/hr)
潔淨等級（紀錄）	Cleanliness class (record)
風量計算模式	Airflow calculation mode
寬度	Width
換氣次數	Air changes per hour
有效送風面風速	Effective supply-face velocity
送風面積／地板面積	Supply-face area / floor area
對共同低壓區壓差	Pressure difference to shared low-pressure zone
同時在室人數	Simultaneous room occupancy
人	 people
指定出口（需求檢核）	Specified leaving state (demand check)
氣體種類	Gas type
標準體積流量	Standard volumetric flow
XLPE 絕緣電纜 (90°C)	XLPE insulated cable (90°C)
PVC 一般電纜 (60°C)	PVC insulated cable (60°C)
35℃ 以下 (標準)	35°C or below (reference)
4根	4 conductors
5~6根	5–6 conductors
7~9根	7–9 conductors
10~20根	10–20 conductors
21~30根	21–30 conductors
31~40根	31–40 conductors
41根以上	41 or more conductors
最少並聯組數	Fewest parallel runs
最少總銅截面	Smallest total copper area
烤箱	Oven
風機	Fan
水泵	Pump
其中最大馬達（0 未知）	Largest motor in group (0 = unknown)
接地線工程覆核紀錄	Grounding-conductor review record
獨立輸入水量	Independent water-flow input
設計水溫差	Design water temperature difference
最低維持流速	Minimum maintained velocity
最高允許流速	Maximum permitted velocity
已知產濕量 kg/h	Known moisture generation (kg/h)
已知潛熱 kW	Known latent load (kW)
自訂規格	Custom specification
初估起點；依現場確認	Starting estimate; confirm on site
本路定寸管內表壓	Pipe gauge pressure for this line's sizing
設計流速來源	Source of design velocity
本路自訂流速上限（自訂時生效）	Custom velocity limit for this line (active in Custom mode)
獨立 DCC 循環	Independent DCC circulation
外氣處理基準（舊版）	Outdoor-air treatment basis (legacy)
截面風速	Face velocity
本路管內壓力	This line's pipe pressure
主案分季需求	Main-project seasonal demand
1｜通用單機邊界（送風目標，不等於室內負荷平衡）	1 | AHU boundary (supply target, not room-load balance)
2｜段落與加熱源（保留實體電熱器）	2 | Stages / heat sources (installed electric heaters retained)
3｜預冷 C1 與再冷 C2	3 | Precooling C1 / secondary cooling C2
4｜循環水洗濕膜（不視為蒸汽加濕）	4 | Recirculating wetted-media air washer (not steam)
5｜EC 風機、濾網與設備壓差	5 | EC fans / filters / equipment pressure drops
6｜H1／H2 熱源選擇	6 | H1 / H2 heat sources
加濕熱源｜濕膜／蒸汽／並用	Humidification | Wetted media / steam / combined
主案連動｜分季入口與送風需求	Main-project link | Seasonal inlet / supply demand
0 待提供	0 = data required
留空待提供	Leave blank if unknown
分段空調箱設計範例	Staged AHU design example
指定風量	Specified airflow
風量所在狀態	Airflow reference state
送風狀態（待核對）	Supply-air state (verification pending)
大氣絕壓	Absolute atmospheric pressure
夏季外氣濕度	Summer outdoor RH
冬季外氣濕度	Winter outdoor RH
單機送風目標乾球	AHU supply-air dry-bulb target
單機送風目標濕度	AHU supply-air RH target
H1／C1 位置	H1 / C1 order
H1 內部相對位置	H1 internal source order
H2 內部相對位置	H2 internal source order
H1 已配置電熱器	H1 installed electric heater
H2 已配置電熱器	H2 installed electric heater
電熱入空氣效率	Electric-heater efficiency to air
熱回收可用情境	Heat-recovery availability
一期未上線	Phase 1 unavailable
熱水盤管最小端差初估	Estimated hot-water coil minimum approach
H1 廠商同工況熱水能力，0 待提供	H1 manufacturer hot-water capacity at design conditions (0 = unknown)
H2 廠商同工況熱水能力，0 待提供	H2 manufacturer hot-water capacity at design conditions (0 = unknown)
C1 冰水供水	C1 chilled-water supply
C1 冰水回水	C1 chilled-water return
C1 ADP 高於供水	C1 ADP above supply water
C1 夏季自動模式出口目標	C1 summer automatic leaving target
C1 總表候選容量（待正本確認）	C1 schedule candidate capacity (confirm original data)
C2 冰水供水	C2 chilled-water supply
C2 冰水回水	C2 chilled-water return
C2 最低 ADP 高於供水	C2 minimum ADP above supply water
C2 總表候選容量（待正本確認）	C2 schedule candidate capacity (confirm original data)
水洗運轉方式	Air-washer operating mode
AMC 需求持續水洗	Continuous air washing for AMC
濕膜有效度（初估，待廠商提供）	Wetted-media effectiveness (estimate; manufacturer data required)
總表加濕能力（轉述，待正本核對）	Schedule humidification capacity (reported; confirm original)
廠商有效淋水面積，0 待提供	Manufacturer effective wetted area (0 = unknown)
廠商單位面積循環水量，0 待提供	Manufacturer circulation flow per area (0 = unknown)
廠商噴頭壓力水頭，0 待提供	Manufacturer nozzle pressure head (0 = unknown)
水面至噴頭高差，0 待提供	Water-level to nozzle elevation (0 = unknown)
循環管路／濾網損失，0 待提供	Circulation pipe / filter head loss (0 = unknown)
另計飛水／排污用水預留	Additional carryover / blowdown allowance
EC 風機配置台數	Installed EC fan count
單台額定電力（轉述，待型錄確認）	Rated power per fan (reported; confirm catalogue)
實際進入氣流的風機熱，0 待核	Actual fan heat to airflow (0 = verification pending)
空氣側壓差資料	Air-side pressure-drop data
尚未完整提供	Incomplete data
初／中效濾網終阻力	Pre / medium filter final resistance
H1 兩加熱元件阻力合計	H1 combined resistance of both heat sources
C1 盤管阻力	C1 coil resistance
水洗膜／擋水器阻力合計	Wetted media / eliminator combined resistance
C2 盤管阻力	C2 coil resistance
H2 兩加熱元件阻力合計	H2 combined resistance of both heat sources
PTFE HEPA 終阻力	PTFE HEPA final resistance
機外需求靜壓及其他阻力	Required external static pressure / other resistance
風機總效率（試算）	Estimated fan total efficiency
｜獨立熱水與電熱條件	 | Independent hot-water / electric-heat conditions
｜逐段出口條件（入口由上一段連動）	 | Stage leaving conditions (inlet linked from previous stage)
循環水洗濕膜	Recirculating wetted-media air washer
蒸汽額定產汽量，0 待提供	Rated steam output (0 = unknown)
蒸汽額定電力，0 待提供	Rated steam electrical power (0 = unknown)
蒸汽比焓（100°C 飽和初估）	Steam specific enthalpy (100°C saturated estimate)
蒸汽機補水溫度	Steam-generator feedwater temperature
蒸汽發生器效率	Steam-generator efficiency
蒸汽機給水資料	Steam-generator feedwater data
尚未確認	Unconfirmed
給水電導率，0 待提供	Feedwater conductivity (0 = unknown)
原廠允許電導率下限，0 待提供	Manufacturer minimum conductivity (0 = unknown)
原廠允許電導率上限，0 待提供	Manufacturer maximum conductivity (0 = unknown)
送風設定方式（來源以視窗上方為準）	Supply-target method (source shown above)
共用送風目標	Shared supply target
送風基準 CMH	Supply-reference CMH
已確認水洗泵輸入電力（留空未知）	Confirmed washer-pump input kW (blank = unknown)
主案連動版本	Linked main-project revision
各季外氣入口狀態	Seasonal outdoor-air inlet states
C1 → H1（比較方案）	C1 → H1 (comparison option)
二期可用（依已填能力）	Phase 2 available (entered capacity)
只在需要加濕時	Only when humidification is required
已填完整同風量資料	Complete data at the same airflow
 使用熱源	 heat source
共用回收水	Shared recovered-water source
本段熱水供水	Stage hot-water supply
本段熱水回水	Stage hot-water return
本段熱水最小端差	Stage hot-water minimum approach
本段電熱效率，0 沿用共同	Stage electric-heater efficiency (0 = shared value)
電熱式蒸汽	Electric steam humidifier
水洗＋電熱式蒸汽	Air washer + electric steam
不加濕	No humidification
原廠確認可用	Manufacturer-approved
去離子／超純水	Deionized / ultrapure water
本段獨立設定	Independent stage setting
 控制	 control
 指定出口濕度	 specified leaving RH
""")

TEXT[
    "控制與量測規劃（供圖審；非 PLC 可執行程式）\n1. OA：量測外氣 T/RH；模式依含濕量需求切換，不只按日曆季節。\n2. H1：配置進／出風 T；預熱目標由水洗需求反算。一般加濕模式使 C1 旁通，避免預熱後又不必要預冷；防凍需求需另訂例外。\n3. 水洗：出口 T/RH、循環水流量／泵回訊、水槽高／低／極低液位。加濕需求與 AMC 持續洗滌需求分開；AMC 效率依污染物及原廠資料，程式不保證去除率。\n4. 水槽：低位補水、高位停止；極低位停循環泵；排水／清洗期間依供應商程序停泵並聯鎖補排水，避免乾轉或邊排邊補失控。水質／換水門檻由 RO 與洗滌水管理規格決定。\n5. C2：盤管後、再熱前量測 T/RH 或露點。真實盤管出口未必飽和，不可一律把乾球當露點。\n6. H2／EC：風機後送風 T 作再熱修正，納入實際風機熱；H1/H2 電熱均需風量證明、獨立過溫切斷及必要延時散熱，不能只靠軟體訊號。\n7. 濾網／濕膜：依實際元件配置壓差量測；濕膜與擋水器功能不可直接互相替代。末端／風管壓力控制須與最低通風、風機轉速限制協調。\n8. 8 台 EC 各自故障／運轉回訊及適當保護；一台停機後能否維持風量，需 N−1 工況風機曲線，不能由台數自動保證。"
] = """Controls and instrumentation plan (design review only; not executable PLC logic)
1. OA: measure outdoor T/RH. Change mode by moisture demand, not just calendar season.
2. H1: measure inlet / leaving temperature. Derive preheat target from washer demand. Normally bypass C1 during humidification to avoid unnecessary precooling after preheat; specify frost-protection exceptions separately.
3. Washer: measure leaving T/RH, circulation flow, pump feedback and high / low / very-low tank levels. Separate humidification from continuous AMC washing. Removal efficiency needs pollutant-specific manufacturer data; this program does not guarantee it.
4. Tank: fill at low level, stop at high level, stop the pump at very-low level. Interlock fill / drain / pump during cleaning per supplier procedures. Set quality and water-change thresholds from RO / washer-water management specifications.
5. C2: measure T/RH or dew point after the coil and before reheat. A real leaving state is not necessarily saturated; dry bulb is not always dew point.
6. H2 / EC: use post-fan supply temperature for reheat trim, including actual fan heat. H1 / H2 electric heaters require proven airflow, independent overtemperature trips and any required cooldown delay.
7. Filters / media: measure differential pressure across actual components. Wetted media and droplet eliminators have different functions. Coordinate duct-pressure control with minimum ventilation and fan-speed limits.
8. Each of the 8 EC fans needs run / fault feedback and protection. Airflow after one fan fails requires an N−1 fan-curve check; installed count alone does not guarantee it."""

_add(r"""
Language / 語言	Language
相	 phases
個	 items
單位轉換	Unit conversion
濕空氣計算	Psychrometrics
兩股混風	Two-stream mixing
兩點空氣過程	Two-state air process
水量與熱量	Water flow / heat load
水管實際流速	Actual water-pipe velocity
風管定寸	Duct sizing
水管定寸	Water-pipe sizing
Kv 與壓差	Kv / pressure drop
耗電與費用	Energy / cost
焓 kJ/kg乾空氣	Enthalpy (kJ/kg dry air)
濕空氣密度 kg/m³	Moist-air density (kg/m³)
混合後狀態	Mixed-air state
乾空氣質量流率 kg/s	Dry-air mass flow (kg/s)
混合後實際風量 CMH	Mixed actual airflow (CMH)
第一股乾空氣 kg/s	Stream 1 dry-air mass flow (kg/s)
第二股乾空氣 kg/s	Stream 2 dry-air mass flow (kg/s)
計算基準	Calculation basis
入口	Inlet
出口	Outlet
加入空氣的淨熱量 kW	Net heat added to air (kW)
加入空氣的淨水氣 kg/h	Net moisture added to air (kg/h)
水溫差 K	Water temperature difference (K)
公式／限制	Formula / limitations
截面積 m²	Cross-sectional area (m²)
累積電量 kWh	Energy consumption (kWh)
費用（依自填幣別）	Cost (entered currency)
寬 mm	Width (mm)
高 mm	Height (mm)
計算直徑 m	Calculated diameter (m)
並聯支數	Parallel run count
風管形狀	Duct shape
所有工具可離線獨立計算；不必先完成廠房專案。	All tools work independently offline. A completed factory project is not required.
類別	Category
數值	Value
第一個值	First value
第二個值	Second value
第一股乾球 °C	Stream 1 dry bulb (°C)
第一股 RH %	Stream 1 RH (%)
第一股實際風量 CMH	Stream 1 actual airflow (CMH)
第二股乾球 °C	Stream 2 dry bulb (°C)
第二股 RH %	Stream 2 RH (%)
第二股實際風量 CMH	Stream 2 actual airflow (CMH)
入口乾球 °C	Inlet dry bulb (°C)
入口 RH %	Inlet RH (%)
出口乾球 °C	Outlet dry bulb (°C)
出口 RH %	Outlet RH (%)
入口實際風量 CMH	Inlet actual airflow (CMH)
求解目標	Solve for
黏度 Pa·s（供主案壓損）	Viscosity (Pa·s; main-project pressure losses)
形狀	Shape
液體比重 SG	Liquid specific gravity SG
每日運轉時數	Operating hours per day
計算天數	Number of days
平均負載比例 0～1	Average load fraction (0–1)
自填每 kWh 單價	Entered price per kWh
工程快算｜V5.5.5	Engineering quick tools | V5.5.5
條件已變更，按「計算」更新結果。	Inputs changed. Press Calculate to update results.
壓力換算不改變表壓／絕壓基準；標準氣體流量需另給溫壓。DN／英吋名目管徑不是實際內徑。	Pressure conversion preserves gauge / absolute basis. Standard gas flow requires its reference temperature and pressure. Nominal DN / inch sizes are not actual internal diameters.
結果可複製；進階設計可帶入主專案	Copy results, or transfer compatible data to the main project.
先計算	Calculate first
請先取得目前條件的結果。	Calculate the current inputs first.
（來源快照）	 (source snapshot)
小工具設定必須為 JSON 物件	Tool settings must be a JSON object
僅獨立計算	Independent calculation only
帶入目標｜	Transfer target | 
閥 Kv	Valve Kv
 切換工具會保留草稿；切換輸入組合時，有效結果可自動換算，否則請依新欄名重填。	 Tool switching retains drafts. Changing the input pair converts valid results automatically; otherwise re-enter values for the new labels.
請修正：	Please correct: 
工程快算 → 	Quick tool → 
工程快算	Engineering quick tools
收藏／取消收藏	Favorite / unfavorite
帶入目前專案…	Transfer to current project…
最近計算	Recent calculations
第一值 °C；第二值 %RH。	First: °C. Second: %RH.
第一值乾球 °C；第二值濕球 °C。	First: dry bulb °C. Second: wet bulb °C.
第一值乾球 °C；第二值露點 °C。	First: dry bulb °C. Second: dew point °C.
第一值 kJ/kg乾空氣；第二值 g/kg乾空氣。	First: kJ/kg dry air. Second: g/kg dry air.
 kPa｜空氣狀態／兩點淨變化	 kPa | Air states / net two-state change
本次結果已算出；歷史紀錄無法寫入。	Results calculated, but history could not be saved.
獨立工具	Independent tool
此工具可複製結果；沒有唯一對應的專案欄位，不自動覆寫。	Copy this result. There is no unique matching project field, so automatic transfer is unavailable.
第一值流量 LPM；第二值溫差 K。	First: flow LPM. Second: temperature difference K.
第一值熱量 kW；第二值溫差 K。	First: heat kW. Second: temperature difference K.
第一值熱量 kW；第二值流量 LPM。	First: heat kW. Second: flow LPM.
 限不可壓縮液體初估。	 Incompressible-liquid estimate only.
黏度必須是大於零的有限數值	Viscosity must be finite and positive
第一值流量 m³/h；第二值壓差 bar。	First: flow m³/h. Second: pressure drop bar.
第一值 Kv；第二值壓差 bar。	First: Kv. Second: pressure drop bar.
第一值流量 m³/h；第二值 Kv。	First: flow m³/h. Second: Kv.
\n其餘明細請查看報告。	\nSee the report for additional details.
 項／待資料 	 failed / data required: 
 項\n	 items\n
未儲存變更	Unsaved changes
整案尚未儲存	Workspace has not been saved
主案、空調箱或 A/B 有未儲存修改。確定捨棄並切換案件？	The main project, AHUs or A/B scenarios have unsaved changes. Discard them and switch projects?
整案未儲存	Unsaved workspace
關閉前儲存主案、所有空調箱及 A/B？\n無效輸入也可作為草稿保存。	Save the main project, all AHUs and A/B scenarios before closing?\nInvalid inputs can also be saved as drafts.
已由手動或其他來源取代	Replaced by manual input or another source
來源未開啟，只保留快照	Source closed; snapshot retained
過期	Outdated
與已保存來源條件一致	Matches saved source conditions
空調箱管理｜	AHU management | 
本案空調箱	AHUs in this project
專案已儲存	Project saved
尚未另存完整專案	Full workspace has not been saved
｜主案＋	 | Main project + 
 台空調箱＋A/B	 AHUs + A/B
不能開啟專案	Cannot open project
來源已修改，快照過期	Source changed; snapshot outdated
資料交換採來源快照；重新帶入前不會自動覆寫。	Transfers use source snapshots. Re-importing is required to update transferred values.
來源未	Source not 
整案／舊主案 JSON	Workspace / legacy main-project JSON
｜結果與來源狀態已同步	 | Results and source status updated
來源快照：	Source snapshot: 
；主案仍採上次回傳值，需重新帶入或確認為獨立設定。	; the main project retains the last transferred values. Re-import or confirm independent settings.
所有單機會隨整案保存；關閉單機視窗不會刪除設計。	All AHUs are saved with the workspace. Closing an AHU window does not delete its design.
新增空調箱	Add AHU
開啟選取單機	Open selected AHU
完整專案（主案、空調箱、A/B）	Full workspace (main project, AHUs, A/B)
整案復原快照未保存：	Workspace recovery snapshot was not saved: 
來源快照	Source snapshot
：運轉 	: operating 
設備表匯入與需求分析 V5.5.5	Equipment schedules / demand analysis V5.5.5
2 匯入設備表	2 Import schedule
範例啟用欄為0；實際設備設為1。每張表最多10,000筆。	Examples are disabled (0). Set actual equipment to enabled (1). Limit: 10,000 rows per sheet.
需求彙總會顯示在這裡	Demand summary appears here
供應群組／供電	Supply group / supply
同時需求	Simultaneous demand
電流／容量／實際量	Current / capacity / actual flow
匯出分析TXT	Export analysis TXT
匯出明細JSON	Export data JSON
等待新的設備表完成檢查	Waiting for the new schedule validation
匯入設備數據	Import equipment data
已匯出範本。保留欄名，填實際數值；要納入的列設為啟用1。	Template exported. Keep the headers and enter actual values. Enable included rows with 1.
選CSV範本存放資料夾	Choose a folder for CSV templates
已匯出七個CSV範本。匯入前選CSV對應系統。	Seven CSV templates exported. Select the matching system before importing a CSV.
正在檢查 	Checking 
筆設備，	 equipment rows, 
個分組｜連接	 groups | Connected 
kW，同時	kW, simultaneous 
kW｜插座	kW | Sockets 
已分析 	Analyzed 
；略過	; skipped 
筆未啟用列。尺寸為候選，明細列出採用條件與待資料。	 disabled rows. Sizes are candidates; details list assumptions and missing data.
已匯出全部分組與設備明細。	All groups and equipment details exported.
已匯出全部數值明細。	All numerical details exported.
設備表 → 需求彙總	Equipment schedule → Demand summary
匯出範本，填實際設備，再匯入檢查。各系統與供應群組會分開計算。	Export a template, enter actual equipment, then import for validation. Systems and supply groups are calculated separately.
1 匯出Excel範本	1 Export Excel template
另存CSV範本	Export CSV templates
Excel一次讀全部系統；CSV依左方選擇。	Excel reads all systems. CSV uses the selected system.
分組條件、公式與設備明細（點選上方一列查看）	Group conditions, formulas and equipment (select a row above)
插座數僅統計點位；支路按單台額定負載。	Sockets count connection points only. Branch sizing uses each unit's rated load.
設備表	Equipment schedule
匯入未完成，請修正下方列別問題。	Import incomplete. Correct the row issues below.
Excel範本	Excel template
分析報告	Analysis report
分析明細	Analysis data
電極	Electrode
輸入已變更；不沿用舊計算書。	Inputs changed; the old report is no longer valid.
灰線 RH 10 / 30 / 50 / 70 / 90 / 100%｜橘：加熱；藍：冷卻；綠：加濕	Gray: RH 10 / 30 / 50 / 70 / 90 / 100% | Orange: heating; blue: cooling; green: humidification
各季送風狀態（固定採用）	Seasonal supply-air state (fixed basis)
進階初估值已帶入；停用欄位只保留草稿，不參與該功能的驗證。	Advanced reference values are populated. Disabled fields retain drafts and do not participate in that function's validation.
：H1 等效全電熱需求 	: H1 equivalent all-electric demand 
 / 配置 	 / installed 
 kW\n水洗蒸發 	 kW\nWasher evaporation 
本季額定初估通過	Seasonal rated-capacity estimate passed
需求流程｜	Demand process | 
 kPa｜P0 外氣；其餘點號對應上表	 kPa | P0 outdoor air; other point IDs refer to the table above
基本畫面外仍採用：	Hidden settings still in use: 
\n整機：	\nComplete AHU: 
保留設定，未採用：	Retained but inactive settings: 
獨立送風條件；未宣告主案連動，尚未帶入快照	Independent supply conditions; no main-project link or imported snapshot
空調箱｜分段式單機送審校核	AHU | Staged single-unit design verification
1 設計條件	1 Design conditions
2 分段結果與線圖	2 Stage results / chart
4 控制／需補資料	4 Controls / missing data
分段空調箱設計｜V5.5.5	Staged AHU design | V5.5.5
未儲存空調箱	Unsaved AHU
關閉前儲存分段空調箱？\n是：儲存；否：捨棄；取消：返回。	Save this staged AHU before closing?\nYes: save. No: discard. Cancel: return.
設為本案獨立設計	Set as independent design
保留目前所有單機設定，解除來源主案需求快照。\n後續回傳會明列為本案獨立設計，請自行確認服務範圍。	Keep all AHU settings and detach the source-demand snapshot.\nFurther transfers are marked as an independent design; confirm the served boundary.
輸入變更，等待單機檢核…	Inputs changed. Awaiting AHU validation…
等待目前輸入檢核	Awaiting validation of current inputs
開啟	Open
另存單機	Save AHU as
重算	Recalculate
匯出校核書	Export verification report
夏季逐段設定	Summer stage settings
冬季逐段設定	Winter stage settings
H1/H2 熱源	H1 / H2 heat sources
逐段出口	Stage leaving states
段落	Stage
進風 °C	Inlet °C
進風 %RH	Inlet %RH
出風 °C	Leaving °C
出風 %RH	Leaving %RH
空氣側 kW（＋熱／−冷）	Air-side kW (+ heating / − cooling)
3 校核書	3 Verification report
所屬主案不同，回傳已停止	Main-project owner differs; transfer blocked
；混風主案不能直接當全外氣箱，請獨立指定入口	; a mixing project cannot be treated as a 100% OA AHU. Specify its inlet independently.
案件不同	Different project
此單機不屬於目前主案，不能直接帶入。	This AHU does not belong to the current main project. Direct import is blocked.
此單機屬於另一主案，回傳已停止。	This AHU belongs to another main project. Transfer is blocked.
來源快照已過期	Source snapshot is outdated
請先重新帶入目前主案需求；若要使用獨立單機設計，請明確選擇「設為本案獨立設計」。	Re-import current main-project demand first, or explicitly select Set as independent design.
\n來源狀態：	\nSource status: 
儲存失敗	Save failed
開啟失敗	Open failed
未儲存	Unsaved
捨棄本單機未儲存修改並開啟？	Discard this AHU's unsaved changes and open another?
帶入主案分季送風需求	Import main-project seasonal supply demand
預覽回傳水量／額定電力	Preview water / rated-power transfer
獨立熱水	Independent hot-water source
有未達額定條件，請查看校核書；列出的狀態是需求，不是實機性能。	Some rated-capacity checks failed. See the report. Displayed states are requirements, not actual undersized-equipment performance.
分段平衡及額定初估通過；仍待廠商性能資料核對。	Stage balances and rated-capacity estimates passed. Manufacturer performance confirmation is still required.
關閉並捨棄本單機未儲存修改？	Close and discard this AHU's unsaved changes?
主案連動	Main-project link
無法帶入	Cannot import
無法回傳	Cannot transfer
單機專案	AHU project
匯出失敗	Export failed
空調箱｜分段需求反算	AHU | Stage-demand calculation
定位問題	Locate issue
顯示進階／廠商資料	Show advanced / manufacturer data
復原帶入	Undo import
單機指定風量校核：保留電熱器與熱水盤管，逐段反算需求，再比對既有容量。\n每段入口沿用前段出口；H1/H2 純加熱的 RH 自動計算。電極式蒸汽列於加濕設備，與直接電熱分開。	Verify an AHU at specified airflow: retain electric heaters and hot-water coils, calculate stage demand and compare with installed capacity.\nEach inlet follows the previous outlet. RH after sensible heating is automatic. Electrode steam belongs to humidification, separately from direct electric heat.
另存線圖 PNG	Save chart PNG
下列為需求狀態；容量未達時不代表實機出風	The states below are requirements. They do not predict actual leaving air when capacity is insufficient.
水洗近似等焓：降低乾球、增加水氣；空氣側 0 kW 不代表沒有加濕。	Air washing is approximately adiabatic: dry bulb falls and moisture rises. An air-side value of 0 kW does not mean no humidification.
需補資料：風量的參考狀態、送風與室內目標區別、H1/H2 內部相對位置、C1/C2 正本選型、濕膜有效度與面積／淋水密度、擋水器性能、噴頭壓力、水盤尺寸、熱回收同工況能力、各段終阻力、風機曲線與實際入室熱。\n所有原廠性能資料應以本專案同工況選型文件確認。	Data required: airflow reference state; supply versus room targets; H1/H2 internal order; original C1/C2 selections; wetted-media effectiveness, area and irrigation density; eliminator performance; nozzle pressure; tank size; heat-recovery capacity at design conditions; final stage resistances; fan curves and actual heat to the room.\nConfirm all manufacturer performance with selection documents for this project's conditions.
與目前主案工程邊界一致	Matches current main-project engineering boundary
來源快照已過期，請重新帶入主案需求	Source snapshot outdated. Re-import main-project demand.
\n帶入夏冬入口、送風目標、乾空氣流率與冰水供回水。\n逐段指定目標與設備額定保留，可能需要調整才能符合新的送風需求。	\nImport summer / winter inlet, supply targets, dry-air mass flow and chilled-water supply / return.\nSpecified stage targets and equipment ratings remain; adjust them if necessary for the new supply demand.
帶入主畫面外氣	Import main-window outdoor conditions
未安裝 matplotlib；表格與校核書仍可使用。	Matplotlib unavailable. Tables and verification reports still work.
條件未成立：	Invalid conditions: 
空調箱｜	AHU | 
來源主案：	Source main project: 
自動：H1 依加濕需求預熱；C1 按預冷目標（需加濕時旁通）；C2 依送風含濕比／溫度反算；H2 補足送風溫度並扣除風機熱。\n指定：直接檢核本段出口條件；旁通：出口沿用入口。入口由上一段連動，結果表另列各段實際採用的需求點。	Automatic: H1 preheats for humidification. C1 uses its precooling target (bypassed when humidifying). C2 solves supply humidity ratio / temperature. H2 trims supply temperature after deducting fan heat.\nSpecified: validate this stage's leaving target. Bypass: leaving state equals inlet. Each inlet follows the previous outlet; the result table lists the adopted demand states.
空調箱 	AHU 
選擇熱水＋電熱可由熱回收優先分擔、電熱補足；回收水未上線或未填能力時，不會假定有可用熱量。	Hot water + electric heat uses recovery first, then electric backup. No recovered heat is assumed when unavailable or without an entered capacity.
所屬主案：	Owner main project: 
使用者輸入	User input
單位等值換算	Equivalent unit conversion
原廠資料	Manufacturer data
流量自動定寸	Automatic flow-based sizing
自動參考：一／二段 ADP 裕度 1 K、露點裕度 1 K；目前值可在進階檢視。MAU 處理外氣，FFU／DCC 為室內循環；FCU／RCU 採入口混合等效模型。	References: first / second-stage ADP approach 1 K, dew-point margin 1 K. View current values in Advanced mode. MAU treats outdoor air; FFU / DCC recirculate room air. FCU / RCU use an equivalent inlet-mixing model.
利用係數 U=0.6、維護係數 M=0.8、人員顯熱 75 W／潛熱 55 W 是初估起點，實際採用值在進階欄位。未知製程產濕不當成已確認零產濕。	Starting estimates: U = 0.6, M = 0.8, occupant sensible / latent heat = 75 / 55 W. Advanced fields show adopted values. Unknown process moisture is not a confirmed zero.
PV 三種單位皆為絕壓，切換會換算數字。CMH 在此為標準狀態流量。特氣／PV 僅作流速初估；材質及真空性能需另核。	All three PV pressure units are absolute and convert the entered value. CMH here is standard-state flow. Gas / PV sizing is a velocity estimate only; verify material and vacuum performance separately.
kW 是電力輸入；HP 是軸輸出。切換單位會自動換算並保留原負荷。原專案線表僅初估，接地及保護仍需覆核。	kW is electrical input; HP is shaft output. Unit changes convert values and preserve the load. Cable tables are estimates; grounding and protection still need review.
已帶入各類排氣初估風速；進階可修改實際上限、物性及風量餘裕。	Reference exhaust velocities are populated. Advanced settings adjust velocity limits, properties and airflow margin.
水量可依負荷自動算。UPW／DI／RO 電阻率以 25°C 參考值帶入；水型名稱不能保證水質。自訂規格可覆寫；TOC／DO 仍依製程確認。	Water flow can be calculated from load. UPW / DI / RO resistivity references are at 25°C; a water-type name does not guarantee quality. Custom specifications can override references. Confirm TOC / DO for the process.
藍：冷卻  橘：加熱  綠：加濕\n灰線：10 / 30 / 50 / 70 / 90 / 100% RH	Blue: cooling. Orange: heating. Green: humidification.\nGray: 10 / 30 / 50 / 70 / 90 / 100% RH
採用 	Adopted 
 支並聯 × ID 	 parallel runs × ID 
範圍	Boundary
MCHW 最不利路徑	MCHW critical path
路徑總直管長（水側含供回）	Total straight length (water: supply and return)
人員 	Occupants 
＋製程 	 + process 
＝室內合計 	 = room total 
 kg/h\n除濕負荷參考 	 kg/h\nReference dehumidification load 
 kW；外氣水氣由空調盤管另算。	 kW; outdoor-air moisture is calculated separately at the HVAC coils.
基本先填現場條件｜F5 重新計算	Enter site conditions first | F5 recalculates
啟動中	Starting
混風輔助線	Mixing reference line
 kW     產濕  	 kW     Moisture  
 kg/h\n補償外氣  	 kg/h\nMakeup outdoor air  
 CMH     DCC 夏冬較大需求  	 CMH     DCC maximum seasonal demand  
氣流配置：OA → MAU 兩段盤管 → 再熱／加濕 → 室內；室內 → DCC → FFU → 室內。MAU 外氣另需對應排氣／洩壓。	Airflow: OA → MAU two-stage coils → reheat / humidification → room; room → DCC → FFU → room. MAU outdoor air requires matching exhaust / relief.
氣流配置：OA＋RA → 混合入口 → 盤管 → 再熱／加濕 → SA → 室內；圖上虛線為混風輔助線。	Airflow: OA + RA → mixed inlet → coils → reheat / humidification → SA → room. Dashed chart lines show mixing.
 kW、產濕 	 kW, moisture 
等待目前輸入通過檢核	Awaiting valid current inputs
先選系統，再填最不利路徑長度。流量、管徑與摩擦自動帶入。	Choose a system and enter its critical-path length. Flow, size and friction are populated automatically.
選擇系統	Select system
管件較少 10%	Few fittings: 10%
管件較多 50%	Many fittings: 50%
簡易公式：直管摩擦 × (1＋管件等效長度餘裕)＋已知設備壓差＋適用靜揚程。\n10／30／50% 只是明示的方案初估，並非管件標準；高阻力閥／濾網等另填設備。\n不知道設備壓差時只報管路小計。詳細 K、L/D、阻力率與效率可切換詳細／進階。	Simple: straight-pipe friction × (1 + fitting equivalent-length allowance) + known equipment pressure drop + applicable static head.\n10 / 30 / 50% are stated planning assumptions, not fitting standards. Enter high-loss valves / filters separately.\nUnknown equipment losses give a piping subtotal only. Detailed / Advanced mode exposes K, L/D, loss rate and efficiency.
複製全文	Copy full report
另存完整驗算資料 JSON	Save full calculation data JSON
流程圖季節	Process-chart season
編輯共同氣候	Edit shared climate
另存流程圖 PNG	Save process chart PNG
 kPa｜IN入口 C1/C2盤管 HT加熱 SA送風	 kPa | IN inlet, C1/C2 coils, HT heating, SA supply
簡易初估：未提供設備壓差時，表格只列管路小計。	Simple estimate: without equipment pressure drops, the table shows piping subtotal only.
沿用詳細管件／設備設定；切換簡易不會刪除詳細設定。	Detailed fitting / equipment settings retained. Simple mode does not delete them.
  效率採 	  Efficiency: 
；流量由各系統連動。	; flows are linked from each system.
 ALPM｜絕壓 	 ALPM | Absolute pressure 
 kPa｜實速 	 kPa | Actual velocity 
 A／設計 	 A / design 
 mm²/相	 mm²/phase
 CMH（含餘裕），	 CMH (including margin), 
含設備	Including equipment
未含設備	Excluding equipment
未安裝 matplotlib：數值及報告仍可使用；安裝後可開啟流程圖。	Matplotlib unavailable: calculations and reports still work. Install it to enable process charts.
本頁初估係數已帶入；可按「進階模式」查看數值。	This page's reference coefficients are populated. Choose Advanced mode to view them.
帶入此等級 ACH／壓差參考值	Apply this class's ACH / pressure references
潛熱＝水氣增加帶來的除濕負荷，並非一般機台發熱。\n人員會自動帶入；製程只算散入室內的水氣。\n採 2501 kJ/kg：1 kg/h ≈ 0.695 kW；1 kW ≈ 1.439 kg/h。	Latent heat is the dehumidification load from added moisture, not ordinary equipment heat.\nOccupant moisture is automatic. Count only process moisture released into the room.\nAt 2501 kJ/kg: 1 kg/h ≈ 0.695 kW; 1 kW ≈ 1.439 kg/h.
支×	 runs × 
，能力 	, capacity 
含輸入設備壓差	Including entered equipment pressure drop
管路小計，未含設備	Piping subtotal, excluding equipment
｜軸功率 	 | Shaft power 
畫面外仍採用的自訂條件：	Hidden custom conditions still in use: 
設定外氣與室內目標；夏季負荷摘要及分季流程圖各自標明計算工況。	Set outdoor and room targets. Summer-load summaries and seasonal charts identify their calculation conditions.
先選系統與區域循環需求；設備容量為需求候選，各季送風量仍需滿足熱濕平衡。	Choose the system and zone circulation demand. Equipment capacities are candidates; seasonal supply airflow must satisfy heat and moisture balances.
設備熱、照明與人員分開計算；潛熱只填散入室內的製程水氣，避免重複計入外氣。	Equipment, lighting and occupants are separate. Enter only process moisture released into the room as latent load; avoid double-counting outdoor moisture.
標準流量先換算管內實際流量；壓力及流速可於進階模式逐路設定。PV 壓力為絕壓。	Standard flow converts to actual pipe flow. Advanced mode sets pressure and velocity per line. PV pressure is absolute.
kW 是輸入電力，HP 是機械輸出；候選線徑需再核對敷設與保護條件。	kW is electrical input; HP is mechanical output. Verify installation and protection conditions for conductor candidates.
名目風量先加設計餘裕，再定寸；管形與寬高比目前共用於所有排氣系統。	Add design margin to nominal airflow before sizing. Shape and aspect ratio are shared across exhaust systems.
連動負荷時以熱量與 ΔT 反算水量；手填水量保留但不採用。水物性共用於全部水迴路。	Linked-load mode calculates water flow from heat and ΔT. Manual flow is retained but inactive. Fluid properties are shared across water loops.
操作未完成，請修正條件後重新計算。	Operation incomplete. Correct the inputs and recalculate.
操作未完成	Operation incomplete
廠務工程工作台 V5.5.5	Facility Studio Workbench V5.5.5
輸入更新中，等待產濕檢核…	Inputs updating. Awaiting moisture validation…
輸入已變更；檢核完成後更新報告。	Inputs changed. The report updates after validation.
依水型帶入參考值，非原廠保證值	Reference based on water type; not a manufacturer guarantee
不支援的復原格式	Unsupported recovery format
復原欄位不完整	Recovery fields are incomplete
圖形功能	Charts
請先安裝 matplotlib。	Install matplotlib first.
操作未完成；請查看錯誤訊息。	Operation incomplete. See the error message.
共同條件 → 工程檢核 → 設計摘要	Shared conditions → Engineering checks → Design summary
新專案	New project
儲存整案	Save workspace
套用本頁初估係數	Apply page reference values
快速工程工具	Quick tools
來源／比較／復原	Sources / comparison / recovery
匯出可列印摘要	Export printable summary
啟動檢核中…	Startup validation…
重新計算	Recalculate
輸入已變更，等待檢核…	Inputs changed. Awaiting validation…
輸入更新中…	Inputs updating…
輸入已變更，等待檢核	Inputs changed. Awaiting validation
介面修改	Edited in interface
與同一筆製程產濕量同步（2501 kJ/kg 初估）	Linked to the same process-moisture quantity (2501 kJ/kg estimate)
復原內容格式不合法	Invalid recovery content format
壓損復原內容格式不合法	Invalid pressure-loss recovery format
依潔淨等級套用初估係數，仍需確認設計條件	Class-based reference coefficients; confirm design conditions
報告已複製	Report copied
 的 25°C 初估參考；非原廠保證	 reference at 25°C; not manufacturer-guaranteed
輸入已變更，待重新計算	Inputs changed; recalculation required
等待目前條件檢核	Awaiting current-condition validation
目前為自動水型參考；原自訂證據已保留	Automatic water-type reference active; previous custom evidence retained
條件未通過，請修正輸入。	Validation failed. Correct the inputs.
整體尚未完成；保留有效分頁：	Overall calculation incomplete. Valid pages retained: 
部分結果可用；	Partial results available; 
已匯出	Exported
使用瀏覽器開啟，可列印或另存 PDF。	Open in a browser to print or save as PDF.
文字報告	Text report
設計報告已匯出	Design report exported
另存失敗	Save as failed
圖形匯出失敗	Chart export failed
廠務工程工作台  V5.5.5	Facility Studio Workbench V5.5.5
空調箱管理	AHU management
條件未通過檢核，流程圖暫停	Invalid conditions; process chart paused
目前條件未通過檢核，未產生可用報告。\n\n	Current conditions failed validation. No usable report generated.\n\n
 項待確認｜	 items to confirm | 
｜結果與報告已同步	 | Results and report updated
請修正輸入	Correct the inputs
可列印設計摘要	Printable design summary
 最不利路徑（流量：	 critical path (flow: 
條件未通過檢核	Conditions failed validation
待修正：	Corrections required: 
檢核完成｜	Validation complete | 
未另存預設專案	Unsaved default project
本頁待修正：	Page corrections required: 
\n\n帶入後：	\n\nAfter transfer: 
共用水物性會同時影響 MCHW、CHW、DCCW、PCW、HW；請確認所有迴路為相同介質及工況。	Shared fluid properties affect MCHW, CHW, DCCW, PCW and HW. Confirm all loops use the same fluid and conditions.
共用形狀／寬高比會同時影響 GEX、SEX、AEX、VEX、HEX。	Shared shape / aspect ratio affects GEX, SEX, AEX, VEX and HEX.
（估算草稿）\n待確認：	 (estimate draft)\nConfirm: 
確認帶入此主案	Confirm transfer to this project
專案管理｜參數來源與方案比較	Project management | Sources / scenario comparison
請分別固定方案 A 與 B。	Capture scenarios A and B first.
\n項目：A → B（B−A）	\nItem: A → B (B−A)
帶入前檢核未通過	Pre-transfer validation failed
目的主案：	Target main project: 
目前值	Current value
文件／說明	Document / description
來源記錄時間 UTC	Source-record time UTC
方案 A／B	Scenarios A / B
備份與計算依據	Backup / calculation basis
工程資料表中繼資料（非現行法規認證）\n	Engineering reference-table metadata (not regulatory certification)\n
來源與方案｜	Sources / scenarios | 
數值已改變	Value changed
請重新選取目前值並核對文件後再標記來源。	Select the current value again and verify the document before marking its source.
請先改為自訂水質規格，再將同工況數值標記為原廠資料。	Choose custom water-quality specifications before marking matching-condition values as manufacturer data.
需補資料	Data required
請填入原廠文件或選型編號	Enter the manufacturer document or selection reference.
計算依據識別 A 	Calculation-basis ID A 
\n變更的設計條件	\nChanged design conditions
\n原主案已保留，請修正目的欄位條件後再帶入。	\nOriginal project retained. Correct target-field conditions before transferring.
 → 設計 	 → design 
 CMH（含主案風量餘裕）。	 CMH (including main-project airflow margin).
舊資料未記時間	Legacy record has no timestamp
不能復原	Cannot recover
預設值是估算起點；原廠資料需留下文件／選型編號。來源註記不會把初估升級成認證。	Defaults are starting estimates. Record manufacturer document / selection references. A source note does not certify an estimate.
更新來源	Update source
重新讀取	Reload
匯出比較紀錄	Export comparison
快照保留當時計算條件與雜湊；主案修改不會自動覆寫 A／B。請用相同計算邊界比較。	Snapshots preserve conditions and hashes. Main-project changes do not overwrite A/B. Compare the same calculation boundaries.
每 30 秒保存整案復原快照（主案、空調箱、A/B、來源）；手動覆存保留上一份 .json.bak。\n無效輸入可保存為草稿，復原後仍會重新檢核。	Workspace recovery snapshots (main project, AHUs, A/B, sources) save every 30 seconds. Manual overwrites keep the previous .json.bak.\nInvalid inputs may be saved as drafts and are revalidated on recovery.
選擇復原快照	Choose recovery snapshot
舊快照	Legacy snapshot
比較紀錄	Comparison record
復原快照	Recovery snapshot
將目前主案固定為 	Capture current main project as 
套用後物性：ρ=	Properties after transfer: ρ = 
""")

# Historical report spelling is normalized at its existing output boundary.
for _source, _value in tuple(TEXT.items()):
    TEXT.setdefault(_source.replace("热", "熱").replace("侧", "側"), _value)

# Individual lines also cover control plans with a non-default fan count.
TEXT["控制與量測規劃（供圖審；非 PLC 可執行程式）"] = (
    "Controls and instrumentation plan (design review only; not executable PLC logic)"
)
TEXT["1. OA：量測外氣 T/RH；模式依含濕量需求切換，不只按日曆季節。"] = (
    "1. OA: measure outdoor T/RH. Change mode by moisture demand, not just calendar season."
)
TEXT[
    "2. H1：配置進／出風 T；預熱目標由水洗需求反算。一般加濕模式使 C1 旁通，避免預熱後又不必要預冷；防凍需求需另訂例外。"
] = "2. H1: measure inlet / leaving temperature. Derive preheat target from washer demand. Normally bypass C1 during humidification to avoid unnecessary precooling after preheat; specify frost-protection exceptions separately."
TEXT[
    "3. 水洗：出口 T/RH、循環水流量／泵回訊、水槽高／低／極低液位。加濕需求與 AMC 持續洗滌需求分開；AMC 效率依污染物及原廠資料，程式不保證去除率。"
] = "3. Washer: measure leaving T/RH, circulation flow, pump feedback and high / low / very-low tank levels. Separate humidification from continuous AMC washing. Removal efficiency needs pollutant-specific manufacturer data; this program does not guarantee it."
TEXT[
    "4. 水槽：低位補水、高位停止；極低位停循環泵；排水／清洗期間依供應商程序停泵並聯鎖補排水，避免乾轉或邊排邊補失控。水質／換水門檻由 RO 與洗滌水管理規格決定。"
] = "4. Tank: fill at low level, stop at high level, stop the pump at very-low level. Interlock fill / drain / pump during cleaning per supplier procedures. Set quality and water-change thresholds from RO / washer-water management specifications."
TEXT[
    "5. C2：盤管後、再熱前量測 T/RH 或露點。真實盤管出口未必飽和，不可一律把乾球當露點。"
] = "5. C2: measure T/RH or dew point after the coil and before reheat. A real leaving state is not necessarily saturated; dry bulb is not always dew point."
TEXT[
    "6. H2／EC：風機後送風 T 作再熱修正，納入實際風機熱；H1/H2 電熱均需風量證明、獨立過溫切斷及必要延時散熱，不能只靠軟體訊號。"
] = "6. H2 / EC: use post-fan supply temperature for reheat trim, including actual fan heat. H1 / H2 electric heaters require proven airflow, independent overtemperature trips and any required cooldown delay."
TEXT[
    "7. 濾網／濕膜：依實際元件配置壓差量測；濕膜與擋水器功能不可直接互相替代。末端／風管壓力控制須與最低通風、風機轉速限制協調。"
] = "7. Filters / media: measure differential pressure across actual components. Wetted media and droplet eliminators have different functions. Coordinate duct-pressure control with minimum ventilation and fan-speed limits."
TEXT[
    "8. 8 台 EC 各自故障／運轉回訊及適當保護；一台停機後能否維持風量，需 N−1 工況風機曲線，不能由台數自動保證。"
] = "8. Each of the 8 EC fans needs run / fault feedback and protection. Airflow after one fan fails requires an N−1 fan-curve check; installed count alone does not guarantee it."
TEXT[
    "台 EC 各自故障／運轉回訊及適當保護；一台停機後能否維持風量，需 N−1 工況風機曲線，不能由台數自動保證。"
] = "EC fans each need run / fault feedback and protection. Airflow after one fan fails requires an N−1 fan-curve check; installed count alone does not guarantee it."

# Runtime captions after optional-zero fields were migrated to blank values.
TEXT["廠商噴頭壓力水頭，留空待提供"] = "Manufacturer nozzle pressure head; leave blank if unknown"
TEXT["水面至噴頭高差，留空待提供"] = "Water-surface-to-nozzle elevation; leave blank if unknown"
TEXT["循環管路／濾網損失，留空待提供"] = "Circulation pipe / filter head loss; leave blank if unknown"

# Offline beginner walkthrough entry (delivery revision 2).
TEXT.update({
    "新手教學": "Beginner tutorial",
    "教學檔案位置：\n": "Tutorial file location:\n",
    "無法開啟離線教學：\n": "Cannot open the offline tutorial:\n",
})
