---
type: fix
issue: 61
---
`policy_check` 在 CLI 啟動時新增引擎版本 gate：比對執行中引擎版本（優先讀已安裝套件的 metadata，source checkout 則 fallback 讀引擎自身的 `VERSION`）與 repo 宣告的 `policy_version`，不符時以 configuration error 等級 fail-loud（訊息含雙方版本與建議重裝指令），並在報告表頭標示執行中引擎版本；帶 `release:*` label 的 release PR 視窗降為 WARN，無法取得引擎版本時 fail-closed 不靜默跳過。
