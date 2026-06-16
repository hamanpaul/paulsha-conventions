## 1. 機密掃描規則（R-21）

- [x] 1.1 新增 `policy_check/rules/r21_secret_scan.py`：對 tracked 文字檔做 denylist 掃描（雇主標記、個人絕對路徑、憑證模式）
- [x] 1.2 嚴格度 tier 感知：從 `.paul-project.yml` 讀 `tier`；`shareable` 命中 FAIL、`work`/`personal` WARN 或 skip
- [x] 1.3 實作自我參照豁免（自身規則檔、fixture 目錄、文件豁免清單），使規則不誤報自己
- [x] 1.4 新增 `tests/test_rule_r21_secret_scan.py` + fixtures（乾淨 repo 通過；shareable repo 含 `brcm` FAIL；work repo 含標記 WARN；自身檔案豁免）
- [x] 1.5 註冊規則並確認出現在 `tests/test_rules_presence.py`

## 2. `.paul-project.yml` 的 tier 欄位

- [x] 2.1 擴充 `.paul-project.yml` schema（R-08），加 optional `tier: shareable | work | personal`
- [x] 2.2 加 schema fixtures/tests（合法與非法 `tier` 值）
- [x] 2.3 在 conventions 自身 `.paul-project.yml` 設定 `tier`（dogfood：`shareable`）

## 3. 版號與傳播

- [x] 3.1 `VERSION` 1.0.2 → 1.0.3，更新 CHANGELOG `[Unreleased]`
- [x] 3.2 更新 caller workflow `policy_version` 為 `1.0.3`（R-20）與 agent 慣例檔版號（R-13/R-14）
- [x] 3.3 跑 `python3 -m policy_check --repo .` 確認全綠（含新 R-21 自查）

## 4. 帳號 ops — 機密清掃（S1）

- [x] 4.1 `serialwrap`：`profiles/brcm.env` → `profiles/brcm.env.example`，值改占位符
- [x] 4.2 `serialwrap`：`profiles/OPI.env` → `profiles/OPI.env.example`，值改占位符 —（N/A：repo 無 OPI.env）
- [x] 4.3 `serialwrap`：`.gitignore` 加 `profiles/*.env`；確認 `git ls-files | grep -E '\.env$'` 為空

## 5. 帳號 ops — 可見性遷移（S2）+ 同步（S3）

- [x] 5.1 前置：`paulc-arc` gh token 補 `delete_repo` scope（`gh auth refresh -h github.com -s delete_repo`） —（替代：fork 由 web 直接刪除，未授 scope）
- [x] 5.2 將 `testpilot`、`logsensing`、`dts-build`、`IntelliDbgKit` 轉 private（依 runbook）
- [x] 5.3 刪除脫鉤的 public fork `paulc-arc/testpilot`、`paulc-arc/dts-build`（先確認下游無未同步的 local 工作）
- [x] 5.4 每個 work canonical 加 `paulc-arc` 為 read collaborator；下游副本加 `SYNC.md` + `upstream` remote —（read collaborator 已加；下游副本 N/A：尚無）

## 6. 帳號 ops — archive（S4）+ 分類落地（S6）

- [x] 6.1 archive `openclaw-obsidian-deploy` 與 `custom-claw-tools`
- [x] 6.2 為每個納管 repo 在 `.paul-project.yml` 寫入符合分類的 `tier` —（conventions/testpilot/serialwrap 完成；logsensing/dts-build/IntelliDbgKit 依 route A 不導入）
