# doc-drift-action Specification

## Purpose
TBD - created by archiving change doc-drift-action. Update Purpose after archive.
## Requirements
### Requirement: 零設定且可被外部 repo uses:
doc-drift Action MUST 為可被任意 repo `uses:` 的獨立 composite action，MUST NOT 要求目標 repo 存在 policy 設定檔（`.paul-project.yml`／profile/version 機制）。Action MUST 自行確保執行環境具備 universal-ctags（自安裝或文件化前置步驟）。

#### Scenario: 外部 repo 無 policy 設定檔仍可執行
- **WHEN** 一個未採用 paulsha-conventions 的外部 repo 以 `uses:` 引用本 Action
- **THEN** Action 在無 `.paul-project.yml` 下完成 doc-drift 分析

### Requirement: doc-drift 與 moc-alignment 兩 mode
Action MUST 提供兩種 mode，由輸入選擇：**doc-drift**（refs + paths + symbols）與 **moc-alignment**（refs + paths + coverage）。moc-alignment mode 的受治理前綴 MUST 可由輸入設定（預設沿用既有治理前綴）。

#### Scenario: 選擇 doc-drift mode
- **WHEN** 以 doc-drift mode 執行，某 doc 引用本次刪除的 symbol
- **THEN** Action 依核心 symbol-drift 語義回報結果

#### Scenario: 選擇 moc-alignment mode 並自訂前綴
- **WHEN** 以 moc-alignment mode 執行並設定自訂受治理前綴
- **THEN** Action 依該前綴判定 map 懸空與孤兒

### Requirement: Action 自理 base/head 供給並在淺層 checkout 下不前置失敗
Action MUST 從 GitHub event 取得 PR base/head 的精確 SHA 並委由核心供給契約確保物件存在，MUST NOT 仰賴 caller 的 `actions/checkout` 深度。當分析無法進行（物件取不到）時 MUST fail-fast 並輸出可行動訊息。

#### Scenario: 預設淺層 checkout 下不在分析前 fatal
- **WHEN** caller 使用預設 `fetch-depth: 1` 的 checkout
- **THEN** Action 自行取得 base 物件後完成分析，不因缺物件在分析前 fatal

### Requirement: 結果輸出與 exit code
Action MUST 在存在 FAIL 級懸空時以非零 exit code 結束（可擋 merge），WARN 為 advisory（不擋），並輸出可定位的清單（檔案 → 引用）。

#### Scenario: 有本次新破壞時擋下
- **WHEN** 分析發現本次變更造成的 FAIL 級懸空引用
- **THEN** Action 以非零 exit code 結束並列出該引用

#### Scenario: 僅有陳年 advisory 時通過
- **WHEN** 分析僅發現陳年 WARN 級引用
- **THEN** Action 以零 exit code 結束並列出 advisory

### Requirement: lychee 邊界
Action MUST NOT 檢查外部 URL 活性／HTTP／anchor；此類檢查交由 lychee。README MUST 說明與 lychee 的互補組合。

#### Scenario: 不檢外部連結
- **WHEN** 某 doc 含一個指向外部網站的失效 URL
- **THEN** Action 不因該外部 URL 回報（屬 lychee 範圍）

### Requirement: in-repo demo 與 self-test
本案 MUST 提供 in-repo demo fixture（一個通過案、一個 known-bad 失敗案）與 self-test CI job，且 self-test MUST 涵蓋淺層 checkout（`fetch-depth: 1`）情境以證明 Action 不前置失敗。

#### Scenario: demo green/red 斷言
- **WHEN** 對 demo 的通過案與 known-bad 案各跑一次 Action
- **THEN** 通過案得零 exit、known-bad 案得非零 exit

