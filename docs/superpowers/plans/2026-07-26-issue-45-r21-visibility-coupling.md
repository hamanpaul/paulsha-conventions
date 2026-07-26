# Issue 45：R-21 visibility coupling 與輸出減敏計畫

**Issue:** `hamanpaul/paulsha-conventions#45`

**Builder boundary:** `policy_check` 的 repository visibility metadata、R-21 detector/verdict、對應 OpenSpec、測試、README/CLAUDE 與 changelog fragment。不得修改 `testpilot-core`。

## Live evidence

- `R21SecretScan.check()` 對 `tier != shareable` 在掃檔前直接回 `PASS`。
- `RuleContext` 沒有 repository visibility。
- GitHub event payload 與 GitLab CI 均可提供 visibility，但目前 `pr_context` 未抽取。
- `hamanpaul/testpilot-core` 目前仍為 PUBLIC，GitHub default branch 搜尋仍可找到 issue 所列的裝置型號、公司名稱與 driver commit marker。

## Verdict contract

R-21 必須掃描所有 tier；`tier` 不再決定「要不要掃」，只參與 verdict：

| tier / visibility | structural 或 credential hit | employer marker-only hit | clean |
| --- | --- | --- | --- |
| `shareable` / 任意 | FAIL | FAIL | PASS |
| 非 shareable / `public` | FAIL | WARN | PASS |
| 非 shareable / `private` 或 `internal` | WARN | WARN | PASS |
| 非 shareable / `unknown` | FAIL | WARN | PASS（訊息明示 visibility unknown） |

若同檔或同 repo 同時有多類 hit，採最嚴重 verdict。`policy-exempt:secret-scan` 與 `secret_scan.allow` 維持既有白名單語意。

## Metadata contract

1. `RuleContext` 新增 `repo_visibility: str | None`。
2. GitHub：
   - 從 event `repository.visibility` 讀取；
   - 若缺 visibility，以 `repository.private` boolean 正規化；
   - 不因沒有 pull request 就丟失 repository metadata。
3. GitLab：從 `CI_PROJECT_VISIBILITY` 讀取。
4. CLI 新增 `--repo-visibility {public,private,internal,unknown}` 供 local/offline CI parity 注入。
5. precedence：provider payload > explicit CLI > `unknown`。
6. policy engine 不得呼叫 GitHub/GitLab API；visibility 必須由既有 event/env/CLI authority 注入。

## Detector 與減敏

1. 保留 personal absolute path 與 private-key header detector。
2. 新增至少：
   - AWS access-key ID 測試模式；
   - GitHub classic/fine-grained token prefix 測試模式。
3. detector 分成 `structural`、`credential`、`marker` 類別，verdict 不可只靠單一 regex。
4. report 只輸出 `repo-relative path:line`、detector 類別與命中數；不得輸出 matched value、原始 line 或 token 片段。
5. marker token 仍由 baseline + repo config extend-only 決定；`public_names` 只能抑制 marker，不能抑制 credential/structural detector。

## TDD 與文件

1. 先擴充 `tests/test_rule_r21_secret_scan.py`：
   - public + work + fake AWS key ⇒ FAIL；
   - public + work + employer marker only ⇒ WARN；
   - private + work +相同 structural/credential marker ⇒ WARN；
   - unknown + work + credential ⇒ FAIL；
   - detail/message 不含測試 secret；
   - shareable 舊案例與 allowlist 不退化。
2. 擴充 `tests/test_pr_context_*.py` 與 CLI context tests，釘住 GitHub/GitLab/manual precedence。
3. 建立 active OpenSpec change `r21-visibility-coupling`，更新 canonical `openspec/specs/secret-scan/spec.md` 的 delta。
4. 更新 README 中英 R-21 說明、CLI help marker與 canonical `CLAUDE.md` checklist。
5. 新增 `changelog.d/45-r21-visibility-coupling.md`，`type: fix`、`issue: 45`。

## 下游 phase（本 slice 驗收後）

引擎先 release，再於 `testpilot-core` 獨立 worktree：

1. 在不印出命中內容的前提下產生 path-only inventory。
2. 將雇主/裝置內容移至 private canonical repo，或改寫 public repo 使其不再含內部資訊。
3. 確認 known markers 搜尋為零，且 R-21 在 `tier: shareable` 下通過。
4. 下游清理不得與本 engine slice 共用 branch 或 write scope。

## 驗收

- targeted R-21 / PR-context / CLI tests 全綠。
- `python3 -m pytest -q`
- `openspec validate --all`
- `python3 -m policy_check --repo .` 全綠。
- report 無任何測試 secret 明文。
- Foreign reviewer 無未處置 critical/important finding。
