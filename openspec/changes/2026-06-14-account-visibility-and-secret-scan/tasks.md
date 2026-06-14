## 1. 機密掃描規則（R-21）

- [ ] 1.1 新增 `policy_check/rules/r21_secret_scan.py`：對 tracked 文字檔做 denylist 掃描（雇主標記、個人絕對路徑、憑證模式）
- [ ] 1.2 嚴格度 tier 感知：從 `.paul-project.yml` 讀 `tier`；`shareable` 命中 FAIL、`work`/`personal` WARN 或 skip
- [ ] 1.3 實作自我參照豁免（自身規則檔、fixture 目錄、文件豁免清單），使規則不誤報自己
- [ ] 1.4 新增 `tests/test_rule_r21_secret_scan.py` + fixtures（乾淨 repo 通過；shareable repo 含 `brcm` FAIL；work repo 含標記 WARN；自身檔案豁免）
- [ ] 1.5 註冊規則並確認出現在 `tests/test_rules_presence.py`

## 2. `.paul-project.yml` 的 tier 欄位

- [ ] 2.1 擴充 `.paul-project.yml` schema（R-08），加 optional `tier: shareable | work | personal`
- [ ] 2.2 加 schema fixtures/tests（合法與非法 `tier` 值）
- [ ] 2.3 在 conventions 自身 `.paul-project.yml` 設定 `tier`（dogfood：`shareable`）

## 3. 版號與傳播

- [ ] 3.1 `VERSION` 1.0.2 → 1.0.3，更新 CHANGELOG `[Unreleased]`
- [ ] 3.2 更新 caller workflow `policy_version` 為 `1.0.3`（R-20）與 agent 慣例檔版號（R-13/R-14）
- [ ] 3.3 跑 `python3 -m policy_check --repo .` 確認全綠（含新 R-21 自查）

## 4. 帳號 ops — 機密清掃（S1）

- [ ] 4.1 `serialwrap`：`profiles/brcm.env` → `profiles/brcm.env.example`，值改占位符
- [ ] 4.2 `serialwrap`：`profiles/OPI.env` → `profiles/OPI.env.example`，值改占位符
- [ ] 4.3 `serialwrap`：`.gitignore` 加 `profiles/*.env`；確認 `git ls-files | grep -E '\.env$'` 為空

## 5. 帳號 ops — 可見性遷移（S2）+ 同步（S3）

- [ ] 5.1 前置：`paulc-arc` gh token 補 `delete_repo` scope（`gh auth refresh -h github.com -s delete_repo`）
- [ ] 5.2 將 `testpilot`、`logsensing`、`dts-build`、`IntelliDbgKit` 轉 private（依 runbook）
- [ ] 5.3 刪除脫鉤的 public fork `paulc-arc/testpilot`、`paulc-arc/dts-build`（先確認下游無未同步的 local 工作）
- [ ] 5.4 每個 work canonical 加 `paulc-arc` 為 read collaborator；下游副本加 `SYNC.md` + `upstream` remote

## 6. 帳號 ops — archive（S4）+ 分類落地（S6）

- [ ] 6.1 archive `openclaw-obsidian-deploy` 與 `custom-claw-tools`
- [ ] 6.2 為每個納管 repo 在 `.paul-project.yml` 寫入符合分類的 `tier`
