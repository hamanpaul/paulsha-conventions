## Context

完整設計見 `docs/superpowers/specs/2026-06-25-cross-repo-drift-governance-design.md`（含元件邊界表、報表輸出範例、驗收對照）。本文件僅收斂關鍵技術決策。

下游 repo 落後 canonical `policy_version` 目前無任何 gate 偵測（R-14/R-20/R-23 只驗單 repo 自洽）。本案在 engine 側補上偵測 + 強制路徑，但不讓 engine 主動 mutate 下游。

## Goals / Non-Goals

**Goals:**
- 提供唯讀的跨 repo 漂移報表（operator 儀表板）。
- 提供可 gate 的 freshness 檢查，讓「落後但自洽」的下游 repo **無法 merge**。
- 版本比較涵蓋 `-fix.N` hotfix 級漂移。

**Non-Goals:**
- engine 不主動改下游內容（不 clone／改檔／替下游開 PR）。
- 不新增 R-xx 規則（理由見 Decision 1）。
- 不處理 org ruleset 的實際套用（屬 org 設定、需 `admin:org`，由使用者執行；engine 只交付 runbook + 範例 workflow）。
- GitLab 發行另見 #20。

## Decisions

### Decision 1 — 強制住在 org-level required workflow，不做成 R-xx 規則
**選擇**：跨 repo freshness 強制由 org 集中控制的 required workflow（跑 `drift check`）負責，而非 `python3 -m policy_check --repo .` 內的新規則。

**理由（bootstrapping 矛盾）**：R-xx 規則由**被釘住的引擎**執行。落後的 repo 釘的是落後的 engine，那份 engine 裡沒有新檢查——引擎無法強制「你已過期」，因為它本身就是過期的東西。唯有 org 層集中、引用 canonical 最新版的 workflow 才能可靠強制，且下游無法釘舊／靜默停用。

**替代方案**：新增 R-25 規則跑在 per-repo Policy Check 內——否決，因為落後 repo 跑舊引擎不會有 R-25。

### Decision 2 — drift 工具雙模式（report exit 0 / check exit≠0）
**選擇**：同一支 `policy_check/drift.py`，`report` 子命令唯讀印表永遠 exit 0；`check` 子命令比當前 repo vs live canonical，`behind` → exit≠0。

**理由**：report 是 operator 儀表板（不該因漂移而 fail 中斷腳本）；check 是 gate（必須以 exit code 表態）。純比對邏輯共用、可單測；gh 取資只在邊緣。

**替代方案**：兩支獨立 script——否決，重複比對邏輯、難一致測試。

### Decision 3 — 版本比較完整 `-fix.N` 排序
**選擇**：`parse_version` 解析 `MAJOR.MINOR.PATCH[-fix.N]` 為 `(major, minor, patch, fix)`，**無尾註 → fix=0**，故 `1.0.7` < `1.0.7-fix.1` < `1.0.7-fix.2`。

**理由**：policy 版本文法允許 `-fix.N`；摺疊尾段會讓 `1.0.7-fix.2` vs `1.0.7` 誤判 current，漏掉 hotfix 級漂移——正是本案要抓的。

### Decision 4 — canonical 真相來源 = 最新 release tag
**選擇**：`canonical_version_live` 取 `hamanpaul/paulsha-conventions` 最新 `vX.Y.Z` release tag。

**理由**：與 `RELEASES.md` tag-driven 譜系一致（自 1.0.2 起 merge → 打 tag）；單一、live、不依賴各 repo 自釘值。

## Risks / Trade-offs

- [org workflow 需網路取 canonical 版本] → 僅在 CI gate 邊緣呼叫 `gh`；純比對邏輯離線可單測，整合層由 runbook Step 3 實驗佐證。
- [org ruleset 套用不在 repo 內、無法被本 repo CI 驗證] → runbook 明列 `gh api` 佐證與「下游落後實驗」作為人工驗收；engine 只保證交付物正確。
- [`unmanaged` repo（無 `.paul-project.yml`）] → 視為非政策管轄，report 標 `unmanaged`、check 不擋（exit 0），避免誤傷非受管 repo。

## Migration Plan

1. 落地 repo 側交付（drift 工具 + runbook + SOP + 測試），feature 先進 `[Unreleased]`。
2. 使用者以 `admin:org` 依 runbook 套用 org ruleset + `Policy Freshness` required workflow。
3. 跑「下游落後實驗」驗證 gate 真能擋。
4. 回滾：移除 org ruleset 即恢復現狀；repo 側工具為唯讀／可選，無破壞性。

## Open Questions

- 無。org-level required workflow 的 default-setup 推送細節於 runbook Step 2 文件化，由使用者依 org 方案決定全 org 或逐 repo target。
