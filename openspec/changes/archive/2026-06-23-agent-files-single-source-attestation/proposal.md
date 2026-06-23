## Why

四份 agent 慣例檔（`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`）目前是 byte-identical 實體複本，須手動同步、R-14 僅事後驗版本一致（業界視為 anti-pattern）。同時版號鏈只驗 intra-repo 自洽：沒有任何規則把宣告的 `policy_version` 綁到「repo 實際 pin 的引擎版本」，下游可升級引擎卻忘改版號而全規則照樣 PASS——正是 P0 跨 repo 漂移的成因。

## What Changes

- 將 `CLAUDE.md` 立為唯一真檔（canonical）；`AGENTS.md` / `GEMINI.md` → `CLAUDE.md`、`.github/copilot-instructions.md` → `../CLAUDE.md` 改為 symlink。「以後只維護一份」。
- `.paul-project.yml` 新增 `agent_files.mode`（列舉 `{symlink, copy}`，預設 `copy`）與 `conventions_engine.repo`（str）。R-08 擴充驗證兩區塊。
- **R-14 升級為 config-gated**：`copy`（預設）維持現行四檔版本相等比對；`symlink` 模式下 canonical 須真檔、其餘三檔須為 symlink 且 resolve 到 `CLAUDE.md`，divergent 複本／指向錯誤／canonical 為 symlink 皆 FAIL。
- **新增 R-23 engine-pin attestation**：workflow `uses:` 指向 `conventions_engine.repo` 的引擎版本（tag `@vX.Y.Z`，或 SHA `@<sha>` + 尾註 `# vX.Y.Z`）須 == `policy_version`，不齊 FAIL；純 SHA 無註解 WARN；`./` 在地引用或未設 → NA。
- Exemption 白名單新增 `policy-exempt:engine-pin`（R-23）。
- 慣例檔字句、README/docs、CHANGELOG 同步；merge 當下 release bump `1.0.5 → 1.0.6`。
- 非破壞：`agent_files.mode` 預設 `copy`，下游 bump 引擎後行為不變，可各自排程遷移。

## Capabilities

### New Capabilities
- `agent-files-single-source`: agent 慣例檔以 canonical `CLAUDE.md` + symlink 為單一真檔；`agent_files.mode` 設定與 R-08 驗證；R-14 config-gated 單一真檔完整性檢查。
- `engine-version-attestation`: repo 實際 pin 的 conventions 引擎版本須與宣告的 `policy_version` 對齊；`conventions_engine.repo` 設定與 R-08 驗證；R-23 attestation gate。

### Modified Capabilities
<!-- 無既有 spec 之 requirement 改變；R-14/R-23 為新引入規則，既有 capability spec 不受影響。 -->

## Impact

- **規則引擎**：`policy_check/rules/r14_agent_files_version.py`（語意升級）、新增 `policy_check/rules/r23_engine_pin_attestation.py`、`policy_check/rules/r08_policy_config_schema.py`（擴充）、`policy_check/config.py`（`agent_files.mode` 預設）。
- **慣例檔**：`AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md` 轉 symlink；`CLAUDE.md` 文字與白名單更新。
- **設定**：`.paul-project.yml` 新增 `agent_files`、`conventions_engine`。
- **文件**：`README.md` / `docs/**`（R-14 新語意、R-23 新規則）、`CHANGELOG.md`。
- **測試**：R-14（兩模式）、R-08（兩新區塊）、R-23（tag/SHA/WARN/NA）fixtures。
- **release**：`VERSION` / `policy_version` / `managed-by` / workflow `policy_version` / tag / `RELEASES.md` 於 merge 當下 bump `1.0.5 → 1.0.6`。
- **下游**：預設 `copy` 不打斷；`new-project-template` 後續可 opt-in（本變更非目標）。
