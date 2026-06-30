# Changelog

本專案所有重大變更都會記錄在此檔案。

格式基於 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-TW/1.1.0/)，
本專案遵循 hamanpaul project policy v1.0.4。

## [Unreleased]

### Added
- **#23 跨 repo policy 漂移治理**：新增 `policy_check/drift.py`（ops 工具，非 R-xx 規則）——`report`（唯讀列出 `hamanpaul/*` 各 repo `policy_version` 對 live canonical 的 `current`/`behind`/`ahead`/`unmanaged`，永遠 exit 0）與 `check`（比當前 repo vs canonical 最高 tag，`behind` → exit≠0，供 org `Policy Freshness` required workflow 當 gate）；版本比較含 `-fix.N` 完整排序。新增 `docs/org-ruleset-runbook.md`（org admin 套用 ruleset + required workflow 步驟），README 新增「跨 repo 升版傳播（機制層）」子段、`RELEASES.md` 新增升版傳播 SOP。engine 不主動改下游。
- **#26 文件規則補強（doc_paths / R-25 doc_coverage / R-26 generated_facts）**：
  - 新增 top-level `doc_paths`（預設 `README.md` + `docs/**`）作為 `R-18` / `R-22` 共用的 canonical doc scope；R-08 驗證其為 `list[str]`。`R-18` 改以 `doc_paths` 判斷 code change 是否伴隨 docs touch；`R-22` 改由 `doc_paths` 取候選文件，仍保留 `openspec/**`・`docs/superpowers/**`・fixtures 內建排除。
  - **新增 R-25（doc coverage / omission gate，opt-in）**：宣告 `doc_coverage` 後，以四種 deterministic extractor（`modules`／`rpc_methods`／`env_vars`／`cli_tree`）抽出 public fact，要求其在 target docs 被精確 mention；`mode: changed`（預設）只查 `base...HEAD` 新增 fact、`mode: all` 查全部；缺 base diff context 降 WARN；target 超出 `doc_paths`／不存在／extractor 設定無效則 FAIL。mention 採區分大小寫的精確 token/phrase 比對（子字串不算）。
  - **新增 R-26（generated-fact marker sync，opt-in）**：宣告 `generated_facts` 後，以通用 `generated-fact` marker 協議比對 command 正規化 stdout 與 doc marker 區塊；marker 缺失／command 非 0／輸出不一致／設定不完整則 FAIL。與 `R-16` 的 `cli-help` marker 並存不互相覆蓋。
  - R-08 新增 `doc_coverage`（mapping／`mode ∈ {changed, all}`／`targets list[str]`／`sources list[mapping]`）與 `generated_facts`（`list[mapping]`）結構驗證；新增共用 helper `_doc_scope`／`_fact_extract`／`_marker_sync`（後者由 R-16 抽出，R-16 行為不變）。
- **R-08 接受 optional `tier` 欄位**：`.paul-project.yml` 新增可選欄位 `tier`，允許值為 `shareable` / `work` / `personal`；提供非法值（如 `public`）時 FAIL，並回報允許值清單。
- **新增 R-21（機密掃描）**：宣告 `tier: shareable` 的 repo 若含雇主標記（內部代號、裝置型號、build 主機等）、個人絕對路徑或憑證模式則 FAIL；`tier: work`/`personal` 視為 not-applicable；自身規則檔/fixtures 與 `.paul-project.yml` 的 `secret_scan.allow` 路徑豁免；豁免 label `policy-exempt:secret-scan`。同時 `.paul-project.yml` 新增 `secret_scan.allow` 設定。
- **新增 R-19（repo 有測試則 CI 必須執行）**：repo 根目錄存在 `tests/`（含 `test_*.py` / `*_test.py`）時，`.github/workflows/**` 必須有至少一個 workflow 實際執行測試（pytest / unittest / npm test / go test / cargo test 等），否則 FAIL；豁免 label `policy-exempt:ci-tests`。無測試套件的 repo 空轉通過。動機：多個 repo 擁有大量測試但 CI 僅跑 policy check，測試從未在 PR gate 上執行。
- **新增 R-20（workflow policy_version 與 config 同步）**：workflow 內宣告的 `policy_version` / `POLICY_VERSION` semver 字面值必須與 `.paul-project.yml` 的 `policy_version` 一致，否則 FAIL（無豁免 label，比照 R-14）；input 宣告與 `${{ inputs.* }}` 模板表達式不在檢查範圍。動機：1.0.2 升版時本 repo 自身的 caller workflow 殘留 1.0.1，僅被 reusable workflow 的 shell 驗證在 CI 階段攔截，本地 policy_check 無法發現——將該驗證提升為引擎規則

### Changed
- **policy_version 1.0.1 → 1.0.2**：隨 R-19 升版；四份 agent convention 檔（`policy_version`、`managed-by@v1.0.2`、白名單與完成前 checklist 加入 R-19）、`.paul-project.yml`、README 規則表與版本敘述一併更新
- **引擎 `VERSION` 與 policy_version 對齊**：`VERSION` 0.0.0 → 1.0.2（pyproject 同步），引擎自此開始打 release tag，R-07 不再因永無 tag 而空轉
- **pytest 設定排除 fixtures**：`--ignore=tests/fixtures`，避免 R-19 fixture 內的假 `test_*.py` 被引擎自身測試蒐集（同名 module 會碰撞）
- **policy_version 1.0.0 → 1.0.1**：新增 R-17 / R-18 與語言規範後同步升版；四份 agent convention 檔的 `policy_version` 與 `managed-by@v1.0.1` 標記、`.paul-project.yml`、README 版本敘述一併更新，讓下游可確認引用的 policy 版本
- **Project-neutral policy config support**：policy engine now prefers
  `.project-policy.yml` while retaining legacy `.paul-project.yml` fallback.
- **Three-repo rollout 文件同步完成**：README 現在明確指向 live `hamanpaul/.github` 與 `hamanpaul/new-project-template`，並補充 fresh smoke repo 已驗證 generated `Policy Check` workflow 可 end-to-end 成功
- **Shell injection 完整防護**：Reusable workflow `Run policy check` 步驟改以 `env:` 繫結 `POLICY_PROFILE` / `POLICY_VERSION`，shell 腳本改用 `$POLICY_PROFILE` / `$POLICY_VERSION`，消除對 `${{ inputs.policy_profile }}` / `${{ inputs.policy_version }}` 的直接插值
- **新增測試 `test_reusable_workflow_run_step_binds_profile_version_via_env`**：驗證 `Run policy check` 步驟精確 env 映射（`POLICY_PROFILE == "${{ inputs.policy_profile }}"` / `POLICY_VERSION == "${{ inputs.policy_version }}"`）且 shell body 不含直接插值
- **R-15 文件一致化**：README.md 與 CHANGELOG.md 中 R-15 描述從「tag / SHA」更新為「完整 40 字元 commit SHA」，與 SHA-only contract 保持一致
- Rename repo from `paul-project-conventions` to `paulsha-conventions`；更新 README、四份 agent convention files 與 fixtures 的 `managed-by` 與 `uses:` 參照
- **OpenSpec 規格文件更新**：新專案 bootstrap spec 與 design doc 更新以反映 reusable workflow 的新 `policy_engine_ref` 輸入需求；template workflow 現在須同時鎖定 reusable workflow SHA 與傳入明確的 policy_engine_ref，確保兩者版本同步
- **README CI 範例 consistency 修正**：使 `uses:` 與 `policy_engine_ref` 兩者都明確鎖定為同一完整 40 字元 commit SHA 範例，不再使用 tag（`@v1.0.0` / `v1.0.0`），確保文件中的 dual-pinning 訊息一致
- **Reusable workflow 輸入描述精確化**：`policy_engine_ref` 輸入描述更新為僅接受完整 40 字元 hex commit SHA；明確排除 tag、short SHA 及 branch ref；新增 workflow 驗證步驟在 `Checkout policy engine` 前強制執行格式檢查（`^[0-9a-f]{40}$`），不符規格的輸入立即 exit 1 並輸出明確錯誤訊息
- **Self-dogfood 測試強化**：`test_caller_workflow_passes_policy_engine_ref_to_reusable` 升級為強型別斷言，要求 `policy_engine_ref` 精確為 `${{ github.sha }}`（執行時解析為完整 40 字元 SHA），並明確禁止退化為 `${{ github.workflow_sha }}`
- **新增測試 `test_reusable_workflow_validates_policy_engine_ref_is_full_sha`**：驗證 reusable workflow 在 checkout 前有 40 字元 SHA 格式驗證步驟
- **新增測試 `test_reusable_workflow_policy_engine_ref_description_says_full_sha_only`**：驗證 `policy_engine_ref` 輸入描述包含 "40" 且不再提及 "tag"
- **OpenSpec 文件一致化**：design.md 與 new-project-bootstrap/spec.md 中的 `policy_engine_ref` 描述從「tag 或 commit SHA」統一改為「完整 40 字元 commit SHA」

### Added
- **R-17 PR↔issue 連結規則**：PR body 出現 `#N` 時必須使用 closing-keyword（`Closes`/`Fixes`/`Resolves #N`），讓 merge 自動關閉 issue 並於 issue timeline 留下 cross-reference；只引用不關閉時上 `policy-exempt:issue-link`（含 TDD 測試 `tests/test_rule_r17_pr_issue_link.py`）
- **R-18 docs/README 對齊規則（WARN）**：`code_paths` 有變動但 `README.md` / `docs/**` 未同步時發出 advisory WARN（不擋 merge），可上 `policy-exempt:docs-sync` 豁免（含 TDD 測試 `tests/test_rule_r18_docs_sync.py`）
- **語言規範 checklist**：repo 屬 `hamanpaul` / `paulc-arc` → PR 與所有 comment 用 zh-tw；arcadyan GitLab → en_US（依 `git remote` 判斷；checklist-only，不做引擎偵測）
- **R-01 ~ R-16 完整規則實作**（TDD 覆蓋 + fixtures）
  - R-01: README.md 存在性檢查
  - R-02: README.md 必備段落（Install / Usage / Version）
  - R-03: CHANGELOG.md 存在性檢查
  - R-04: CHANGELOG.md 格式（Keep-a-Changelog 1.1.0 schema + `[Unreleased]` section）
  - R-05: VERSION 存在性檢查
  - R-06: VERSION 語意檢查（`<MAJOR>.<MINOR>.<PATCH>[-fix.N]`）
  - R-07: VERSION 與最新 tag 一致性（除非 PR 帶 `release:*` label）
  - R-08: `.paul-project.yml` 存在性與完整性（`policy_profile` / `policy_version` 必填）
  - R-09: Code 變動必有 CHANGELOG entry（code_paths 涵蓋檔案變動時，`[Unreleased]` 必須有新增 entry，或 PR 帶 `skip-changelog` + 理由）
  - R-10: PR title conventional-commit 格式（`type(scope): subject` 或 `type: subject`）
  - R-11: PR body checkbox 全勾檢查（帶 `wip` label 時自動通過）
  - R-12: 分支來源正確性（目標=main 要求來源 `feature/*`；目標=`feature/*` 要求來源 `wt/<feature>/*`）
  - R-13: Agent convention files 存在性（`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`）
  - R-14: Agent files policy 版本一致性（四份檔案 `policy_version` 必須與 `.paul-project.yml` 一致）
  - R-15: Caller workflow ref 鎖定檢查（一般 `uses:` 允許 tag 或完整 40 字元 commit SHA，禁止 branch ref 如 `@main`；本次 reusable workflow 的 `policy_engine_ref` 則另由 workflow 內部強制完整 SHA）
  - R-16: CLI help 與 docs 同步檢查（`.paul-project.yml.cli` 宣告的 command，實跑 help 輸出必須與 marker 區塊字元一致）
- **Reusable workflow**：`.github/workflows/policy-check.yml`（下游 repo 直接 `uses:` 呼叫）
- **Composite action**：`.github/actions/policy-check/action.yml`（可獨立使用或被 workflow 呼叫）
- **Helper script**：`scripts/update-cli-help.sh`（本地更新 CLI help marker 區塊，配合 R-16）
- **Agent convention files 完整 checklist**（zh-TW）：
  - 動工前 / 改 code 時 / 改版號時 / claim done 前分階段檢查清單
  - 禁止事項明列（不可發明新豁免 label、不可直接 commit 到 main 等）
  - Exemption Labels 白名單（`policy-exempt:*` / `skip-changelog` / `wip`）
- **使用者文件 README.md 完整化**（zh-TW）：
  - 專案背景與問題定位
  - R-01~R-16 規則總覽表（含豁免 label）
  - CI 整合範例（reusable workflow caller）
  - Helper scripts 使用說明
  - 新專案 bootstrap 流程
- **Self-dogfood 測試增強**：新增 `test_caller_workflow_passes_policy_engine_ref_to_reusable` 結構測試，確保本 repo 的 caller workflow 自身也遵循 dual-pinning 需求（policy_engine_ref 必傳且精確為 `${{ github.sha }}`）

### Changed
- CHANGELOG.md 格式改為 zh-TW 敘述，拆分明細項目（取代過度籠統的兩條 Added）
- 四份 agent files 內容完全同步（`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`）

### Fixed
- 無（baseline 建立階段）
- reusable workflow 不再對下游 repo 執行 `pip install -e .`；改為僅安裝 action runtime 相依，並讓 composite action 直接從自身 source tree 載入 `policy_check`
- **reusable workflow action 解析問題**：移除 `uses: ./.github/actions/policy-check`（在被呼叫 workflow 中此路徑解析自 caller repo，導致 action-not-found）；改為顯式 checkout `hamanpaul/paulsha-conventions` 至 `.policy-engine/` 並直接呼叫 `run.sh`
- **interpreter 不一致**：`run.sh` 移除對 `${WORKSPACE}/.venv/bin/python` 的優先使用；統一使用 `setup-python` 設置的 `python3`，確保安裝與執行使用同一直譯器
- **README 敘述**：更新 CI workflow 說明，反映實際的 policy engine checkout + 安裝流程
- **reusable workflow policy engine 版本漂移**：`Checkout policy engine` 步驟加入 `ref: ${{ github.workflow_sha }}`，確保 policy engine 版本與呼叫者所鎖定的 workflow 版本一致，消除未鎖定時永遠抓 main branch 的風險；同步新增回歸測試 `test_reusable_workflow_policy_engine_checkout_is_pinned`
- **跨 repo reusable workflow 中 `github.workflow_sha` 指向錯誤 repo**：根據 GitHub 官方文件，reusable workflow 中 `github` context 始終屬於 caller workflow，因此 `github.workflow_sha` 是 caller repo 的 SHA，而非 `paulsha-conventions` 的 SHA；改為在 `workflow_call.inputs` 新增必填 `policy_engine_ref` 參數，由呼叫者明確傳入指向 `hamanpaul/paulsha-conventions` 的完整 40 字元 commit SHA；同步更新 `policy-check.yml`（self-dogfood 以 `${{ github.sha }}` 傳入）、README CI 範例、及測試 `test_reusable_workflow_interface_contract` 與 `test_reusable_workflow_policy_engine_checkout_is_pinned`
- **reusable workflow metadata 解析錯誤**：`workflow_call.inputs.policy_engine_ref.description` 不再包含 GitHub expression syntax；避免跨 repo 呼叫時在 job 啟動前就被 GitHub 判定為 invalid workflow

## [1.0.7] - 2026-06-23

### Added
- **新增 R-24（moc-alignment）**：repo 於 `.paul-project.yml` 宣告 `moc`（`static` / `map` / `triggers`）後生效（未宣告 → NA）。三瓣：靜態鮮度（`moc.triggers` 命中但 `moc.static` 未同步 → WARN）／動態連結懸空（`moc.map` 連到不存在產物，本次新破壞 FAIL、陳年 WARN）／動態連結孤兒（active openspec change・`docs/superpowers/{plans,specs}` 未被連結 → WARN，永不 FAIL）。platform-agnostic（純 git-level，不依賴 GitHub/GitLab）。豁免 `policy-exempt:moc-alignment`。R-08 擴充驗 `moc`；r22/r24 共用 link helper 抽至 `policy_check/rules/_doc_links.py`。

## [1.0.6] - 2026-06-23

### Added
- **新增 R-23（引擎 pin 版本 attestation）**：workflow `uses:` 指向 `conventions_engine.repo` 的引擎版本（tag `@vX.Y.Z`，或 SHA `@<sha>` + 尾註 `# vX.Y.Z`）必須與 `.paul-project.yml` 的 `policy_version` 一致，否則 FAIL；純 SHA 無版本註解時降為 WARN（離線無法驗證）；`./` 在地引用或未設 `conventions_engine.repo` 時 not-applicable。豁免 label `policy-exempt:engine-pin`。動機：閉合「repo 實際 pin 的引擎版本 ⟷ 宣告 policy_version」這條既有引擎只驗 intra-repo 自洽、看不到的缺口。
- **`.paul-project.yml` 新增 `agent_files.mode` 與 `conventions_engine.repo`**：`agent_files.mode` 列舉 `copy`（預設）/ `symlink`；`conventions_engine.repo` 為 `owner/repo` 字串（空字串為 NA sentinel）。R-08 擴充驗證兩區塊型別、列舉與格式。

### Changed
- **R-14 升級為 config-gated 單一真檔完整性**：`agent_files.mode: copy`（預設）維持四檔版本相等比對；`symlink` 模式下 canonical `CLAUDE.md` 須為一般檔、`AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md` 須為 resolve 到 `CLAUDE.md` 的 symlink，divergent 複本／錯誤目標／canonical 為 symlink 皆 FAIL。維持無豁免 label（比照原 R-14）。
- **本 repo agent 慣例檔改為 canonical `CLAUDE.md` + symlink**：消除四份 byte-identical 複本，今後只維護 `CLAUDE.md`；`.paul-project.yml` 設 `agent_files.mode: symlink`。

## [1.0.5] - 2026-06-18

### Added
- **新增 R-22（doc-reference 懸空引用）**：偵測 `README.md` / `docs/**` 對 code 產物（檔案路徑、markdown 內部連結、反引號 symbol）的結構化懸空引用。**Prong P**（路徑/連結）走快照存在性、**Prong S**（symbol）走 `base..head` diff（本次刪/改名的 Python `def`/`class`）。diff-aware 分級：本次新破壞 **FAIL**、陳年懸空 **WARN**、無 diff context（本地）Prong P 降 WARN 且 Prong S 關閉。掃描排除 `openspec/**`、`docs/superpowers/**` 與自身 fixtures；`.paul-project.yml` 新增 `doc_reference.allow`（R-08 驗其為 `list[str]`）；豁免 label `policy-exempt:doc-reference`。同步三層治理：Tier 1 checklist（搬/改/刪 code 產物時同步 docs）、Tier 3「PR review 留意語意陳舊」導引（四份 agent 檔），並新增「defer 的版本 bump 須於 merge 當下立即補做」convention。對應 issue #11。

## [1.0.4] - 2026-06-18

> **主題**：R-21 機密標記 config 化（baseline 資料檔 + per-repo extend-only 疊加、結構偵測器 always-on、vendor/OS 名減敏）＋ R-08 驗證 `secret_scan` 標記欄位 schema。`policy_version` 1.0.3 → 1.0.4（`VERSION` / `pyproject.toml` / `.paul-project.yml` / 四份 agent 慣例檔 / caller workflow 同步升版）。對應 engine tag `v1.0.4`、SHA `77a3e8381eeced9dbba623e450ed6a5c1fcc7b18`（見 `RELEASES.md`）。

### Added
- **新增 `RELEASES.md` 版本譜系**：`policy_version` ↔ engine tag/SHA 的權威對照表；1.0.0 / 1.0.1 的 SHA 由下游釘選值事後考據回填，自 1.0.2 起發版流程為「merge → 打 `vX.Y.Z` tag → 回填本表」。

### Changed
- **R-21 偵測改 config-driven markers + always-on 結構偵測器**：偵測拆為兩類——結構偵測器（個人絕對路徑 `/home/<user>/`、私鑰 PEM）恆開且寫死於 code；marker tokens（內部代號／裝置型號等）改由 `resolve_markers(ctx.config)` 從 baseline 資料檔疊加 repo config 動態解析（extend-only、扣除 `public_names`）。一行命中任一結構偵測器或任一 marker token 即 FAIL。行為相較先前一致，唯廠商／OS 名（brcm/broadcom/airoha/prplos/prplog/marvell/mtk 等）已列入 baseline `public_names`、不再觸發。`_SELF_EXEMPT` 新增 `_secret_scan_config.py`、`secret_scan_defaults.yml` 與 `tests/test_secret_scan_config.py`，避免引擎掃描自身的 baseline token 清單時誤報。R-08 schema 同步擴充：`secret_scan` 的 `allow` / `markers` / `public_names` 若存在須為 `list[str]`，型別不符時 FAIL。

### Fixed
- **打包 `policy_check/data/*.yml`**：`pyproject.toml` 新增 `[tool.setuptools.package-data]`，將 `policy_check.data` 下的 `*.yml` 納入 wheel/sdist，確保 R-21 baseline 資料檔（`secret_scan_defaults.yml`）在 pip-install 後可由 `importlib.resources` 載入；否則下游 repo 釘選安裝引擎時 `load_baseline()` 會在 runtime 找不到資料檔。
- **R-21 改掃 git-tracked 檔案**：`_iter_text_files()` 從 `rglob("*")` 改為優先以 `git ls-files` 列舉已追蹤檔案，自動尊重 `.gitignore`，避免 `build/`、`dist/`、`*.egg-info/` 等本地產物含雇主標記時誤報 FAIL；非 git 目錄（如測試 fixture 的暫存目錄）自動 fallback 至原有 rglob 行為，現有測試無需修改。
