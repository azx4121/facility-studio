# 第三方元件授權範圍

## 5.7.3 現行封裝契約 / Current packaging contract

5.7.3 原生 build 由 integration/build.py 收集實際環境與 Python 授權，加入包內 `第三方授權.txt`；最終包仍需逐項核對，不把開發依賴清單等同出貨清單。PsychroLib、python-hvac、fluids、CoolProp、Pint 已列入目前整合建置，不沿用下方舊版「僅獨立比較、未交付」敘述。

python-hvac 使用 build-local loading adapter：只移除 eager initializer 對未使用 Water／Ice wrapper 的匯入；不修改工程方程式或已安裝環境。`iapws`、`hvac.fluids.water`、`hvac.fluids.ice` 排除於本次執行檔，manifest 保留上游 commit、原始／調整後 initializer hash 及排除項。開發 lock 中有 iapws 不表示成品包含它。

The 5.7.3 builder collects runtime/Python notices into the bundled `第三方授權.txt`; inspect final artifacts rather than treating all development dependencies as shipped. The build-local python-hvac loading adapter excludes unused iapws-backed Water/Ice wrappers without changing engineering equations or the installed environment. Its provenance and initializer hashes are recorded in the manifest. Historical statements below apply only to their original releases, not current runtime inclusion.

## 歷史授權說明 / Historical release notes

根目錄的目前 `LICENSE`（PolyForm Noncommercial 加公司內部使用附加許可） 適用於 Facility Studio 專案自身的程式與文件，不替第三方執行環境、套件、建置工具或工程規範變更授權。
原有作者標示 `DESIGNED BY ANDY HUANG ©` 保留。

macOS 封裝保留 Python Framework 與各套件隨附的授權資料；Windows win.1 離線包將 CPython、Tk、Matplotlib、NumPy、Pillow 等相依元件事先封裝，並保留其授權文件於 `THIRD_PARTY_LICENSES.txt`。舊 Windows 線上安裝器的取得方式仍可依歷史版本重現。
第三方元件的授權與版權以實際取得版本所附文件為準。重新發布安裝包時，應一併保留相應授權文件，不能以本專案的限制性授權文件取代。

本次測試額外使用 PsychroLib 2.5.0 作獨立數值比較；它不是應用程式的執行需求，也未複製到專案中。其授權及公式來源見 [PsychroLib](https://github.com/psychrometrics/psychrolib)。

工程參考表保留原有來源、版本與適用範圍；目前授權及歷史 MIT 授權均不表示這些參考值已通過任何工程法規的認證。
