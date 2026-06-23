# paulsha-conventions

> `hamanpaul/*` 跨專案 policy 守門員  
> 讓文件、版號、分支、PR 保持一致，防止規範漂移

## 專案背景

本 repo 提供一套跨 `hamanpaul/*` 所有專案的 **policy engine**，目標：

- **新 repo 建立時**：自動帶入合規骨架（via `new-project-template`）
- **CI gate**：PR merge 前擋住不合規變更
- **Agent checklist**：進入 session 時自動看到規範
- **強制同步**：code 與 docs / CHANGELOG / VERSION 必須一起動

### 解決什麼問題？
- 防止「改了 code 忘記改 CHANGELOG」
- 防止「CLI flag 改了但 README 沒更新」
- 防止「分支命名混亂、版號語意不一致」
- 防止「policy 說要遵守但 policy repo 自己不遵守」

本 repo 自身亦 **dog-food** 本套 policy（`profile: flat`, `policy_version: 1.0.5`）。

版本譜系（policy_version ↔ engine tag/SHA 對照）見 [`RELEASES.md`](./RELEASES.md)。

## 規則總覽（R-01 ~ R-24）

| ID | 檢查項 | 失敗條件 | 豁免 label |
|----|--------|----------|------------|
| R-01 | `README.md` 存在 | 缺檔或 <100 byte | — |
| R-02 | `README.md` 必備段落 | 缺 `## Install` / `## Usage` / `## Version` | `policy-exempt:readme-sections` |
| R-03 | `CHANGELOG.md` 存在 | 缺檔 | — |
| R-04 | `CHANGELOG.md` 格式合規 | 非 Keep-a-Changelog 1.1.0 / 缺 `[Unreleased]` | `policy-exempt:changelog-format` |
| R-05 | `VERSION` 存在 | 缺檔 | — |
| R-06 | `VERSION` 符合語意 | 不匹配 `<MAJOR>.<MINOR>.<PATCH>(-fix\.\d+)?` | — |
| R-07 | `VERSION` 與最新 tag 一致 | 不一致且無 `release:*` label | — |
| R-08 | `.paul-project.yml` 存在且完整 | 缺檔或缺 `policy_profile` / `policy_version` | — |
| R-09 | Code 變動必有 CHANGELOG entry | code path 有變動但 `[Unreleased]` 未動 | `skip-changelog` |
| R-10 | PR title 符合 conventional-commit | regex 不匹配 | `policy-exempt:pr-title` |
| R-11 | PR body checkbox 全勾 | 必勾項未勾滿 | `wip` 時自動通過 |
| R-12 | 分支來源正確 | 目標=main 時來源非 `feature/*`；目標=`feature/*` 時來源非 `wt/<feature>/*` | `policy-exempt:branch-name` |
| R-13 | Agent convention files 存在 | 缺 `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md` | `policy-exempt:agent-files` |
| R-14 | Agent files 單一真檔完整性（config-gated） | `copy`（預設）：四檔 `policy_version` 與 `.paul-project.yml` 不符；`symlink`：鏡像檔非 symlink／未 resolve 到 `CLAUDE.md`／canonical 自身為 symlink | — |
| R-15 | Caller workflow 用 tag / SHA 鎖定（本 repo 的 policy-check dual-pinning path 另要求完整 40 字元 SHA） | `uses:` 指向 branch ref（`@main`、`@develop`）或無 ref | — |
| R-16 | CLI help 與 docs 同步 | `.paul-project.yml.cli` 宣告項目，實跑 help 輸出與 marker 區塊不一致 | `policy-exempt:cli-help` |
| R-17 | PR↔issue 連結 | PR body 出現 `#N` 但非 closing-keyword（`Closes`/`Fixes`/`Resolves #N`）形式 | `policy-exempt:issue-link` |
| R-18 | docs/README 對齊 code 變動 | code_paths 有變動但 `README.md` / `docs/**` 未同步（**WARN**，不擋 merge） | `policy-exempt:docs-sync` |
| R-19 | repo 有測試則 CI 必須執行 | 存在 `tests/`（含 `test_*.py` / `*_test.py`）但 `.github/workflows/**` 無任何測試執行指令（pytest / unittest / npm test 等） | `policy-exempt:ci-tests` |
| R-20 | Workflow policy_version 與 config 同步 | workflow 內宣告的 `policy_version` / `POLICY_VERSION` 字面值與 `.paul-project.yml` 的 `policy_version` 不一致 | — |
| R-21 | tier=shareable repo 機密掃描 | 宣告 `tier: shareable` 的 repo 含雇主標記（內部代號、裝置型號等）／個人絕對路徑／憑證模式，且不在 `secret_scan.allow` 或自我豁免範圍 | `policy-exempt:secret-scan` |
| R-22 | docs 對 code 產物引用無懸空 | `README.md` / `docs/**` 引用的路徑／內部連結／反引號 symbol 在 repo 不存在；本次變更新破壞 **FAIL**、陳年懸空 **WARN**、無 diff context（本地）降 WARN | `policy-exempt:doc-reference` |
| R-23 | 引擎 pin 版本與 policy_version 對齊 | workflow `uses:` 指向 `conventions_engine.repo` 的引擎版本（tag `@vX.Y.Z` 或 SHA `@<sha>` + 尾註 `# vX.Y.Z`）與 `.paul-project.yml` 的 `policy_version` 不一致 **FAIL**；純 SHA 無註解 **WARN**；`./` 在地引用或未設 `conventions_engine.repo` 則 NA | `policy-exempt:engine-pin` |
| R-24 | MOC 與本次變更對齊 | repo 宣告 `moc` 時：`moc.triggers` 命中但 `moc.static` 未同步（**WARN**）／`moc.map` 連結懸空（本次新破壞 **FAIL**、陳年 **WARN**）／active openspec change・plan・spec 未被連結（**WARN**，永不 FAIL）；未宣告 `moc` 則 NA | `policy-exempt:moc-alignment` |

**Exemption Labels 白名單**：上表所列 `policy-exempt:*` / `skip-changelog` / `wip` 即所有可用豁免 label；gate 只認這些，其他一律視同未豁免。

## Doc-alignment governance（三層）

文件陳舊分三層治理，只有 Tier 2 為確定性 gate：

- **Tier 1（預防）**：agent 改 code 時同步更新引用該產物的 docs（見四份 agent 慣例檔 checklist）。
- **Tier 2（確定性 gate）**：R-22 在 CI 偵測 `README.md` / `docs/**` 的結構化懸空引用——本次新破壞 FAIL、陳年 WARN。確定性層只看「結構性 rot」（引用死掉），不判斷語意。
- **Tier 3（語意複審）**：建議將 GitHub Copilot 設為 PR reviewer，複審「引用仍在但描述已過時」的語意陳舊（advisory，不擋 merge）。

## Install

```bash
python3 -m pip install -e ".[test]"
```

## Usage

### 1. 本地檢查（開發階段）

對當前 repo 跑完整檢查：

```bash
python3 -m policy_check --repo .
```

只跑指定規則（例如：快速檢查文件結構）：

```bash
python3 -m policy_check --repo . --only R-01,R-02,R-03
```

### 2. CI 整合（下游 repo）

在下游專案 `.github/workflows/policy-check.yml` 中呼叫本 repo 提供的 **reusable workflow**：

```yaml
# .github/workflows/policy-check.yml
name: Policy Check
on: [pull_request]

jobs:
  policy:
    # Pin both the reusable workflow and the policy engine to the SAME full 40-char commit SHA.
    # Do NOT use a tag or branch ref — full SHA is required by the policy engine validation step.
    uses: hamanpaul/paulsha-conventions/.github/workflows/reusable-policy-check.yml@aabbccddeeff0011223344556677889900aabbcc
    with:
      policy_profile: stage-driven  # 或 flat
      policy_version: 1.0.1
      # 必須傳入完整 40 字元 hex commit SHA，指向 hamanpaul/paulsha-conventions。
      # 不可使用 tag、short SHA 或 github.workflow_sha（那是 caller 自己 repo 的 SHA）。
      # uses: 與 policy_engine_ref 兩者必須鎖定到同一個 SHA。
      policy_engine_ref: aabbccddeeff0011223344556677889900aabbcc
```

Workflow 會自動：
- Checkout PR context
- 從 `hamanpaul/paulsha-conventions` 取得 policy engine（含 PyYAML 依賴）
- 跑完整規則檢查
- 在 GitHub Actions Summary 輸出結果

### 3. Helper Scripts

#### `scripts/update-cli-help.sh`

**用途**：實跑 `.paul-project.yml.cli` 宣告的每個 command，自動回寫 docs 內的 marker 區塊（R-16 同步機制）。

**使用**：
```bash
cd <下游專案>
bash /path/to/paulsha-conventions/scripts/update-cli-help.sh
```

**注意**：
- CI **不** auto-fix（避免 PR 在沒有 dev 意識下被改）
- 開發者在本地跑，commit 更新後的 docs
- 此 script 固定 `LC_ALL=C` 避免多語系輸出差異

### 4. 新專案 Bootstrap

使用 `hamanpaul/new-project-template` 建立新 repo，自動包含：
- `.paul-project.yml`（需填入 profile / version）
- `README.md` / `CHANGELOG.md` / `VERSION` 骨架
- 四份 agent convention files（`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`）
- `.github/workflows/policy-check.yml` 呼叫本 repo reusable workflow

目前已落地的 live rollout repos：
- [`hamanpaul/.github`](https://github.com/hamanpaul/.github)：提供 account-level PR template / CONTRIBUTING / SECURITY defaults
- [`hamanpaul/new-project-template`](https://github.com/hamanpaul/new-project-template)：提供新專案 bootstrap skeleton 與 dual-pinned `Policy Check` workflow

這條 bootstrap 路徑已用 fresh smoke repo 驗證：只補 smoke metadata 的 PR 即可直接通過 generated `Policy Check` workflow，無需手改 workflow 檔。暫時只剩遠端 smoke repo 清理尚未完成，因目前 `gh` token 缺少 `delete_repo` scope。

```bash
gh repo create hamanpaul/<new-project> --template hamanpaul/new-project-template
```

### CLI Help

<!-- BEGIN: cli-help marker="policy-check-help" -->
usage: policy-check [-h] [--repo REPO] [--pr-title PR_TITLE]
                    [--pr-body PR_BODY] [--pr-labels PR_LABELS]
                    [--pr-base-ref PR_BASE_REF] [--pr-head-ref PR_HEAD_REF]
                    [--only ONLY]

options:
  -h, --help            show this help message and exit
  --repo REPO           Repository root
  --pr-title PR_TITLE
  --pr-body PR_BODY
  --pr-labels PR_LABELS
                        Comma-separated
  --pr-base-ref PR_BASE_REF
  --pr-head-ref PR_HEAD_REF
  --only ONLY           Comma-separated rule IDs (e.g. R-01,R-09)
<!-- END: cli-help marker="policy-check-help" -->

## Version

`VERSION` 檔（repo root）為專案版號 single source of truth。

**本 repo 版號語意**（`profile: flat`）：
- **MAJOR**: 正式 release（feature 達到對外可用狀態）
- **MINOR**: 功能穩定（已規劃 feature 全 landed + 7 天無 hotfix）
- **PATCH**: 累積已完成的 feature batch 計數（本 repo 為 R-01~R-23 完整實作）
- **-fix.N**: 落地後 bug fix（非新 feature、非穩定、非 release）

當前版本：見 `VERSION`（現為 `1.0.6`）。

## 相關專案

- [`hamanpaul/.github`](https://github.com/hamanpaul/.github)：GitHub 社群預設（PR template / Issue template / SECURITY / CONTRIBUTING）
- [`hamanpaul/new-project-template`](https://github.com/hamanpaul/new-project-template)：新專案骨架（供 `gh repo create --template` 使用）

## License

See [`LICENSE`](./LICENSE) if present, otherwise defaults to repository owner's preference.
