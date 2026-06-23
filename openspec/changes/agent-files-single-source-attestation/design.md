## Context

本 repo 是 agent-first policy-as-code 引擎。四份 agent 慣例檔目前為 byte-identical 實體複本（須手動同步、R-14 僅事後驗版本）；版號鏈（R-14/R-20/R-15）只驗 intra-repo 自洽，未綁到 repo 實際 pin 的引擎版本，是 P0 跨 repo 漂移成因。完整背景與行內證據見 `docs/superpowers/specs/2026-06-23-agent-files-single-source-and-version-attestation-design.md`。

## Goals / Non-Goals

**Goals:**
- `CLAUDE.md` 立為唯一 canonical，其餘三檔 symlink；「只維護一份」。
- 把「單一真檔」由慣例升級為 enforce（config-gated，漸進不打斷下游）。
- 補 attestation gate：repo pin 的引擎版本 ⟷ `policy_version` 對齊，閉合版號鏈。

**Non-Goals:**
- cross-repo currency 硬 gate（per-repo 版本 vs canonical 最新版）→ org 層／報表，另案。
- MOC／專案層 stage 地圖治理 → 另案（memory `moc-cross-stage-governance`）。
- 業界方法全面抽換稽核 → 另案。

## Decisions

**D1 — canonical = `CLAUDE.md`（非 `AGENTS.md`）。** 本 repo 主 agent 為 Claude Code，原生讀 `CLAUDE.md`、至今不讀 `AGENTS.md`（anthropics/claude-code#34235）。*替代*：以 AGENTS.md 為 canonical（AAIF 業界介面標準）——本 repo 否決；symlink 仍讓讀 AGENTS.md 的工具 resolve 到同一份。

**D2 — R-14 config-gated，預設 `copy`。** R-14 為共用引擎規則，下游也跑；寫死 symlink-required 會在下游 bump 時 flag-day。*替代*：寫死 symlink——否決（破壞 fleet、違背漸進強制）。

**D3 — R-23 為獨立新 rule（非擴充 R-15/R-20）。** attestation 與「pin 是否存在」「workflow policy_version 字面值」是不同關注點，需獨立 exemption 與 WARN 語意。*替代*：擴充 R-20——否決以免混兩種解析；過細時可再併。

**D4 — SHA pin + `# vX.Y.Z` 尾註為 attestation 橋樑；純 SHA → WARN。** SHA pin（資安、L0）離線無法反推版本；尾註讓 SHA pin 仍可 FAIL-grade 對齊（與 dependabot 慣例一致）。*替代*：SHA→version 查表（網路／lockfile）——出範圍，歸 cross-repo currency 另案。

**D5 — R-14 維持不可豁免（`exempt_label = None`）。** 單一真檔／版本為真相，不應可繞過；平台 symlink 支援列為 adoption 前提，CI 為 Linux（symlink 正常）。

## Risks / Trade-offs

- **純 SHA pin 下游 attestation 僅 advisory** → 落地後推「pin 行帶 `# vX.Y.Z`」慣例；查表方案歸另案。
- **無 symlink 支援平台 clone 退化為文字檔**（`tier: shareable`）→ README/spec 註記；主環境 WSL/ext4，下游消費引擎而非這幾份檔；不建生成器。
- **新增 R-23 之目錄 churn**（白名單／README rule 目錄／presence 測試手動同步）→ tasks 涵蓋；正凸顯 MOC/self-index 缺口（另案）。

## Migration Plan

- 預設 `copy` → 下游 bump 引擎後行為不變，各自排程遷移；本 repo `.paul-project.yml` 設 `agent_files.mode: symlink`。
- **Rollback**：將三 symlink 還原為複本並把 `mode` 設回 `copy`／移除即可，無資料遷移。
- **Release**：merge 當下 bump `1.0.5 → 1.0.6`（`VERSION` / `policy_version` / `CLAUDE.md` 含 `managed-by@v1.0.6` / workflow `policy_version` 字面值 / tag / `RELEASES.md`）。

## Open Questions

- 是否日後為純 SHA pin 引入 SHA→version lockfile（暫緩，歸 cross-repo currency 另案）。
- `new-project-template` 是否預先 ship `agent_files.mode: symlink` 與 `conventions_engine.repo`（獨立變更，本案非目標）。
