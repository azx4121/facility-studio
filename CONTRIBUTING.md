# 參與維護 / Contributing

[繁中首頁](README.md) · [English home](README.en.md) · [開發與驗收 / Development](docs/development.md)

## 回報問題 / Report a problem

先搜尋 [Issues](https://github.com/azx4121/facility-studio/issues)，再提供版本、Release／附件、OS／CPU、最小重現步驟、輸入及單位、預期與實際結果。使用合成或可公開的資料；移除業主名稱、個人路徑與機密。計算問題應列出採用公式與控制範圍。

Search existing issues first. Include the exact version/package, OS/CPU, minimal steps, inputs with units, and expected/actual results. Use synthetic or public-safe data; remove client information and private paths. State the calculation basis and boundary.

## 修改文件 / Documentation changes

- 繁中與英文同步更新，保留原有授權與設計者標示。 / Keep Chinese and English aligned and retain licensing and attribution.
- 新示意圖明標「非介面截圖」；截圖附來源版本、平台與擷取證據，不重標舊圖。 / Label illustrations and preserve screenshot provenance.
- 不把來源測試、候選包、文件存在或歷史 PASS 當作原生成品驗收。 / Distinguish source checks, candidates, documentation and historical passes from native package acceptance.
- 由倉庫根目錄執行： / Run from the repository root:

```sh
python tools/verify_documentation.py
```

此檢查核對現行文件的本機連結與 Markdown 錨點、圖解結構及身分；不連線檢查所有外部網址，也不驗證軟體成品。 / This checks local links, Markdown anchors, diagram structure and identity in current documentation. It does not validate all external URLs or application packages.

## 修改程式 / Code changes

依[現行開發與發布契約](docs/development.md)閱讀適用測試。Windows／macOS 來源分開執行，不覆蓋平台差異；變更後重跑受影響測試及必要 aggregate checks。說明哪些通過、失敗、跳過或未執行，不用 Linux 結果冒充原生驗收。

Follow the current development contract. Test Windows and macOS source trees separately, preserving platform differences. Run affected tests and required aggregate checks. Report passed, failed, skipped and unrun stages separately; Linux source checks are not native acceptance.

以 draft PR 提交可覆核的範圍，附測試命令、結果與限制。發布、tag、簽章及 binary 變更須遵循現行 gate，不能重寫歷史資產。 / Submit a scoped draft PR with commands, results and limitations. Follow release gates for tags, signing and binaries; preserve historical assets.

**DESIGNED BY ANDY HUANG ©**
