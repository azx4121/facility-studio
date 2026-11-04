# 直接照度配置與報告（候選功能）

這是平均流明法之外的獨立模式。使用匯入的光度資料逐點計算**直接光**，不把流明法平均值畫成分布圖，也不重建使用者的 DIALux 報表。

## 操作

1. 在「照明照度」按「配置／直接照度」。重複按鈕會回到既有視窗，不清掉正在編輯的內容。
2. 匯入 IES 或 LDT。來源表顯示 ID、檔名、燈具名稱及原始檔案 SHA-256。未匯入有效來源前不能計算。
3. 輸入房間長寬、工作面距地面高度、邊緣內縮、X/Y 取樣數、維護係數。所有幾何距離以 m 計，維護係數預設 1，初始與維護後結果分開列出。
4. 直接編輯 CSV 配置，或明確選來源 ID、列數、欄數、安裝高度後產生規則排列，再修改。CSV 欄位為 `ID,x,y,z,yaw,scale`。原點在左下，+x 向右、+y 向上，+z 朝上。全部燈具朝下；只支援繞垂直軸旋轉，不支援傾斜。yaw=0 時檔案 C0 指向 +x，C90 指向 +y；正 yaw 由上往下看逆時針。C0 不代表燈具外殼的正面，必須由型錄或原廠確認安裝方向。
5. 按「計算直接照度」。畫面顯示位置、檔案 C0 方向、格點色階及等照度線。平均／最小／最大及均勻度只代表這批格點，不能視為連續空間極值或法規合格。
6. 匯出 HTML、逐點 CSV 或完整結果 JSON。HTML 可由瀏覽器列印為 A4 直式報表。結果包含方法版本、配置、來源雜湊、網格及初始／維護後照度。任何輸入或來源變更都會清除舊結果；存檔對話框期間變更也會阻止匯出。

CSV/JSON 是結果和追溯交付；此版尚未提供專案 JSON 重新載入。匯入的檔案是當時內容的快照，不會暗中讀取日後改寫的同名檔案。原有平均流明法與跨模組功率帶入維持獨立，沒有把直接照度誤當成含反射的平均結果。

## 支援的嚴格子集

- IES：UTF-8/ASCII、LM-63-1995 或 2002、Type C、`TILT=NONE`。尺寸 feet/metres 轉成 m。接受 C0 單一旋轉對稱、0–90、0–180 或 0–360；1995 另接受 90–270 的平面對稱格式，保留原檔方向並只鏡射缺少的半圓，不旋轉配光。2002 已取消此角域，因此宣告 2002 的 90–270 檔仍拒絕。垂直角接受完整下半球、上半球或全球。未提供的半球為零，不鏡射。負數形狀尺寸、其他版本和 TILT 不支援。
- LDT：UTF-8/ASCII、單一燈組、Isym 0/1/2/4、均勻全圓 C 平面清單、測量傾角 0。Isym 3、多燈組、Dc=0（包括旋轉對稱單平面）及廠商延伸格式尚未支援。拒絕，不猜修格式。
- 光強資料需有限、非負、矩陣數量正確，角度遞增，重合極點／C0-C360 接縫一致。只接受精確的半球／對稱端點，不把近零角誤當零。
- 讀取上限 4 MiB，展開光強矩陣最多500,000個值。全案匯入矩陣合計最多2,000,000個值；每案最多32來源、200盞，網格2–80點／軸。未實作遠場距離認證；過近或大型燈具要另做驗證。檔案尺寸全為零時會提醒其為點光源記法，不能證明實體尺寸或遠場有效距離。0.01 m 只是數值幾何下限，不是精度保證。

## 計算及單位

每盞對水平工作面的初始照度：

`E = I(C, γ) × cos(γ) / r² × scale`

I 以 cd，r 以 m，E 為 lx。光強在已提供的 C/γ 角資料間雙線性內插。逐盞加總後，只乘一次維護係數 M。不使用流明法的利用係數 U。光輸出倍率不代表耗電也依相同比例下降。

IES 的光強是 cd，乘檔案 candela multiplier 與 ballast factor；不再乘燈數或流明。LDT 的相對與絕對資料都是 cd/klm，乘 conversion factor × 該燈組**總**參考流明/1000；不再乘燈數或 LOR。IES 光源流明不冒充整燈流明。負燈數的絕對 LDT 依規範使用整燈流明。

格點採內縮矩形的均勻格心。等照度線在格點間使用固定三角形分割的線性內插，只到取樣範圍，不外插到牆邊。需加密網格、檢查收斂，避免漏掉窄配光峰值及暗區。

## 未計算的項目

反射光、遮擋陰影、日光、UGR、各牆面／天花板反射結果及法規符合全部未計算。這不是 DIALux 等價引擎。特別是參考報表約四成的間接光，不能用本模式的直接照度補造。

## 來源與驗證

- [Autodesk IES 文件](https://help.autodesk.com/cloudhelp/2015/ENU/AutoCAD-Core/files/GUID-45CAAF1C-7C9D-49A7-B18D-00CA5E2ED380.htm)
- [AGi32 EULUMDAT 欄位](https://docs.agi32.com/PhotometricToolbox/Content/Open_Tool/eulumdat_file_format.htm)
- [DIAL EULUMDAT 格式／對稱](https://evo.support-en.dial.de/support/solutions/articles/9000074164-description-of-the-eulumdat-format)
- [DIAL 絕對光度 LDT 定義](https://dialux4.support-en.dial.de/support/solutions/articles/9000073286-absolute-photometric-luminaire-data-in-eulumdat-format)

驗收包含常數100 cd、正下方2m＝25lx、距離倍增照度四分之一、斜入射餘弦、非對稱 C0/C90 及 yaw、兩燈加總、倍率／維護只乘一次、半球缺失、矩形立體角積分收斂、來源追溯、HTML逸出、雙語與存檔護鎖。合成資料不是原廠驗證；[合成 IES](examples/direct-lighting/synthetic-constant-1000cd.ies)只供軟體測試，不能用於工程選型。原生 GUI／瀏覽器列印仍需在有顯示環境的候選版驗收。

C 平面方向另以 [Radiance source.cal 修正後的座標實作](https://www.radiance-online.org/cgi-bin/viewcvs.cgi/ray/src/cv/source.cal?revision=2.12&view=markup)、[Viso IES/LDT 軸向圖](https://data.visosystems.com/content/manuals/guidelines_dimensions%20of%20lighting%20fixtures.pdf)及[AGi32 aiming 定義](https://docs.agi32.com/PhotometricToolbox/Content/Aiming_Parameters.htm)核對。IES 與 LDT 保留各自檔案 C0/C90，不猜測燈殼長軸，也不對非對稱配光做鏡射。JSON 明列座標慣例。

### 1995 年版 90–270 匯入修正

此角域在 LM-63-1995 合法，LM-63-2002 第 4 節才將它移除。舊版匯入器把兩版本一律限制為 C0 起始，會誤拒絕有效的 1995 檔案。修正按照 C90–C270 平面對稱：C0 取 C180、C45 取 C135、C315 取 C225；C90 與 C270 各自保留，不強制相等。[Radiance 的 IES 匯入原始碼](https://www.radiance-online.org/cgi-bin/viewcvs.cgi/ray/src/cv/ies2rad.c?revision=2.38&view=markup)亦明確處理此對稱面。

不等距角度表未量測 C180 時，C0 接縫使用相同的線性內插，不補造量測。JSON 追溯資料記錄原始 C 角度表及對稱面；原始 IES 檔案和 SHA-256 不變。回歸使用合成資料，涵蓋不相等的 C90/C270、37×37 角度矩陣、不等距角度、yaw、重複匯入、取消和匯出，不隨程式公開原廠附件。

English: LM-63-1995 Type C files may use the 90–270 degree horizontal domain, which LM-63-2002 removed. The importer now reflects only the missing half about C90–C270 while preserving file axes and measured rows. C0 maps to C180, C45 to C135 and C315 to C225. A missing C180 sample is linearly interpolated at the periodic seam. Files declaring 2002 with this legacy domain remain rejected. Original bytes and hashes are unchanged; source angles and symmetry are retained in JSON metadata. Synthetic regression data covers asymmetric endpoints, nonuniform grids, scaling, rotation and the import/export workflow.
