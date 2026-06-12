# Policy 版本譜系

`policy_version` ↔ engine 釋出（tag / commit SHA）的權威對照表。
下游 repo 的 `POLICY_ENGINE_REF` 釘選 SHA 時，依此表查對應 policy 版本；升版傳播 PR 必須同時更新 `.paul-project.yml` 的 `policy_version`、四份 agent 檔與此處對應的 SHA。

| policy_version | engine tag | engine SHA | 摘要 |
|----------------|-----------|------------|------|
| 1.0.2 | `v1.0.2` | `98487868a098e22647074c677a58633ce4fa19be` | 新增 R-19（repo 有測試則 CI 必須執行，豁免 `policy-exempt:ci-tests`）與 R-20（workflow 宣告的 policy_version 須與 `.paul-project.yml` 一致）；引擎 `VERSION` 自此與 policy_version 對齊並開始打 tag |
| 1.0.1 | —（未打 tag） | `4ff59b6c35a46a87af3c3e641975743ee8fa0858` | R-17（PR↔issue closing-keyword）、R-18（docs 對齊，WARN）、語言規範 |
| 1.0.0 | —（未打 tag） | `8454aa1967b752ea38c82edd79a8439b5bde915b` | R-01 ~ R-16 初版 |

> 註：1.0.0 / 1.0.1 的 SHA 取自下游 repo 當時的 `POLICY_ENGINE_REF` 釘選值（ocr-from2xlsx、paulshaclaw 等），屬事後考據；自 1.0.2 起，發版流程改為「merge → 打 `vX.Y.Z` tag → 回填本表 SHA」。
