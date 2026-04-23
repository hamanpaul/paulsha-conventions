# paulsha-conventions

> `hamanpaul/*` 跨專案 policy 守門員  
> 讓文件、版號、分支、PR 保持一致，防止規範漂移

## 專案背景

本 repo 提供一套跨 `hamanpaul/*` 所有專案的 **policy engine**，目標：

- **新 repo 建立時**：可透過 template（規劃中）或手動 bootstrap 帶入合規骨架
- **CI gate**：PR merge 前擋住不合規變更
- **Agent checklist**：進入 session 時自動看到規範
- **強制同步**：code 與 docs / CHANGELOG / VERSION 必須一起動

### 解決什麼問題？
- 防止「改了 code 忘記改 CHANGELOG」
- 防止「CLI flag 改了但 README 沒更新」
- 防止「分支命名混亂、版號語意不一致」
- 防止「policy 說要遵守但 policy repo 自己不遵守」

本 repo 自身亦 **dog-food** 本套 policy（`profile: flat`, `policy_version: 1.0.0`）。

## 目前狀態

**可以開始用，但定位是 pilot / draft adoption，不是完整生態已齊備的穩定方案。**

目前已可用的部分：

- `policy_check` CLI 可本地執行
- R-01 ~ R-16 已實作並由本 repo 自己 dog-food
- reusable workflow / composite action 已可供下游 repo 接入
- `scripts/update-cli-help.sh` 可支援 R-16 docs 同步

目前仍缺的部分：

- `hamanpaul/.github` 尚未建立，組織層預設 PR template / community health files 尚未集中化
- `hamanpaul/paul-project-template` 尚未建立，新專案 bootstrap 目前以手動方式為主
- 尚未有正式 release tag；下游若要接 reusable workflow，現階段應 **pin commit SHA**

## 規則總覽（R-01 ~ R-16）

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
| R-14 | Agent files policy 版本一致 | 內容 `policy_version` 與 `.paul-project.yml` 不符 | — |
| R-15 | Caller workflow 用 tag / SHA 鎖定 | `uses:` 指向 branch ref（`@main`、`@develop`）或無 ref | — |
| R-16 | CLI help 與 docs 同步 | `.paul-project.yml.cli` 宣告項目，實跑 help 輸出與 marker 區塊不一致 | `policy-exempt:cli-help` |

**Exemption Labels 白名單**：上表所列 `policy-exempt:*` / `skip-changelog` / `wip` 即所有可用豁免 label；gate 只認這些，其他一律視同未豁免。

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

在下游專案 `.github/workflows/policy-check.yml` 中呼叫本 repo 提供的 **reusable workflow**。

> 目前尚未建立穩定 release tag，請先固定 **commit SHA**；不要用 branch ref。

```yaml
# .github/workflows/policy-check.yml
name: Policy Check
on: [pull_request]

jobs:
  policy:
    uses: hamanpaul/paulsha-conventions/.github/workflows/reusable-policy-check.yml@<pinned-commit-sha>
    with:
      policy_profile: stage-driven  # 或 flat
      policy_version: 1.0.0
```

Workflow 會自動：
- Checkout PR context
- 安裝 policy_check 套件
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

### 4. 典型 Use Cases

| Use case | 現在可否開始 | 建議做法 |
|----------|--------------|----------|
| 既有 repo 漸進導入 | 可以 | 先補 `.paul-project.yml`、`README.md`、`CHANGELOG.md`、`VERSION`，本地跑 `policy_check`，再接 CI gate |
| 新專案建立 | 可以 | 目前以手動 bootstrap 建立骨架；待 template repo 建立後可改成 `gh repo create --template` |
| 強制團隊遵循流程 | 可以 | 將 policy workflow 設為 required status check，並搭配 branch protection |
| 組織級預設化 | 部分可行 | 目前先逐 repo 接入；待 `.github` / template repo 建立後可再集中化 |

### 5. 新專案建立（目前建議手動 bootstrap）

在 `paul-project-template` 尚未建立前，建議新 repo 先手動補齊最小骨架：

1. 建 repo，並建立 `feature/*` 工作分支
2. 新增 `.paul-project.yml`
3. 新增 `README.md`、`CHANGELOG.md`、`VERSION`
4. 新增四份 agent convention files：`CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md`
5. 新增 `.github/workflows/policy-check.yml`，呼叫本 repo 的 reusable workflow
6. 本地跑 `python3 -m policy_check --repo .`
7. 將 CI check 設成 required status check 後再開放團隊使用

可參考的最小 workflow 如下：

```bash
mkdir -p .github/workflows
```

```yaml
# .github/workflows/policy-check.yml
name: Policy Check
on:
  pull_request:

jobs:
  policy:
    uses: hamanpaul/paulsha-conventions/.github/workflows/reusable-policy-check.yml@<pinned-commit-sha>
    with:
      policy_profile: flat
      policy_version: 1.0.0
```

### 6. 如何讓專案硬性跟隨這個流程

要「硬性」跟隨，不靠口頭規範，而是靠 merge gate：

1. 每個 repo 都接上 policy workflow
2. GitHub branch protection 要求 PR merge 前必須通過 `Policy Check`
3. 禁止直接 push 到 `main`
4. 團隊日常開發都走 PR，讓 R-09 / R-10 / R-11 / R-12 在 merge 前生效

做到這一步後，流程就會從「建議」變成「不過 gate 就不能 merge」。

### 7. 流程是否有調整彈性

有，但彈性應放在 **policy 設定**，不是讓個別 repo 自行繞過流程。

可調整的地方：

- `.paul-project.yml` 的 `policy_profile`：目前支援 `flat` / `stage-driven`
- `.paul-project.yml` 的 `code_paths`：決定哪些檔案變動會觸發 R-09
- `.paul-project.yml` 的 `cli` 區塊：決定哪些命令需要做 R-16 help sync
- 白名單 exemption labels：用於明確、可審計的例外處理
- workflow ref：可從 pinned SHA 升級成正式 release tag

不建議保留太大彈性的地方：

- 不建議讓 repo 任意改 branch 規則格式
- 不建議讓 repo 自行新增未列入白名單的 exemption label
- 不建議用 branch ref（如 `@main`）引用 reusable workflow

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
- **PATCH**: 累積已完成的 feature batch 計數（本 repo 為 R-01~R-16 完整實作）
- **-fix.N**: 落地後 bug fix（非新 feature、非穩定、非 release）

當前版本：`0.0.0`（R-01~R-16 baseline 建立中，待 merge 後升版）

## 相關專案

- `hamanpaul/.github`（planned）：未來放 GitHub 社群預設（PR template / Issue template / SECURITY / CONTRIBUTING）
- `hamanpaul/paul-project-template`（planned）：未來提供新專案骨架（`gh repo create --template`）

## License

See [`LICENSE`](./LICENSE) if present, otherwise defaults to repository owner's preference.
