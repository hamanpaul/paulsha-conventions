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

本 repo 自身亦 **dog-food** 本套 policy（`profile: flat`；`policy_version` 見 `.paul-project.yml` / `VERSION`）。

版本譜系（policy_version ↔ engine tag/SHA 對照）見 [`RELEASES.md`](./RELEASES.md)。

## 規則總覽（R-01 ~ R-26）

| ID | 檢查項 | 失敗條件 | 豁免 label |
|----|--------|----------|------------|
| R-01 | `README.md` 存在 | 缺檔或 <100 byte | — |
| R-02 | `README.md` 必備段落 | 缺 `## Install` / `## Usage` / `## Version` | `policy-exempt:readme-sections` |
| R-03 | `CHANGELOG.md` 存在 | 缺檔 | — |
| R-04 | `CHANGELOG.md` 格式合規 | 缺 `# Changelog` 標頭（fragment 模型下不再要求 `[Unreleased]`） | `policy-exempt:changelog-format` |
| R-05 | `VERSION` 存在 | 缺檔 | — |
| R-06 | `VERSION` 符合語意 | 不匹配 `<MAJOR>.<MINOR>.<PATCH>(-fix\.\d+)?` | — |
| R-07 | `VERSION` 與最新 tag 一致 | 不一致且無 `release:*` label | — |
| R-08 | `.paul-project.yml` 存在且完整 | 缺檔或缺 `policy_profile` / `policy_version` | — |
| R-09 | Code 變動必有 changelog fragment | code path 有變動但本 PR 未新增 `changelog.d/*.md` fragment | `skip-changelog` |
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
| R-22 | docs 對 code 產物引用無懸空 | canonical doc scope（`doc_paths`，預設 `README.md` / `docs/**`）引用的路徑／內部連結／反引號 symbol 在 repo 不存在；symbol 改用**語言無關 scoped identity**（ctags `(language, kind, scope, name)` 差集，限定式 token 精準命中、結構化裸名 snake/Camel 多 scope 同名只 WARN、純單字不偵測以避免常見字誤報）；本次變更新破壞 **FAIL**、陳年懸空 **WARN**、無 diff context（本地）降 WARN；`openspec/**`・`docs/superpowers/**`・fixtures 內建排除 | `policy-exempt:doc-reference` |
| R-23 | 引擎 pin 版本與 policy_version 對齊 | workflow `uses:` 指向 `conventions_engine.repo` 的引擎版本（tag `@vX.Y.Z` 或 SHA `@<sha>` + 尾註 `# vX.Y.Z`）與 `.paul-project.yml` 的 `policy_version` 不一致 **FAIL**；純 SHA 無註解 **WARN**；`./` 在地引用或未設 `conventions_engine.repo` 則 NA | `policy-exempt:engine-pin` |
| R-24 | MOC 與本次變更對齊 | repo 宣告 `moc` 時：`moc.triggers` 命中但 `moc.static` 未同步（**WARN**）／`moc.map` 連結懸空（本次新破壞 **FAIL**、陳年 **WARN**）／active openspec change・plan・spec 未被連結（**WARN**，永不 FAIL）；orphan/freshness 改呼叫共用核心，受治理前綴**參數化**（預設沿用既有前綴）；未宣告 `moc` 則 NA | `policy-exempt:moc-alignment` |
| R-25 | 文件覆蓋（omission gate，opt-in） | repo 宣告 `doc_coverage` 時：extractor 抽出的 public fact 未在任一 target doc 被精確 mention 則 **FAIL**（`mode: changed` 只查本次新增 fact、`mode: all` 查全部）；`mode: changed` 缺 base diff context 降 **WARN**；target 超出 `doc_paths`／不存在／extractor 設定無效 **FAIL**；未宣告 `doc_coverage` 則 NA | — |
| R-26 | 生成事實 marker 同步（opt-in） | repo 宣告 `generated_facts` 時：`generated-fact` marker 區塊內容與 command 正規化 stdout 不一致、marker 缺失、command 非 0 結束、或設定不完整則 **FAIL**；與 R-16 的 `cli-help` marker 並存不互相覆蓋；未宣告 `generated_facts` 則 NA | — |

**Exemption Labels 白名單**：上表所列 `policy-exempt:*` / `skip-changelog` / `wip` 即所有可用豁免 label；gate 只認這些，其他一律視同未豁免。

## Doc-alignment governance（三層）

文件陳舊分三層治理，只有 Tier 2 為確定性 gate：

- **Tier 1（預防）**：agent 改 code 時同步更新引用該產物的 docs（見四份 agent 慣例檔 checklist）。
- **Tier 2（確定性 gate）**：R-22 在 CI 偵測 `README.md` / `docs/**` 的結構化懸空引用——本次新破壞 FAIL、陳年 WARN。確定性層只看「結構性 rot」（引用死掉），不判斷語意。
- **Tier 3（語意複審）**：建議將 GitHub Copilot 設為 PR reviewer，複審「引用仍在但描述已過時」的語意陳舊（advisory，不擋 merge）。

### 獨立 doc-drift Action（OSS-ready，#25）

R-22/R-24 的 doc↔code 漂移核心抽成語言無關、零設定的共用核心（`policy_check/doc_drift/`，按
refs/paths/symbols/coverage/langs/provision primitive 組織），並包成可被**任意 repo** `uses:` 的
獨立 composite action（`.github/actions/doc-drift/`，詳見其 [README](.github/actions/doc-drift/README.md)）。
不要求目標 repo 採用 `.paul-project.yml`；symbol 抽取改用 universal-ctags 的 scoped identity
`(language, kind, scope, name)` 差集，支援 **Python / bash / C / C++**，消除原本 Python-only 與同名 fail-open 兩個限制。
Action 提供 `doc-drift` 與 `moc` 兩 mode，自理 base/head SHA 供給（shallow checkout 下不前置失敗），
FAIL 以非零 exit 擋 merge、WARN advisory。

> **與 lychee 的互補**：本 Action 只管 in-repo code 產物引用不懸空；外部 URL 活性／HTTP／anchor 交由 [lychee](https://github.com/lycheeverse/lychee-action)。

### 跨 repo 升版傳播（機制層，#23）

確定性的三層 doc-alignment 是 **intra-repo**；跨 repo 的 `policy_version` 漂移由本機制層治理（engine 只強制＋偵測＋文件，**不主動改下游**）：

- **強制（擋）**：org ruleset 的 `Policy Freshness` required workflow 跑 `python3 -m policy_check.drift check`，落後 canonical 的 repo PR 無法 merge。設定見 [`docs/org-ruleset-runbook.md`](docs/org-ruleset-runbook.md)。
- **偵測（點名）**：`python3 -m policy_check.drift report --org hamanpaul` 唯讀列出各 repo `policy_version` 與漂移狀態（`current` / `behind` / `ahead` / `unmanaged`）。
- **修復（升）**：落後 repo 由其自身 agent 依 [RELEASES.md](RELEASES.md) 的「升版傳播 SOP」自助升版。

> `policy_check.drift` 是 ops 工具，**非 R-xx gate 規則**，不進 `python3 -m policy_check --repo .` 的 FAIL 集合。

### 文件規則設定面（`doc_paths` / `doc_coverage` / `generated_facts`）

`.paul-project.yml` 提供三個文件治理設定面，皆向後相容（未宣告即維持既有行為）：

```yaml
# 1) canonical doc scope：R-18 / R-22 共用；未宣告時預設 README.md + docs/**
doc_paths:
  - "README.md"
  - "docs/**"
  - "CLAUDE.md"

# 2) doc_coverage（opt-in，R-25）：抓「新增了 X 卻沒記」的 omission drift
doc_coverage:
  mode: "changed"          # changed（只查本次新增 fact，預設）| all（查全部）
  targets: ["README.md"]   # 必須落在 doc_paths 內的 canonical docs
  sources:
    - kind: "modules"      # fact = repo-relative 路徑
      include: ["pkg/**/*.py"]
      exclude: ["**/__init__.py"]
    - kind: "rpc_methods"  # fact = pattern 的單一 capture group
      include: ["pkg/service.py"]
      pattern: 'method == "([^"]+)"'
    - kind: "env_vars"     # fact = PREFIX[A-Z0-9_]+ token
      include: ["pkg/**/*.py"]
      prefix: "APP_"
    - kind: "cli_tree"     # fact = command stdout 一行一個命令路徑
      command: "python3 scripts/list-cli-paths.py"

# 3) generated_facts（opt-in，R-26）：通用 marker-sync，把 R-16 的 cli-help 模式一般化
generated_facts:
  - kind: "fact_list"
    command: "python3 scripts/render-rpc-facts.py"
    reflected_in: "README.md"
    marker: "rpc-methods"
```

- **mention 判定**：R-25 採區分大小寫的精確 token/phrase 比對，子字串命中不算覆蓋（例如 `session.closed` 不滿足 `session.close`）。
- **changed 模式邊界**：缺 base diff context（如本地 `--repo .`）時降 WARN，不在無證據下 FAIL；`cli_tree` 無法快照 base，僅在 `mode: all` 受檢。
- **generated-fact marker 語法**：`<!-- BEGIN: generated-fact marker="<name>" -->` … `<!-- END: generated-fact marker="<name>" -->`；command 以 `shlex.split` 不經 shell 執行、`cwd=repo_root`、`LC_ALL=C`、固定 30 秒 timeout，只比對正規化 stdout。
- **安全注意（命令執行型規則）**：`R-16`（`cli`）、`R-25` 的 `cli_tree` extractor 與 `R-26`（`generated_facts`）會執行 `.paul-project.yml` 宣告的命令（無 shell injection，但命令字串本身受 config 控制並繼承完整環境）。因此**不應**在未信任的 PR／fork 分支上執行 `policy_check`；只在可信任的 repo config 上啟用。`cli_tree` 在 `mode: changed` 不會被執行（僅 `mode: all` 才跑）。

## CHANGELOG fragment 模型（並行安全）

為消除並行 agent 改共用 `CHANGELOG.md [Unreleased]` 的 merge conflict，待發布記錄改採
**每 PR 一個 fragment 檔**（changesets / towncrier 模式，但 agent 寫碎片、gate 驗碎片）：

- **每個 PR** 新增 `changelog.d/<issue>-<slug>.md`（不碰 `CHANGELOG.md`）：
  ```markdown
  ---
  type: feat        # 必填，conventional-commit type
  scope: changelog  # 選填
  issue: 24         # 選填
  ---
  一句話描述（成為 CHANGELOG 的一條 bullet）。
  ```
  不同 issue 天然不同檔、零共用行 → **並行 PR 永不衝突**。
- **type → Keep-a-Changelog 段** 固定映射：`feat`→Added、`fix`→Fixed、
  `refactor`/`perf`/`change`→Changed、`remove`→Removed、`deprecate`→Deprecated、`security`→Security。
  未知 type → collate 失敗。`docs`/`test`/`chore` 走 `skip-changelog`。
- **release 收斂**：升版時跑
  ```bash
  python3 -m policy_check.changelog collate --version X.Y.Z --date YYYY-MM-DD
  ```
  把 `changelog.d/*.md` 依 type 分組產出 `## [X.Y.Z] - <date>` 段（KaC 格式，R-04 仍過）並清空目錄。
- `R-09` 改驗「本 PR 有無 fragment」、`R-04` 不再要求 `[Unreleased]`。屬行為綁版本的 hard cutover
  （下游靠 pin 版本主動升級，未升級者用舊 `[Unreleased]` 行為）。

## Install

```bash
python3 -m pip install -e ".[test]"
```

### 離線 pip 安裝（給 GitLab gate / air-gapped runner）

若下游 CI 不走 GitHub reusable workflow，而是把引擎當成 wheel 發佈到 GitLab merge request pipeline，**必須**一併 vendor 引擎 wheel 與相依閉包；只做 `pip install --no-index <wheel>` 並不足夠，因為離線 runner 仍需要 `PyYAML` 等相依。

build-time（可連網）先做 wheel 與相依閉包：

```bash
python3 -m pip wheel --no-deps --wheel-dir dist .
mkdir -p vendor
python3 -m pip download --dest vendor dist/policy_check-1.0.10-py3-none-any.whl
```

gate-time 的 **Python 套件安裝** 可離線，只吃已 vendored 的檔案：

```bash
python3 -m pip install --no-index --find-links vendor policy-check==1.0.10
```

界線請分清楚：

- **build-time / 發行階段**：需要網路，負責 build wheel 並抓完整相依閉包。
- **gate-time / MR 檢查階段**：`policy-check` 與其 vendored Python 相依可離線安裝；但 `universal-ctags` 仍需預裝在 runner image，或透過公司內部 package mirror 提供。

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

#### GitHub reusable workflow

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
      policy_version: 1.0.10  # 範例；填你釘選 SHA 對應的實際版本
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

#### GitLab merge_request gate（pip mode）

下游 repo 的 `.paul-project.yml` 需顯式宣告 pip mode，讓 R-23 改驗「已安裝套件版號」與 `policy_version` lockstep；GitLab merge request pipeline 亦會自 `CI_MERGE_REQUEST_*` 載入 MR context，R-12 在 GitLab 路徑標示為 NA。

```yaml
# .paul-project.yml
policy_profile: flat
policy_version: 1.0.10
conventions_engine:
  mode: pip
```

GitLab CI job 可採最小 gate：

```yaml
policy-check:
  image: python:3.11
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  variables:
    GIT_DEPTH: "0"
  before_script:
    # 若 runner image 未預裝 universal-ctags，這一步仍需網路或公司內部 APT mirror
    - apt-get update && apt-get install -y universal-ctags
    # Python 套件安裝可離線，只吃 build-time 已 vendored 的 wheel 與相依
    - python3 -m pip install --no-index --find-links vendor policy-check==1.0.10
  script:
    - policy-check --repo .
```

此範例假設 runner 在 gate-time 已取得 build-time 產出的 `vendor/` 內容。若要讓 MR gate 不碰外部網路，請把 `universal-ctags` 預裝進 runner image；否則至少需接公司內部 APT / package mirror。換言之，這裡的離線保證只涵蓋 **Python wheel / vendored 相依安裝** 這一段。**Artifactory / 內部 PyPI / GitLab Package Registry** 哪一條作為正式發行管道，仍屬需由公司決定的 follow-up。

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
- **PATCH**: 累積已完成的 feature batch 計數（完整規則清單見 `RELEASES.md` / `CHANGELOG.md`）
- **-fix.N**: 落地後 bug fix（非新 feature、非穩定、非 release）

當前版本（權威值見 `VERSION`）：

<!-- BEGIN: generated-fact marker="repo-version" -->
1.0.10
<!-- END: generated-fact marker="repo-version" -->

## 相關專案

- [`hamanpaul/.github`](https://github.com/hamanpaul/.github)：GitHub 社群預設（PR template / Issue template / SECURITY / CONTRIBUTING）
- [`hamanpaul/new-project-template`](https://github.com/hamanpaul/new-project-template)：新專案骨架（供 `gh repo create --template` 使用）

## License

See [`LICENSE`](./LICENSE) if present, otherwise defaults to repository owner's preference.
