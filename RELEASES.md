# Policy 版本譜系

`policy_version` ↔ engine 釋出（tag / commit SHA）的權威對照表。
下游 repo 的 `POLICY_ENGINE_REF` 釘選 SHA 時，依此表查對應 policy 版本；升版傳播 PR 必須同時更新 `.paul-project.yml` 的 `policy_version`、四份 agent 檔與此處對應的 SHA。

| policy_version | engine tag | engine SHA | 摘要 |
|----------------|-----------|------------|------|
| 1.0.7 | `v1.0.7` | `e24fbd679d35d04a79ea21aff7733fadebd5e77e` | R-24（moc-alignment）：repo 宣告 `moc` 後盯靜態脈絡／動態連結地圖與本次變更同步（靜態鮮度 WARN／連結懸空 diff-aware FAIL-WARN／連結孤兒 WARN，永不 FAIL）；platform-agnostic（純 git-level）；R-08 擴充驗 `moc`；r22/r24 共用 link helper 抽至 `_doc_links`；新增豁免 label `policy-exempt:moc-alignment` |
| 1.0.6 | `v1.0.6` | `261f3f64bfe33a9762355c65cdc702b00110fea3` | agent 慣例檔 symlink 單一真檔（canonical `CLAUDE.md`，R-14 config-gated `agent_files.mode`）＋ R-23 engine pin ⟷ `policy_version` attestation（`conventions_engine.repo`，tag 或 SHA+`# vX.Y.Z`）＋ R-08 擴充驗證；新增豁免 label `policy-exempt:engine-pin` |
| 1.0.5 | `v1.0.5` | `e9c806984f1df5b7adbe79b4bdc9930a8cea1932` | R-22 doc-alignment 三層治理：`README.md` / `docs/**` 結構化懸空引用偵測（Prong P 路徑／連結快照 + Prong S diff 驅動 symbol、diff-aware 分級）＋ Tier 1/3 convention ＋ R-08 `doc_reference.allow` schema |
| 1.0.4 | `v1.0.4` | `77a3e8381eeced9dbba623e450ed6a5c1fcc7b18` | R-21 機密標記 config 化（baseline 資料檔 + per-repo extend-only 疊加、結構偵測器 always-on、廠商／OS 名列入 `public_names` 減敏）＋ R-08 驗證 `secret_scan` 標記欄位 schema |
| 1.0.3 | `v1.0.3` | `614caf23f6514d865cb43e77b53837a273b0b07f` | 新增 R-21（機密掃描：`tier: shareable` 的 repo 含雇主標記／個人絕對路徑／私鑰標頭則 FAIL，掃 git-tracked 檔，自身與 `secret_scan.allow` 豁免，label `policy-exempt:secret-scan`）與 `.paul-project.yml` 的 `tier` 欄位 |
| 1.0.2 | `v1.0.2` | `98487868a098e22647074c677a58633ce4fa19be` | 新增 R-19（repo 有測試則 CI 必須執行，豁免 `policy-exempt:ci-tests`）與 R-20（workflow 宣告的 policy_version 須與 `.paul-project.yml` 一致）；引擎 `VERSION` 自此與 policy_version 對齊並開始打 tag |
| 1.0.1 | —（未打 tag） | `4ff59b6c35a46a87af3c3e641975743ee8fa0858` | R-17（PR↔issue closing-keyword）、R-18（docs 對齊，WARN）、語言規範 |
| 1.0.0 | —（未打 tag） | `8454aa1967b752ea38c82edd79a8439b5bde915b` | R-01 ~ R-16 初版 |

> 註：1.0.0 / 1.0.1 的 SHA 取自下游 repo 當時的 `POLICY_ENGINE_REF` 釘選值（ocr-from2xlsx、paulshaclaw 等），屬事後考據；自 1.0.2 起，發版流程改為「merge → 打 `vX.Y.Z` tag → 回填本表 SHA」。
