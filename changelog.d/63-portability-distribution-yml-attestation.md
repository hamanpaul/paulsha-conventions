---
type: fix
scope: portability
issue: 63
---
`verify_installed_wheel_payload` 的 `policy_check/data/distribution.yml` 檢查改以 manifest（`verification.canonical_distribution_identity`）為完整性錨，不再比對 wheel RECORD 的 size/sha256；修正安裝期身分寫入（`_write_distribution_identity`）與安裝後 attestation 之間必然衝突、導致 install 永遠失敗的問題。`manager.py` 的寫入端改為呼叫同一個 `verification.py` 函式，寫入與驗證不再有漂移風險。
