## 1. Config schema 與載入（R-08 + config.load）

- [ ] 1.1 撰寫 R-08 測試（fixtures）：`agent_files.mode` 非法→FAIL、合法→PASS；`conventions_engine.repo` 非 str→FAIL、合法→PASS
- [ ] 1.2 擴充 `policy_check/rules/r08_policy_config_schema.py`：驗 `agent_files`（mapping、`mode` ∈ {`symlink`,`copy`}）與 `conventions_engine`（mapping、`repo` 為 str）
- [ ] 1.3 `policy_check/config.py`：`load()` 對 `agent_files.mode` 預設 `copy`（未設時行為不變）；補 `tests/test_config.py`
- [ ] 1.4 R-08 與 config 測試全綠

## 2. R-14 hardened（config-gated）

- [ ] 2.1 撰寫 R-14 測試（fixtures，含實際 symlink）：`copy` 正例＋版本 drift 負例；`symlink` 正例＋三負例（鏡像為複本、symlink 錯誤目標、canonical 為 symlink）
- [ ] 2.2 改 `policy_check/rules/r14_agent_files_version.py`：讀 `agent_files.mode`（經 config）；`symlink` 檢查拓撲（`is_symlink()`/`resolve()` == canonical `CLAUDE.md`），`copy` 維持原版本比對
- [ ] 2.3 確認缺檔／斷鏈仍交 R-13；R-14 維持 `exempt_label = None`
- [ ] 2.4 R-14 測試全綠

## 3. R-23 engine pin attestation（新 rule）

- [ ] 3.1 撰寫 R-23 測試（fixtures）：tag 對齊/不齊、SHA+`# vX.Y.Z` 對齊/不齊、純 SHA→WARN、`./` 在地→NA、`conventions_engine` 未設→NA、`policy-exempt:engine-pin`→SKIP
- [ ] 3.2 新增 `policy_check/rules/r23_engine_pin_attestation.py`：掃 `.github/workflows/*.yml` 的 `uses:`→`conventions_engine.repo`；取 tag/SHA 尾註版本；比對 `policy_version`；WARN/NA/SKIP 邏輯；`exempt_label = "policy-exempt:engine-pin"`
- [ ] 3.3 確認 registry 依 `rNN_` 命名自動載入 R-23；`tests/test_rules_presence.py` 與 action/integration 測試補 R-23
- [ ] 3.4 R-23 測試全綠

## 4. 套用 symlink 拓撲與設定（本 repo）

- [ ] 4.1 `.paul-project.yml` 新增 `agent_files.mode: symlink`，並加 `conventions_engine`（本 repo 以 `./` 在地引用引擎 → R-23 NA，可不設 `repo` 或附註）
- [ ] 4.2 `AGENTS.md`/`GEMINI.md` → `CLAUDE.md`、`.github/copilot-instructions.md` → `../CLAUDE.md` 改為 git-tracked symlink（mode 120000）
- [ ] 4.3 本地 dogfood：`python3 -m policy_check --repo .` → R-13 PASS、R-14（symlink）PASS、R-23 NA、其餘無 failure

## 5. 慣例檔文字、白名單、文件、CHANGELOG

- [ ] 5.1 `CLAUDE.md`：header 註記、release checklist「四份」用語、禁止段「同步其他三份」改述 symlink 單一真檔模型；Exemption 白名單新增 `policy-exempt:engine-pin`；rule 目錄/checklist 補 R-23
- [ ] 5.2 `README.md` / `docs/**`：四檔模型、R-14 新語意、R-23 新規則、跨平台 symlink 退化註記（R-18/R-22）
- [ ] 5.3 `CHANGELOG.md [Unreleased]` 補本批 entry
- [ ] 5.4 確認 R-22 對本批 doc 引用無新懸空

## 6. 驗證與 release 準備

- [ ] 6.1 `python3 -m pytest -q` 全綠
- [ ] 6.2 `python3 -m policy_check --repo .` 無 failure（含 self-dogfood R-16／語言）
- [ ] 6.3 PR template checklist 全勾；PR body zh-tw；（如對應 issue）用 closing-keyword
- [ ] 6.4 merge 當下 release bump `1.0.5 → 1.0.6`（`VERSION`/`policy_version`/`CLAUDE.md` `managed-by`/workflow `policy_version`/tag/`RELEASES.md`）— 列為 merge 待辦
