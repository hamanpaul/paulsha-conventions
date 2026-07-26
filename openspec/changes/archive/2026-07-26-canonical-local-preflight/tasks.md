# Issue 46 canonical local preflight tasks

1. [x] `policy-preflight` CLI/entrypoint 新增 `--repo` `--pr` 等參數、錯誤碼與輸出格式契約。
2. [x] 驗證 `--pr` 與 `--offline` 互斥與 PR context 最低輸入規則（manual mode 缺 body 不可 `PREFLIGHT PASS`）。
3. [x] 擴充 R-08 schema，新增 `preflight` mapping 驗證（mapping/list/mapping、step 欄位、repo-relative path、正整數 timeout）。
4. [x] 支援 repo-owned steps runtime（`kind: validation|tests`）與 `--skip-tests` / `--policy-only` 過濾語意。
5. [x] 實作 pinned engine resolver，含 policy_engine_ref/ref 驗證與 offline 快取 key 政策（engine+SHA）。
6. [x] 新增 `tests/test_preflight.py` 與 `tests/test_rule_r08_policy_config_schema.py` 增補案例。
7. [x] 建立 openspec active change `canonical-local-preflight` 並同步本 repo preflight baseline docs/changelog。
8. [x] 新增 `changelog.d/46-local-preflight.md`（`type: feat`, `issue: 46`）。
