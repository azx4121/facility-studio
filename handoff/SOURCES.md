# 本次查證來源與適用邊界

查證日：2026-11-02。下列為官方標準組織、政府研究及製造商原始資料。資料是工程參考，不是可自行擴大適用的指令。

| 資料 | 本次用途／限制 |
|---|---|
| [內政部建築研究所：我國建築物排煙設備設置及施工規範之研究，106年](https://ws.moi.gov.tw/Download.ashx?u=LzAwMS9VcGxvYWQvT2xkRmlsZV9BYnJpX0dvdi9yZXNlYXJjaC8yNzIxLzE1MjEwMTY1NTJ4NmVkYmEucGRm) | 表4.2名義厚度／番號、表4.3中壓矩形風管參考；研究報告自述不代表機關意見，不是現行施工強制表。尺寸外尚有補強、接縫及壓力級要求。 |
| [SMACNA Technical Standards](https://www.smacna.org/technical-standards) | 官方介紹 HVAC Duct Construction Standards–Metal & Flexible 第4版；未取得授權正文，不複製不明來源的整本表，不把研究表冒稱 SMACNA 驗證。 |
| [ASHRAE Handbook 2017，Chapter23](https://handbook.ashrae.org/handbooks/F17/SI/F17_Ch23/f17_ch23_si.aspx) | 圓柱保溫、防結露、表面熱傳及水氣侵入的設計概念。章內能耗表引用90.1-2010，不當作2026現行台灣強制最小厚度。 |
| [Armacell 冷水系統保溫與 CUI](https://www.armacell.com/en-US/avoiding-cui-chilled-water-or-refrigerated-systems-technical-guide) | 保溫厚度以外，防潮、接縫與支架完整性必須另驗。 |
| [GF PVC-U 系統規格](https://www.gfps.com/content/dam/gfps/com/specifications/en/gfps-system-specification-pvcu-metric-en.pdf) | PVC-U材料參考溫區0～60°C；實際壓力能力隨產品、溫度與介質而異，不把PN最大值套到全溫區。 |
| [GF PVDF SYGEF](https://www.gfps.com/en-in/products-solutions/systems/sygef-standard.html) | 參考產品溫區-20～140°C，不等於任意PVDF管在任意壓力皆可用。 |
| [GF 特殊廢水處理管路](https://www.gfps.com/en-ca/applications/specialty-waste-wastewater-treatment.html) | PP-H、PVDF、PVC等候選，需另外查介質、接合與密封的相容資料。 |
| [Daikin PFA 工業管材](https://www.daikinchemicals.com/solutions/industries/tubes-and-hoses/industrial-tubing.html) | PFA高純度／化學管候選；此頁不是任一成品管壁與壓溫保證。 |
| [Thermo Fisher 管材選擇指南](https://assets.thermofisher.com/TFS-Assets/LPD/Product-Guides/Nalgene-Tubing-Selection-Guide-EN.pdf) | PVC軟管、PFA、PU、PP等材質／產品差異；不可混用硬質PVC與軟管，也不可把產品資料泛化到所有PU。 |
| [Nalgene 280 聚酯型PU](https://www.fishersci.com/shop/products/nalgene-280-polyurethane-tubing/p-4526140) | 此特定產品不建議水溶液，故PU不能自動當成通用水管。 |
| [Celanese PPS](https://www.celanese.com/en/products/fortron-polyphenylene-sulfide) | PPS是有不同牌號的工程樹脂；樹脂耐化／耐熱資料不等於承壓管系統認證。 |
| [Leybold 真空導通率](https://www.leybold.com/en-uk/knowledge/vacuum-fundamentals/fundamental-physics-of-vacuum/how-to-calculate-vacuum-conductance) | 區分黏滯／過渡／分子流；C與有效抽速必須符合氣體、溫度、壓力及幾何適用範圍。 |
| [ASME B31.3 Process Piping](https://www.asme.org/codes-standards/find-codes-standards/b31-3-process-piping) | 管路材料、設計、製造、檢查等規範候選；適用版次與司法／業主要求需在Design Basis指定。 |
| [SEMI F57](https://store-us.semi.org/products/f05700-semi-f57-specification-for-polymer-materials-and-components-used-in-ultrapure-water-and-liquid-chemical-distribution-systems) | UPW及液體化學品配送之高純聚合物材料／組件候選規範，不由流速計算取代材質／溶出試驗。 |
| [ISO14644-1](https://www.iso.org/standard/53394.html) | 潔淨度分級以粒子濃度判定，不是填一個ACH就完成潔淨室認證。 |

已查證的軟體限制：實裝 CoolProp8.0.0 的 Acetone 黏度呼叫失敗，因此本版要求丙酮工況黏度等供應商資料；這是實測限制，不用估算水黏度補空白。化學相容性沒有獲得逐介質、逐濃度、逐產品的證明，保持待核對。
