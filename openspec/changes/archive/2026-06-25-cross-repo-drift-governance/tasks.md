## 1. TDD — drift 純邏輯（RED first）

- [x] 1.1 寫 `tests/test_drift.py`：`parse_version` 的 `-fix.N` 完整排序（無尾註 < `-fix.1` < `-fix.2`），先 RED
- [x] 1.2 加測 `classify`：落後但自洽（`1.0.5` vs `1.0.7` → `behind`）、相等 → `current`、較新 → `ahead`、`None` → `unmanaged`
- [x] 1.3 加測 `parse_policy_version`（抽 `policy_version`／缺欄回 `None`）與 `format_report` 表格輸出
- [x] 1.4 確認以上測試因 `policy_check/drift.py` 不存在而 RED（正確失敗原因）

## 2. drift 工具實作

- [x] 2.1 建 `policy_check/drift.py` 純邏輯：`parse_policy_version` / `parse_version` / `classify` / `format_report`，使第 1 組測試轉綠
- [x] 2.2 加 I/O 邊緣：`local_policy_version` / `canonical_version_live`（最高版本 tag，非 releases/latest）/ `list_managed_repos` / `fetch_policy_version`（gh CLI，認兩種設定檔名）
- [x] 2.3 加 CLI：`report` 子命令（`--org` / `--json`，永遠 exit 0）
- [x] 2.4 加 CLI：`check` 子命令（`--against`，`behind`/`invalid` → exit≠0，其餘 exit 0）
- [x] 2.5 `python3 -m policy_check.drift report` 與 `... check` 手動 smoke（read-only，不改任何下游）

## 3. org ruleset runbook

- [x] 3.1 寫 `docs/org-ruleset-runbook.md`：目的、前置（`admin:org`）、Step 1 建 ruleset（`Policy Check` + `Policy Freshness` 兩條 required check、require PR、禁直推 main、`gh api` payload 範例）
- [x] 3.2 Step 2：org-level required workflow / default setup 推 `policy-freshness.yml`（附範例 workflow YAML，checkout canonical 最新版跑 `drift check`）
- [x] 3.3 Step 3：下游落後實驗驗證步驟；並說明與 R-15/R-23 dual-pin 並存、Non-goals（GitLab 見 #20）

## 4. 升版傳播 SOP

- [x] 4.1 `README.md`「Doc-alignment governance」新增「跨 repo 升版傳播（機制層）」子段，串起 freshness gate → drift report → 下游自助升版
- [x] 4.2 `RELEASES.md`：把手動傳播句擴成明確 SOP 區塊（6 步：查表 → 改 policy_version → re-pin SHA + `# vX.Y.Z` → 更新 canonical agent 檔 → 測試/policy_check 全綠 → 開 zh-tw PR）
- [x] 4.3 `README.md` 規則/工具總覽補上 drift 工具（report/check）

## 5. 文件對齊與收尾

- [x] 5.1 `CHANGELOG.md [Unreleased]` 補本批 entry（drift 工具 + runbook + SOP）
- [x] 5.2 `docs/MOC.md` 把本案 openspec change + plan + `docs/org-ruleset-runbook.md` 連進 `moc.map`（避免 R-24 orphan WARN）
- [x] 5.3 `python3 -m pytest -q` 全綠
- [x] 5.4 `python3 -m policy_check --repo .` 無 failure
- [x] 5.5 requesting-code-review；依回饋修正並 re-review
