# paulsha-conventions — MOC（Map of Content）

專案層地圖：連結 canonical capabilities、active/archived OpenSpec changes 與
superpowers plans/specs，並標其 stage 狀態。
本 repo 以 `moc.map: docs/MOC.md` 宣告，由 R-24（moc-alignment）盯其與本次變更同步。

## Active openspec changes

目前無 active change。

## Canonical capabilities / archived changes

- [runtime bundle specification](../openspec/specs/runtime-bundle/spec.md) — v1.0.14 正式 bundle、offline lifecycle 與 fleet rollout 已完成；斷電級 hardening 見 #52
- [project-policy manifest specification](../openspec/specs/project-policy-manifest/spec.md) — canonical manifest 與 10-repo migration 已完成

（已落地者見 `openspec/changes/archive/`。[#48 versioned runtime bundle](../openspec/changes/archive/2026-07-26-2026-07-26-versioned-runtime-bundle/proposal.md) 已 archive，canonical specs 見 `openspec/specs/runtime-bundle/` 與 `openspec/specs/project-policy-manifest/`。[#46 canonical local preflight](../openspec/changes/archive/2026-07-26-canonical-local-preflight/proposal.md) 已 archive，canonical spec 見 `openspec/specs/preflight/`。[#45 R-21 visibility coupling](../openspec/changes/archive/2026-07-26-r21-visibility-coupling/proposal.md) 已 archive，canonical spec 見 `openspec/specs/secret-scan/`。[#30 提案 A auto-build-block](../openspec/changes/archive/2026-07-02-auto-build-block/proposal.md) 已於本批落地並 archive，canonical spec 見 `openspec/specs/auto-build-config/`。[#20 gitlab-internalization](../openspec/changes/archive/2026-07-01-gitlab-internalization/proposal.md) 已於本批落地並 archive，canonical spec 見 `openspec/specs/gitlab-ci-gate/`。#25 doc-drift-action 已於本批落地並 archive，canonical specs 見 `openspec/specs/doc-drift-core/`・`openspec/specs/doc-drift-action/`（`doc-reference`／`moc-alignment` 規格亦同步更新）。#23 cross-repo-drift-governance 已於本批落地並 archive，canonical spec 見 `openspec/specs/cross-repo-drift-governance/`。Runbook：[`docs/org-ruleset-runbook.md`](org-ruleset-runbook.md)。）

## Plans（docs/superpowers/plans）
- [arc-conventions portability 階段一（#63）](superpowers/plans/2026-08-10-arc-conventions-portability.md) — 已實作；5 個 task，去硬編碼 + distribution identity，版號與 GitLab provider 明確排除在外
- [versioned runtime bundle（#48）](superpowers/plans/2026-07-26-issue-48-runtime-bundle.md) — 歷史 implementation plan；v1.0.14 與 fleet rollout 已落地
- [smoke fixture R-21 誤中 + preflight 摘要改善（#77）](superpowers/plans/2026-08-11-issue-77-smoke-fixture-r21.md) — 派工中；fixture 自我豁免 + 失敗行優先摘要
- [install root 跟隨 distribution_name（#74 之 3）](superpowers/plans/2026-08-11-issue-74-install-root-distribution-name.md) — 派工中；安裝期以 manifest 推導根目錄，覆寫語意不變
- [引擎版本 vs policy_version 啟動比對（#61）](superpowers/plans/2026-08-10-issue-61-engine-version-gate.md) — 派工中；啟動 fail-loud + 報告表頭引擎版本
- [R-19 結構化偵測實際測試執行（#62）](superpowers/plans/2026-08-10-issue-62-r19-real-test-execution.md) — 已完成；YAML 結構化偵測 + canonical tests.yml 骨架 + 反例 fixtures，分階段上線
- [activation 斷電級 crash recovery（#52）](superpowers/plans/2026-08-10-issue-52-activation-crash-recovery.md) — 派工中；journal + SIGKILL fault injection + 重啟自動收斂
- [ISO/IEC 42001 opt-in profile 設計（#60）](superpowers/plans/2026-08-10-issue-60-iso42001-profile-design.md) — 設計文件已交付（[design](superpowers/specs/2026-08-10-iso42001-profile-design.md)），schema 落地與規則實作另開 scoped issue
- [runtime bundle runbook](runtime-bundle-runbook.md) — build/install/exact selection/rollback 與 #39 authority 邊界
- [內部發行管道決策（#39）](superpowers/plans/2026-07-26-issue-39-internal-release-channel.md) — needs_human（待公司選定 package authority）
- [#46 Opus 5 對抗審查修復](superpowers/plans/2026-07-26-issue-46-opus5-review-repair.md) — 第三輪 `PASS / NONE`，主整合驗收通過
- [release ledger tag SHA（#42）](superpowers/plans/2026-07-26-issue-42-release-ledger-tag-sha.md) — 已實作、對抗審查通過並整合
- [R-21 visibility coupling（#45）](superpowers/plans/2026-07-26-issue-45-r21-visibility-coupling.md) — 已實作、對抗審查通過並 archive
- [canonical local preflight（#46）](superpowers/plans/2026-07-26-issue-46-local-preflight.md) — 已實作並 archive，Opus 5 第三輪覆審通過
- [preflight-ci ownership migration summary](migrations/preflight-ci/merge-summary.md) — governed 遷移中
- [preflight-ci ownership migration risks](migrations/preflight-ci/merge-risks.md) — rollback 與殘餘風險
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
- [ISO/IEC 42001 opt-in profile design（#60）](superpowers/specs/2026-08-10-iso42001-profile-design.md) — 設計交付；opt-in 機制、證據對映表、新規則規劃（ISO-NN）、Stage 2/3 follow-up issue 草稿
- [arc-conventions portability design（#63）](superpowers/specs/2026-08-10-arc-conventions-portability-design.md) — 已實作；階段一去硬編碼 + distribution identity 信任模型，階段二 rule plugin 介面僅列草案
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
