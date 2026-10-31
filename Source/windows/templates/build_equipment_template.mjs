import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const [specPath, outputDir] = process.argv.slice(2);
const spec = JSON.parse(await fs.readFile(specPath, "utf8"));
await fs.mkdir(outputDir, {recursive:true});
const wb = Workbook.create();
const guide = wb.worksheets.add("填寫說明");
const sheetMap = new Map(spec.systems.map(s => [s.name, wb.worksheets.add(s.name)]));
const font = "Noto Sans CJK TC";
const colName = i => { let s=""; for(i++;i>0;i=Math.floor((i-1)/26)) s=String.fromCharCode(65+(i-1)%26)+s; return s; };
const overview = [
 ["操作順序","在各系統分頁填設備，啟用設1，保留第5列欄名；回軟體右上「設備表匯入」開檔。"],
 ["範例列","第6列是示範，啟用為0。可改成自己的設備，或從第7列新增。"],
 ["每台與台數","功率／流量都填每台數據，台數另填。插座數只統計點位，不再乘功率。"],
 ["同時使用率","填0~100的瞬間同時需求係數。空白採100%。不能用每小時運轉比例替代安全系統的設計量。"],
 ["支路與主管","支路按單台額定負載；主管依同時需求初估，盤進線不低於已納入最大單台支路設計電流。另列全開需求。"],
 ["供應群組","填供應盤或共用主管，例如UP-01、CDA-01。不同群組分開定寸。"],
 ["電力","填每台電氣輸入kW、設備兩端電壓、1或3相、PF與台數。三相電壓填線間電壓。"],
 ["插座","填每台所需插座點位。未知插座負荷請先估接入kW，不能只靠插座數決定NFB。"],
 ["電力預設","PF空白採0.85，類型採一般設備，距離採30m。線表初估：XLPE、60°C端子、35°C、同管3根、壓降≤3%。"],
 ["PCW","填每台循環水量及流量單位；溫差預設5K。合計水量與熱量，未計泵揚程。"],
 ["CDA／N2","標準量需對應溫壓，預設25°C／101.325kPa(abs)。ALPM是所填管內溫壓的實際L/min。"],
 ["氣體壓力","CDA／N2填表壓，程式另加大氣壓。合計前會把各台標準量換到共同基準。"],
 ["EXHAUST","GEX、SEX、AEX、VEX、HEX各別統計。設備端靜壓只列最大已知要求，不能當風機總ESP。"],
 ["DI","每台製程用量可乘同時率；每台額外循環LPM持續納入，不乘同時率。避免重複填已包含的循環量。"],
 ["PV","流量可填標準量或ALPM；壓力填絕壓，支援Torr、kPa、mbar。模型限1~760Torr。"],
 ["PV抽速","所需抽速是在製程端的有效抽速；要選泵仍需泵曲線、氣體與真空管導通資料。"],
 ["空白與零","必填欄不可空白。可用0的欄位請明確填0。選填欄採預設時，匯入明細會列出採用值。"],
 ["新增與排序","預留100列。更多設備請在下方「欄位／填寫提示」之前插入列並複製輸入格式，最多10,000筆。按整列排序，設備編號不得重複。"],
 ["公式欄","右方灰色欄提供該列原單位初算。匯入程式從黃色輸入欄重新計算，不依賴Excel快取結果。"],
 ["資料格式","數值填數字，單位另選。輸入欄不接受公式；若來源是公式，請貼上值。保留工作表名稱。"],
 ["盤體設計邊界","可列NFB／線徑候選、分組kW／kVA／電流與點位；盤體尺寸、遮斷容量、相別平衡及接地需再補資料。"]
];
guide.showGridLines=false;
guide.getRange("A1:B28").format.font={name:font,size:10,color:"#18334D"};
guide.getRange("A1:A28").format.columnWidth=23;
guide.getRange("B1:B28").format.columnWidth=108;
guide.getRange("A2").values=[["設備需求表填寫說明"]];
guide.getRange("A2").format.font={name:font,size:14,bold:true,color:"#18334D"};
guide.getRange("A2:B2").format.rowHeight=30;
guide.getRange("A4:B4").values=[["項目","填寫方式與計算意義"]];
guide.getRange("A4:B4").format={fill:"#203F5A",font:{name:font,size:10,bold:true,color:"#FFFFFF"},rowHeight:26};
guide.getRange("A5:B25").values=overview;
guide.getRange("A5:B25").format.wrapText=true;
guide.getRange("A5:B25").format.verticalAlignment="center";
guide.getRange("A5:B25").format.rowHeight=40;
guide.getRange("A5:A25").format.font.bold=true;

const checks=[];
for(const system of spec.systems) {
 const sh=sheetMap.get(system.name), columns=system.columns, n=columns.length;
 const last=colName(n+1);
 sh.showGridLines=false;
 sh.getRange("A1:"+last+"105").format.font={name:font,size:10,color:"#18334D"};
 sh.getRange("A1:"+last+"105").format.rowHeight=24;
 sh.getRange("A2").values=[[system.name+"設備表"]];
 sh.getRange("A2").format.font={name:font,size:14,bold:true,color:"#18334D"};
 sh.getRange("A3").values=[["黃色填實際設備；灰色為原單位初算。範例啟用0，納入時改1。欄位詳細說明見下方。"]];
 const derived=system.name==="電力"?["計算_全開kW","計算_同時kW"]:["計算_全開量(原單位)","計算_同時量(原單位)"];
 sh.getRange("A5:"+last+"5").values=[[...columns.map(c=>c.label),...derived]];
 sh.getRange("A5:"+last+"5").format={fill:"#203F5A",font:{name:font,size:10,bold:true,color:"#FFFFFF"},wrapText:true,
   horizontalAlignment:"center",verticalAlignment:"center",rowHeight:42};
 for(let i=0;i<n+2;i++){
  const letter=colName(i),c=columns[i];
  sh.getRange(letter+"1:"+letter+"105").format.columnWidth=c?.key==="name"?24:c?.key==="notes"?28:c?.key==="id"||c?.key==="group"?19:i>=n?24:17;
  if(i<n){
   const input=sh.getRange(letter+"6:"+letter+"105");
   input.format.fill="#FFF8E6";
   input.format.horizontalAlignment=c.kind==="text"||c.kind==="choice"?"left":"right";
   if(c.kind==="number")input.setNumberFormat("#,##0.000");
   if(c.kind==="integer")input.setNumberFormat("#,##0");
   if(c.options.length)input.dataValidation={rule:{type:"list",values:c.options}};
   else if(c.kind==="integer")input.dataValidation={rule:{type:"whole",operator:"between",formula1:c.low,formula2:c.high}};
   if(c.required){
    const missing=c.key==="enabled"?'AND($B6<>"",NOT(ISNUMBER($A6)))':
      'AND($A6=1,'+((c.kind==="number"||c.kind==="integer")?'NOT(ISNUMBER('+letter+'6))':letter+'6=""')+')';
    input.conditionalFormats.addCustom(missing,{fill:"#FFE4DF",font:{color:"#AF2D2D"}});
   }
  }else{
   sh.getRange(letter+"6:"+letter+"105").format.fill="#EDF1F5";
   sh.getRange(letter+"6:"+letter+"105").setNumberFormat("#,##0.000");
  }
 }
 sh.getRange("A6:"+colName(n-1)+"6").values=[[...columns.map(c=>system.example[c.key]??null)]];
 const idx=Object.fromEntries(columns.map((c,i)=>[c.key,colName(i)]));
 const valueCol=idx.power||idx.flow;
 const connected='=IF('+idx.id+'6="","",IF('+idx.enabled+'6<>1,0,IF(ISNUMBER('+valueCol+'6),'+valueCol+'6*IF(ISNUMBER('+idx.quantity+'6),'+idx.quantity+'6,1),"待填需求")))';
 const demand='=IF('+idx.id+'6="","",IF(ISNUMBER('+colName(n)+'6),'+colName(n)+'6*IF(ISNUMBER('+idx.usage+'6),'+idx.usage+'6,100)/100,"待填需求"))';
 sh.getRange(colName(n)+"6").formulas=[[connected]];
 sh.getRange(colName(n+1)+"6").formulas=[[demand]];
 sh.getRange(colName(n)+"6:"+colName(n)+"105").fillDown();
 sh.getRange(colName(n+1)+"6:"+colName(n+1)+"105").fillDown();
 sh.freezePanes.freezeRows(5);
 sh.freezePanes.freezeColumns(3);
 const helpRows=columns.filter(c=>c.help).map(c=>[c.label,c.help]);
 sh.getRange("A109:B109").values=[["欄位","填寫提示"]];
 sh.getRange("A109:B109").format.font={name:font,size:10,bold:true,color:"#18334D"};
 for(let i=0;i<helpRows.length;i++){ sh.getRange("A"+(110+i)+":B"+(110+i)).values=[helpRows[i]]; sh.getRange("A"+(110+i)+":B"+(110+i)).format.font={name:font,size:10,color:"#18334D"}; }
 const rawCSV=[columns.map(c=>c.label),columns.map(c=>system.example[c.key]??"")];
 const escapeCSV=x=>'"'+String(x).replaceAll('"','""')+'"';
 await fs.mkdir(path.join(outputDir,"equipment_csv"),{recursive:true});
 await fs.writeFile(path.join(outputDir,"equipment_csv",system.name+".csv"),"\ufeff"+rawCSV.map(r=>r.map(escapeCSV).join(",")).join("\r\n")+"\r\n","utf8");
 sh.getRange(idx.enabled+"6").values=[[1]];
 sh.getRange(idx.quantity+"6").values=[[2]];
 sh.getRange(idx.usage+"6").values=[[50]];
 wb.recalculate();
 const cells=sh.getRange(colName(n)+"6:"+last+"6").values[0];
 const raw=system.example[columns.find(c=>c.key==="power"||c.key==="flow").key];
 if(Math.abs(cells[0]-raw*2)>1e-8||Math.abs(cells[1]-raw)>1e-8)throw new Error("live formula check: "+system.name);
 checks.push({name:system.name+"_formula_recalculation",passed:true,connected:cells[0],demand:cells[1]});
 sh.getRange(idx.enabled+"6").values=[[0]];
 sh.getRange(idx.quantity+"6").values=[[1]];
 sh.getRange(idx.usage+"6").values=[[100]];
}
wb.recalculate();
const scan=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",options:{useRegex:true,maxResults:30},maxChars:2500});
await fs.writeFile(path.join(outputDir,"template_formula_scan.ndjson"),scan.ndjson);
const inspect=await wb.inspect({kind:"table",range:"電力!A5:Q8",include:"values,formulas",tableMaxRows:4,tableMaxCols:17,maxChars:5000});
await fs.writeFile(path.join(outputDir,"template_inspect.ndjson"),inspect.ndjson);
for(const [name,sh] of [["填寫說明",guide],...sheetMap]) {
 const cols=name==="填寫說明"?"B":colName(spec.systems.find(s=>s.name===name).columns.length+1);
 const preview=await wb.render({sheetName:name,range:"A1:"+cols+(name==="填寫說明"?"25":"10"),scale:1,format:"png"});
 await fs.writeFile(path.join(outputDir,"Template_"+name+".png"),new Uint8Array(await preview.arrayBuffer()));
}
await fs.writeFile(path.join(outputDir,"Template_Checks.json"),JSON.stringify({checks,formula_error_scan:scan.ndjson,native_excel_execution_tested:false},null,2));
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(outputDir,"Equipment_Template.xlsx"));
console.log(JSON.stringify({sheets:8,recalculation_checks:checks.length,output:path.join(outputDir,"Equipment_Template.xlsx")}));
