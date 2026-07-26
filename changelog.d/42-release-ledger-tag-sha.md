---
type: fix
issue: 42
---
修正 RELEASES release ledger 的 tag→commit SHA 對照，避免 `v1.0.5` 到 `v1.0.12` 仍參照 merge commit，並新增 release ledger 自我檢測測試。
