# preflight Specification

## Purpose
定義本地 CI-parity preflight 的 PR context、typed repo-owned gates、pinned
engine resolution、offline fail-closed 與整體 verdict 契約。
## Requirements
### Requirement: canonical local preflight CLI
引擎 SHALL 提供 `policy-preflight` 與 `python3 -m policy_check.preflight`
兩個等價入口，支援 `--repo`、`--pr`、`--pr-title`、`--pr-body-file`、
`--pr-labels`、`--base`、`--head`、`--repo-visibility`、`--skip-tests`、
`--policy-only`、`--offline` 與 `--cache-dir`。

#### Scenario: GitHub PR context 由 gh 取得
- **WHEN** 使用者傳入 `--pr <number-or-url>`
- **THEN** preflight 以 `gh pr view` 取得 title、body、labels、base 與 head，並取得 repository visibility

#### Scenario: PR mode 不混用手動 authority
- **WHEN** `--pr` 與任一手動 PR context 參數同時出現
- **THEN** preflight 回傳 exit 2，不猜測 precedence

#### Scenario: offline 與 PR lookup 互斥
- **WHEN** `--offline` 與 `--pr` 同時出現
- **THEN** argument parser 回傳 exit 2，且不呼叫 `gh`

#### Scenario: 手動模式要求完整文字 context
- **WHEN** 未提供 `--pr`，且缺少 `--pr-title` 或 `--pr-body-file`
- **THEN** preflight 回傳 exit 2，且不得輸出 `PREFLIGHT PASS`

#### Scenario: labels 可明確為空
- **WHEN** 手動模式傳入空的 `--pr-labels`
- **THEN** effective labels 為空陣列，不視為 context 缺失

#### Scenario: base 與 head 安全推導
- **WHEN** 手動模式未提供 base 或 head
- **THEN** preflight 只從本地 git symbolic refs 推導；無法安全推導時 exit 2

#### Scenario: checkout 與 PR context 一致
- **WHEN** effective head 不等於目前 checkout branch，或 `origin/<base>` 不存在／無法建立 merge base
- **THEN** preflight 回傳 exit 2，不以空 changed-files context 繼續

### Requirement: repo-owned preflight steps 必須 typed 且可驗證
`.paul-project.yml` SHALL 支援 optional `preflight.steps`。每一步 MUST 是
mapping，包含唯一非空 `name`、`kind: validation|tests` 與非空
`argv: list[str]`；optional `cwd` 與 `when_path_exists` MUST 為不可逃出 repo
的相對路徑；optional `timeout_seconds` MUST 為正整數，未設時使用有界預設。
已知欄位型別錯誤 MUST 由 R-08 FAIL；未知 subkey SHALL 保持 lenient。

#### Scenario: argv 不經 shell
- **WHEN** preflight 執行 repo-owned step
- **THEN** 它以 typed argv 直接 spawn subprocess，MUST NOT 使用 shell string

#### Scenario: 路徑逃逸被拒絕
- **WHEN** `cwd` 或 `when_path_exists` 為 absolute path、含 `..`，或 symlink resolve 到 repo 外
- **THEN** config/runtime validation 拒絕該 step

#### Scenario: skip-tests 只跳測試
- **WHEN** 使用者傳入 `--skip-tests`
- **THEN** `kind: tests` 回報 SKIP，`kind: validation` 仍執行

#### Scenario: policy-only 跳過所有 repo-owned steps
- **WHEN** 使用者傳入 `--policy-only`
- **THEN** 所有 repo-owned steps 回報 SKIP，但 engine resolution 與 policy gate 仍執行

#### Scenario: when-path 不存在時跳過
- **WHEN** step 宣告的 `when_path_exists` 在 repo 內不存在
- **THEN** 該 step 回報 SKIP 而非 FAIL

### Requirement: policy gate 必須使用已驗證的 engine identity
preflight MUST 先解析 engine authority，再以該 engine 的獨立 subprocess 執行
policy gate，並傳入完整 title、body、labels、base、head 與 visibility context。

對 engine repo self-dogfood，MUST 核對 checkout 的 `VERSION` 與
`.paul-project.yml.policy_version`。對 `conventions_engine.mode: pip`，
MUST 核對 installed distribution version。對 workflow/source mode，MUST 從
`.github/workflows/policy-check.yml` 取得 remote reusable workflow 的完整 SHA 與
`policy_engine_ref`，兩者 MUST 相同，且 configured engine repo MUST 一致。

#### Scenario: workflow dual pin 不一致
- **WHEN** reusable workflow `uses` SHA 與 `policy_engine_ref` 不一致
- **THEN** engine gate FAIL，且不得 fallback 到 default branch 或其他版本

#### Scenario: installed version skew
- **WHEN** pip mode 的 installed `policy-check` version 與 policy_version 不同
- **THEN** engine gate FAIL

#### Scenario: self-dogfood version skew
- **WHEN** engine repo checkout 的 `VERSION` 與 project config 不同
- **THEN** engine gate FAIL

### Requirement: exact-SHA cache 與 offline resolution 必須 fail-closed
source cache MUST 以 `engine repo + full SHA` 為 immutable key，並包含帶 digest
的 manifest。Cache hit MUST 驗證 manifest identity/digest、checkout HEAD、tree
與 clean worktree（包含 ignored/untracked artifact）。Online 缺 cache時 MAY
fetch exact SHA；MUST NOT fallback。

`--offline` MUST 禁止 `gh`、`git fetch`、`git clone` 或其他 network resolver；
只接受 matching installed distribution、self engine，或驗證通過的 exact-SHA
cache。缺 artifact 時 MUST 明示 repo/SHA/version 並 exit 1。

#### Scenario: verified cache offline 通過
- **WHEN** offline cache 的 manifest digest、repo、SHA、tree、HEAD 與 clean status 全部一致
- **THEN** resolver 使用該 cache，且不執行 network-capable command

#### Scenario: dirty 或遭竄改的 cache 被拒絕
- **WHEN** cache checkout dirty，或 manifest digest/HEAD/tree 任一不一致
- **THEN** resolver 不將它視為 cache hit

#### Scenario: offline artifact 缺失
- **WHEN** offline 模式沒有 matching installed distribution 或 verified cache
- **THEN** engine gate FAIL（exit 1），訊息列出缺少的 repo、SHA 與 version

#### Scenario: online 只 fetch exact SHA
- **WHEN** online mode 需要建立 cache
- **THEN** resolver 只 fetch requested full SHA 並 detached checkout 該 SHA，不 checkout default branch

### Requirement: preflight verdict 與輸出不得誤導或洩密
每個 selected gate SHALL 輸出 `PASS|FAIL|SKIP`、duration（執行 gate）與 effective
engine identity；輸出 MUST NOT 包含 token、完整 GitHub metadata、matched secret
或 repo-owned command 的原始 stdout/stderr。只有 engine、policy 與所有 selected
repo-owned steps 全部通過時，最後一行才 SHALL 為 `PREFLIGHT PASS`。

#### Scenario: 任一 gate failure
- **WHEN** policy、validation 或 tests 任一 selected gate 非零或 timeout
- **THEN** 最終 exit 1、輸出 `PREFLIGHT FAIL`，且不得輸出 `PREFLIGHT PASS`

#### Scenario: config 或 context error
- **WHEN** CLI/context/config contract 不合法
- **THEN** preflight exit 2

#### Scenario: 全部 selected gates 通過
- **WHEN** engine、policy 與所有 selected steps 都通過
- **THEN** preflight exit 0，最後一行輸出 `PREFLIGHT PASS`

#### Scenario: offline 保證邊界明示
- **WHEN** 使用 `--offline`
- **THEN** 輸出明示 offline 只約束 resolver；repo-owned commands 仍由 repo authority 負責

### Requirement: preflight-ci skill authority belongs to paulsha-conventions
The repository MUST contain and deploy the canonical `preflight-ci` agent
skill. The skill wrapper MUST delegate to the adjacent
`policy_check.preflight` implementation and MUST NOT parse a GitHub Actions
workflow, clone/fetch an engine, or duplicate policy/OpenSpec/test
orchestration.

#### Scenario: installed skill resolves one canonical authority
- **WHEN** the user installs `preflight-ci` from a conventions checkout
- **THEN** `~/.agents/skills/preflight-ci` resolves to this repository's skill
  directory and no copy from another skill store is required

#### Scenario: skill execution does not require Actions resolution
- **WHEN** the skill runs against a target repository
- **THEN** it supplies its adjacent verified source engine directly, without
  reading or executing `.github/workflows/policy-check.yml`

### Requirement: skill source engine must fail closed
The source checkout supplied by the skill MUST have the canonical repository
origin, a clean worktree, a full HEAD SHA, and a `VERSION` matching the target
repo's `policy_version`. Any mismatch MUST fail the engine gate without
falling back to a workflow/default branch/other installed version.

#### Scenario: source version skew
- **WHEN** the deployed skill checkout VERSION differs from target policy_version
- **THEN** preflight exits nonzero before running policy or repo-owned steps

### Requirement: full skill mode requires repo-owned gates
When invoked through the canonical skill, full preflight MUST require an
explicit `.paul-project.yml.preflight` declaration. Absence MUST return exit 2
unless the caller explicitly requests `--policy-only`.

#### Scenario: missing target gate declaration
- **WHEN** a target repo has no `preflight` block and the skill runs without
  `--policy-only`
- **THEN** preflight rejects the incomplete local gate instead of printing
  `PREFLIGHT PASS`
