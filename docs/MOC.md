# paulsha-conventions — MOC（Map of Content）

專案層地圖：連結 active openspec changes 與 superpowers plans/specs，並標其 stage 狀態。
本 repo 以 `moc.map: docs/MOC.md` 宣告，由 R-24（moc-alignment）盯其與本次變更同步。

## Active openspec changes
（目前無 active change。）

（已落地者見 `openspec/changes/archive/`。[#30 提案 A auto-build-block](../openspec/changes/archive/2026-07-02-auto-build-block/proposal.md) 已於本批落地並 archive，canonical spec 見 `openspec/specs/auto-build-config/`。[#20 gitlab-internalization](../openspec/changes/archive/2026-07-01-gitlab-internalization/proposal.md) 已於本批落地並 archive，canonical spec 見 `openspec/specs/gitlab-ci-gate/`。#25 doc-drift-action 已於本批落地並 archive，canonical specs 見 `openspec/specs/doc-drift-core/`・`openspec/specs/doc-drift-action/`（`doc-reference`／`moc-alignment` 規格亦同步更新）。#23 cross-repo-drift-governance 已於本批落地並 archive，canonical spec 見 `openspec/specs/cross-repo-drift-governance/`。Runbook：[`docs/org-ruleset-runbook.md`](org-ruleset-runbook.md)。）

## Plans（docs/superpowers/plans）
- [內部發行管道決策（#39）](superpowers/plans/2026-07-26-issue-39-internal-release-channel.md) — needs_human（待公司選定 package authority）
- [release ledger tag SHA（#42）](superpowers/plans/2026-07-26-issue-42-release-ledger-tag-sha.md) — 實作中
- [R-21 visibility coupling（#45）](superpowers/plans/2026-07-26-issue-45-r21-visibility-coupling.md) — 實作中
- [canonical local preflight（#46）](superpowers/plans/2026-07-26-issue-46-local-preflight.md) — 待 #45 整合後實作
- [auto-build-block（#30 提案 A）](superpowers/plans/2026-07-02-auto-build-block.md) — 已完成（#30 提案 A，change 已 archive）
- [gitlab-internalization（#20）](superpowers/plans/2026-07-01-gitlab-internalization.md) — 已完成（#20，change 已 archive）
- [rule families + 版號 generated-fact（無 issue）](superpowers/plans/2026-07-01-rule-families-and-version-fact.md) — 已完成（change 已 archive）
- [doc-drift 獨立 Action（#25）](superpowers/plans/2026-06-30-doc-drift-action.md) — 已落地（#25，change 已 archive）
- [changelog-fragments（#24）](superpowers/plans/2026-06-30-changelog-fragments.md) — 已完成（#24，已 archive）
- [doc-rule-hardening（#26）](superpowers/plans/2026-06-30-doc-rule-hardening.md) — 已完成（#26，已 archive）
- [cross-repo-drift-governance](superpowers/plans/2026-06-25-cross-repo-drift-governance.md) — 已完成（#23，已 archive）
- [moc-alignment-rule](superpowers/plans/2026-06-23-moc-alignment-rule.md) — 已完成（v1.0.7）
- [agent-files single-source + attestation](superpowers/plans/2026-06-23-agent-files-single-source-and-version-attestation.md) — 已完成（v1.0.6）
- [r22 doc-alignment governance](superpowers/plans/2026-06-18-r22-doc-alignment-governance.md) — 已完成（v1.0.5）
- [r21 secret-scan](superpowers/plans/2026-06-14-r21-secret-scan.md) — 已完成（v1.0.3/1.0.4）
- [three-repo rollout](superpowers/plans/2026-04-23-three-repo-rollout.md) — 已完成
- [rollout github defaults + new-project-template](superpowers/plans/2026-04-23-rollout-github-defaults-and-new-project-template.md) — 已完成

## Specs / designs（docs/superpowers/specs）
- [auto-build-block design（#30 提案 A）](superpowers/specs/2026-07-02-auto-build-block-design.md) — 已完成（#30 提案 A，change 已 archive；canonical spec 見 `openspec/specs/auto-build-config/`）
- [gitlab-internalization design（#20）](superpowers/specs/2026-07-01-gitlab-internalization-design.md) — 已完成（#20，change 已 archive；canonical spec 見 `openspec/specs/gitlab-ci-gate/`）
- [rule families + 版號 generated-fact design（無 issue）](superpowers/specs/2026-07-01-rule-families-and-version-fact-design.md) — 已完成（change 已 archive）
- [doc-drift 獨立 Action design（#25）](superpowers/specs/2026-06-30-doc-drift-action-design.md) — 已落地（#25，change 已 archive）
- [changelog-fragments design（#24）](superpowers/specs/2026-06-30-changelog-fragments-design.md) — 已完成（#24，已 archive）
- [doc-rule-hardening design（#26）](superpowers/specs/2026-06-30-doc-rule-hardening-design.md) — 已完成（#26，已 archive）
- [cross-repo-drift-governance design](superpowers/specs/2026-06-25-cross-repo-drift-governance-design.md) — 已完成（#23，已 archive）
- [moc-alignment-rule design](superpowers/specs/2026-06-23-moc-alignment-rule-design.md) — 已完成（v1.0.7）
- [agent-files single-source + attestation design](superpowers/specs/2026-06-23-agent-files-single-source-and-version-attestation-design.md) — 已完成
- [r22 doc-alignment governance design](superpowers/specs/2026-06-18-r22-doc-alignment-governance-design.md) — 已完成
- [issue/docs/language policy rules design](superpowers/specs/2026-06-08-issue-docs-language-policy-rules-design.md) — 已完成
- [three-repo rollout design](superpowers/specs/2026-04-23-three-repo-rollout-design.md) — 已完成
