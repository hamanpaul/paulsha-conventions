# Policy 版本譜系

`policy_version` ↔ engine 釋出（tag / commit SHA）的權威對照表。
下游 repo 的 `POLICY_ENGINE_REF` 釘選 SHA 時，依此表查對應 policy 版本；升版傳播 PR 必須同時更新 canonical `.project-policy.yml` 的 `policy_version`、四份 agent 檔與此處對應的 SHA。

| policy_version | engine tag | engine SHA | 摘要 |
|----------------|-----------|------------|------|
| 1.0.16 | `v1.0.16` | `42b0dae11eaf435d22ea3116ae2b9593ffcb4aff` | open-issue batch：#63 distribution identity（arc-conventions 發行接口）、#61 引擎版本 gate（fail-loud + 報告表頭）、#62 R-19 結構化偵測（含 canonical tests.yml 骨架）、#52 activation 斷電級 crash recovery（fsync journal + 自動收斂）、#60 ISO/IEC 42001 opt-in profile 設計；另收斂 changelog docs type 與 #57 遺留的 release smoke fragment |
| 1.0.15 | `v1.0.15` | `a764806046c410eb4f254ac0b6a8aec8b7559dab` | tag 觸發的 release workflow：依支援的 Python minor version 逐一建置 runtime bundle、驗證 archive digest 與離線安裝，全數通過才發布 GitHub Release；release notes 由該版 CHANGELOG 段落、archive SHA-256 對照與前版 compare 連結組成。本版為首個由 workflow 自動發行的 release |
| 1.0.14 | `v1.0.14` | `451c2680fb3a1f977fcbc8007baaa7dbe415cf03` | #48 建立 clean-tag versioned runtime bundle、exact-version selector、offline install/activate/rollback、installed wheel/venv identity attestation，並將 `.project-policy.yml` 升格為 canonical public manifest；公司 artifact authority 仍由 #39 決策 |
| 1.0.13 | `v1.0.13` | `57dc4e8d54697be3400d4f58ee34c2e0c5681411` | #42 修正 release ledger tag SHA 與自我檢測；#45 將 R-21 改為 visibility-aware 並擴充 credential detectors／減敏輸出；#46 建立 canonical local CI-parity `preflight-ci` skill、pinned/source/offline engine 驗證與 fail-closed gate orchestration |
| 1.0.12 | `v1.0.12` | `25d31e021e45c2991c718923ae2dd49bc3d0b542` | #30（提案 A）`.paul-project.yml` 新增 optional `auto_build:` 區塊（LLM auto build 慣例欄位 description/setup/steps/artifacts/verify）；R-08 lenient 形狀驗證（未知 subkey 放行、顯式 null 視同未宣告、engine 永不執行其中命令）。提案 B（paul-scans 注入機制）於 hamanpaul/custom-skills#16 交付 |
| 1.0.11 | `v1.0.11` | `1d653c97c8c8c3409c61576d4f306118d476094e` | #20 引擎內部化 / GitLab 離線 pip gate：`pr_context` 加 GitLab MR provider（`CI_MERGE_REQUEST_*`、R-12 於 GitLab 標 NA）、`changed_files` 拆 SHA/branch 路徑；R-23 pip-mode attestation（顯式 `conventions_engine.mode: pip`、比對已安裝 `policy-check` 版本、fail-closed、PEP440 正規化）+ R-08 驗 `mode` 列舉；離線 wheel（vendored 相依）+ 版本 lockstep + CI 離線 smoke；發行管道選型另追蹤。＋ #35 規則 family 呈現層分組（`families.py` + report OTHER catch-all，零 rule_id/label 變動）＋ README 版號 R-26 generated-fact dogfood ＋ 覆審 nits。GitHub 路徑零回歸 |
| 1.0.10 | `v1.0.10` | `ee87a6d5ed91209d944934a2559f4f2622fd1ac2` | #25（子項 1）doc↔code drift 抽成語言無關、零設定的共用核心 `policy_check/doc_drift/`（refs/paths/symbols/coverage/langs/provision/exempt primitive，symbol 用 universal-ctags scoped identity；支援 Python/bash/C/C++）＋ 可被外部 repo `uses:` 的獨立 composite Action（doc-drift / moc 兩 mode、自理 base/head SHA 供給 + fail-fast）；R-22/R-24 改委派共用核心（單一真相、純單字不誤報、限定式 top-level 不放過）；誤報雙軌豁免（inline marker + `.doc-drift-allow`）|
| 1.0.9 | `v1.0.9` | `376cc3c5dabcccae8a97e7e7129591daa7f539ed` | #24 CHANGELOG per-PR fragment（`changelog.d/<issue>-<slug>.md` 消除並行 agent 的 `[Unreleased]` 衝突；R-09 改驗 fragment、R-04 不再要求 `[Unreleased]`；新增 `policy_check.changelog collate` 於 release 收斂碎片成 Keep-a-Changelog dated 段；hard cutover、行為綁版本）。本版為 fragment 模型首次發版（CHANGELOG `## [1.0.9]` 段由 `collate` 自 fragment 產生） |
| 1.0.8 | `v1.0.8` | `8337bea081422302707a39d2b03fb4eded132dda` | #23 跨 repo policy 漂移治理（`policy_check/drift.py` ops 工具：`report` 唯讀儀表板 / `check` org freshness gate，含 `-fix.N` 完整排序；`docs/org-ruleset-runbook.md` + 升版傳播 SOP；engine 不改下游）＋ #26 文件規則補強（`doc_paths` 共用 canonical doc scope 補強 R-18/R-22；R-25 `doc_coverage` omission gate；R-26 `generated_facts` 通用 marker-sync；R-08 擴充驗證；R-16 抽 `_marker_sync` 共用 helper） |
| 1.0.7 | `v1.0.7` | `a35ef15acec1022bcbe721d81bbd461945588369` | R-24（moc-alignment）：repo 宣告 `moc` 後盯靜態脈絡／動態連結地圖與本次變更同步（靜態鮮度 WARN／連結懸空 diff-aware FAIL-WARN／連結孤兒 WARN，永不 FAIL）；platform-agnostic（純 git-level）；R-08 擴充驗 `moc`；r22/r24 共用 link helper 抽至 `_doc_links`；新增豁免 label `policy-exempt:moc-alignment` |
| 1.0.6 | `v1.0.6` | `572d364ef8101bbcf3c08548ddf059e46ef8d0fb` | agent 慣例檔 symlink 單一真檔（canonical `CLAUDE.md`，R-14 config-gated `agent_files.mode`）＋ R-23 engine pin ⟷ `policy_version` attestation（`conventions_engine.repo`，tag 或 SHA+`# vX.Y.Z`）＋ R-08 擴充驗證；新增豁免 label `policy-exempt:engine-pin` |
| 1.0.5 | `v1.0.5` | `484f963adddf384d30fa0dd85aef35dddf822ee7` | R-22 doc-alignment 三層治理：`README.md` / `docs/**` 結構化懸空引用偵測（Prong P 路徑／連結快照 + Prong S diff 驅動 symbol、diff-aware 分級）＋ Tier 1/3 convention ＋ R-08 `doc_reference.allow` schema |
| 1.0.4 | `v1.0.4` | `77a3e8381eeced9dbba623e450ed6a5c1fcc7b18` | R-21 機密標記 config 化（baseline 資料檔 + per-repo extend-only 疊加、結構偵測器 always-on、廠商／OS 名列入 `public_names` 減敏）＋ R-08 驗證 `secret_scan` 標記欄位 schema |
| 1.0.3 | `v1.0.3` | `614caf23f6514d865cb43e77b53837a273b0b07f` | 新增 R-21（機密掃描：`tier: shareable` 的 repo 含雇主標記／個人絕對路徑／私鑰標頭則 FAIL，掃 git-tracked 檔，自身與 `secret_scan.allow` 豁免，label `policy-exempt:secret-scan`）與 `.paul-project.yml` 的 `tier` 欄位 |
| 1.0.2 | `v1.0.2` | `98487868a098e22647074c677a58633ce4fa19be` | 新增 R-19（repo 有測試則 CI 必須執行，豁免 `policy-exempt:ci-tests`）與 R-20（workflow 宣告的 policy_version 須與 `.paul-project.yml` 一致）；引擎 `VERSION` 自此與 policy_version 對齊並開始打 tag |
| 1.0.1 | —（未打 tag） | `4ff59b6c35a46a87af3c3e641975743ee8fa0858` | R-17（PR↔issue closing-keyword）、R-18（docs 對齊，WARN）、語言規範 |
| 1.0.0 | —（未打 tag） | `8454aa1967b752ea38c82edd79a8439b5bde915b` | R-01 ~ R-16 初版 |

> 註：1.0.0 / 1.0.1 的 SHA 取自下游 repo 當時的 `POLICY_ENGINE_REF` 釘選值（ocr-from2xlsx、paulshaclaw 等），屬事後考據；自 1.0.2 起，發版流程改為「merge → 打 `vX.Y.Z` tag → 回填本表 SHA」。

## 升版傳播 SOP（下游 repo 自助）

canonical bump 後，落後的下游 repo 由**其自身 agent** 依序升版（engine 不主動改下游；`python3 -m policy_check.drift report --org hamanpaul` 會點名哪些 repo `behind`）：

1. 以 `git rev-list -n1 vX.Y.Z` 取得目標 tag 的完整 commit SHA，並與上表的 `policy_version`、engine tag 與 engine SHA 三者交叉核對。
2. 改 canonical `.project-policy.yml` 的 `policy_version`（legacy alias 只供相容，不應由新 PR 產生）。
3. 若 repo 有啟用 README 的 `repo-version` generated-fact marker，更新其值為新 `VERSION`（R-26 為安全網，漏改則 CI 會擋）。
4. re-pin workflow 的 `policy_engine_ref` 為新 SHA，並補 `# vX.Y.Z` 尾註（R-23）。
5. canonical `CLAUDE.md` 有變則更新（`AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md` 在 `agent_files.mode: symlink` 下自動跟隨）。
6. `python3 -m pytest -q` 與 `python3 -m policy_check --repo .` 全綠。
7. 開 PR（`hamanpaul` → zh-tw），body 寫 `Closes #N`（若有對應 issue）。

> org `Policy Freshness` gate 會擋下未做此 SOP 的 merge（見 [`docs/org-ruleset-runbook.md`](docs/org-ruleset-runbook.md)）。
