# Org Ruleset Runbook — 跨 repo policy 強制（#23）

> 本文件操作需 `admin:org` 權限，**不在 repo CI 內自動套用**；engine 只交付步驟與範例。
> 相關設計：[`docs/superpowers/specs/2026-06-25-cross-repo-drift-governance-design.md`](superpowers/specs/2026-06-25-cross-repo-drift-governance-design.md)。

## 目的

org 層 require 兩條 status check 才能 merge，涵蓋既有 repo、下游無法靜默停用：

- `Policy Check`：per-repo 自洽（R-14 / R-20 / R-23…，既有）。
- `Policy Freshness`：跑 `python3 -m policy_check.drift check`，擋下「落後但自洽」的 repo（本案新增）。

> 為什麼需要第二條：被釘住的舊引擎無法強制「自己已過期」（它本身就是過期的東西）。
> 唯有 org 層集中、引用 canonical **最新**版的 workflow 才能可靠強制 freshness。

## 前置

- `gh auth status` 為 org admin 帳號，且 token 具 `admin:org`。

## Step 1 — 建 org ruleset

UI：Org → Settings → Rules → Rulesets → New ruleset。target 全 org（或選定 repo），啟用：

- Require a pull request before merging。
- Block direct pushes to `main`（restrict deletions / require PR）。
- Require status checks：`Policy Check`、`Policy Freshness`。

或 `gh api`（示意 payload，實際結構以 GitHub REST「org rulesets」文件為準）：

```bash
gh api -X POST /orgs/hamanpaul/rulesets \
  -f name='policy-enforcement' \
  -f target='branch' \
  -f enforcement='active' \
  -f 'conditions[ref_name][include][]=~DEFAULT_BRANCH' \
  -f 'rules[][type]=pull_request' \
  -f 'rules[][type]=required_status_checks' \
  -f 'rules[][parameters][required_status_checks][][context]=Policy Check' \
  -f 'rules[][parameters][required_status_checks][][context]=Policy Freshness'
```

設定後可 `gh api /orgs/hamanpaul/rulesets` 匯出佐證。

## Step 2 — org-level required workflow（Policy Freshness）

以 org required workflow / default setup 推下列 `policy-freshness.yml`，不靠各 repo 自行 `include`。
它 checkout canonical **最新**版（`ref: main`，org 控制、非各 repo 自釘）跑 `drift check`：

```yaml
name: Policy Freshness
on:
  pull_request:
jobs:
  freshness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4               # 下游 repo（含其 .paul-project.yml）
      - uses: actions/checkout@v4               # canonical engine（最新）
        with:
          repository: hamanpaul/paulsha-conventions
          ref: main
          path: .engine
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ./.engine
      - run: python3 -m policy_check.drift check --repo .
        env:
          GH_TOKEN: ${{ github.token }}
```

> `drift check` 讀下游 repo 的 `.paul-project.yml` 對 live canonical 最高 tag 比對；
> `behind` → exit≠0 → required check 失敗。非政策管轄（無 `.paul-project.yml`）的 repo 判 `unmanaged`、exit 0，不誤傷。

## Step 3 — 驗證（下游落後實驗）

1. 在一個 `policy_version` 落後 canonical 的下游 repo 開 PR（例：`drift report` 點名的 `behind` repo）。
2. `Policy Freshness` 跑 `drift check` → 判 `behind` → exit≠0 → required check 失敗 → **merge 被擋**。
3. 把該 repo 依 [RELEASES.md](../RELEASES.md) 的「升版傳播 SOP」帶到 canonical 後重跑 → 通過。
4. 佐證：PR checks 截圖 或 `gh api /orgs/hamanpaul/rulesets`。

## 與既有機制並存

org freshness gate 與 `reusable-policy-check.yml` 的 R-15 / R-23 dual-pin 並存、職責不同：

| 檢查 | 由誰控制 | 比對對象 | 答的問題 |
|---|---|---|---|
| per-repo Policy Check | 各 repo 自釘版本 | 該 repo 自身 | 在它釘的版本下自洽嗎 |
| org Policy Freshness | org admin 集中、引用 canonical 最新 | repo 版本 vs live canonical | 你釘的版本還是不是最新 |

不重複造、不衝突。

## Non-goals

- 不改規則引擎邏輯。
- GitLab 發行另見 #20。
