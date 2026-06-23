## Context

brainstorm / openspec 為單一 feature 視角，缺專案層全貌；大型重構的 stage 被 postpone 後跨 session 流失，靜態操作脈絡（platform / vendor / toolchain / build / install / profiles）改了也可能漏更新文件。模型分界（探索結論）：**內容跟著專案走（留各自 repo，內部 GitLab，tier 私有）；paulsha 只提供盯它的規則。** MOC 兩態：靜態脈絡（yaml / CLAUDE.md 段）＋ 動態地圖（link 到 `docs/superpowers/{specs,plans}` 與 `openspec/changes/*` 並標 stage 狀態）。

## Goals / Non-Goals

**Goals:**
- 通用、platform-agnostic 的 R-24，盯 repo 宣告的 MOC 與本次變更同步。
- 對上引擎現有 pattern：靜態鮮度≈R-18、連結懸空≈R-22、孤兒≈新增。
- opt-in（`moc` 未宣告 → NA）。

**Non-Goals:**
- MOC 狀態語意對齊（stage 宣稱 done 是否真 done）→ L2 advisory（Copilot），不入確定性規則。
- 引擎內部化 / GitLab 發行（issue #20）→ 本案不依賴；規則邏輯不碰平台。
- 規範 MOC 檔的內部格式 schema（platform/vendor 欄位）→ 那是專案自己的事，引擎不管內容。

## Decisions

**D1 — 單一規則 R-24，三瓣（非拆多 rule）。** 比照 R-22（一 rule、prong P/S）；MOC 相關檢查共用一個 ID 與一個豁免 label。

**D2 — platform-agnostic，純 git-level。** 只用 `ctx.changed_files` + `ctx.repo_root` + repo 內檔案，不讀 GitHub/GitLab 任何 env。與 issue #20（GitLab 發行）解耦——本規則現在就能做，#20 落地後自動在 GitLab 生效。

**D3 — 嚴重度：只有「確定性破壞」硬 FAIL。**
- 靜態鮮度（trigger 檔變但 `moc.static` 未變）→ **WARN**（啟發式，可能誤判，比照 R-18 不擋 merge）。
- 連結懸空（`moc.map` 連到不存在的產物）→ **本次新破壞 FAIL、陳年 WARN**（比照 R-22 diff-aware）。
- 連結孤兒（active openspec change / plan 未被 link）→ **WARN**（提醒補 link）。
*替代*：全部 FAIL——否決（啟發式 FAIL 摩擦大、誤報傷信任）。

**D4 — L2 狀態對齊為 advisory，不入 R-24。** 「stage 真的 done 嗎」是語意，無法確定性判；比照既有「Doc-alignment review」段，於 CLAUDE.md 記為 Copilot advisory 層。

**D5 — opt-in（`moc` 未設 → NA）。** 不是每個 repo 都有 MOC，不強制。

## Risks / Trade-offs

- **靜態鮮度誤報**（trigger 檔因無關原因變動）→ 設 WARN + 可豁免；triggers 由 repo 自訂縮小範圍。
- **「連結」定義模糊**（什麼算 map 裡的 link）→ 重用 R-22 的 link/path token 抽取（markdown 內部連結 + path-shaped token），對象限 `openspec/changes/**`、`docs/superpowers/{specs,plans}/**`。
- **孤兒範圍**（哪些產物「必須」被 link）→ 限 active openspec change 與 `docs/superpowers/plans/*`；archived 不算。
- **無 diff context（本地非 PR）** → 靜態鮮度無法證明「本次新破壞」降 WARN／略過；懸空降 WARN（比照 R-22 graceful degradation）。

## Migration Plan

- 純新增規則 + 新 config 區塊，opt-in；既有 repo 未設 `moc` → NA，零影響。
- 本 repo（paulsha-conventions）可自宣告 `moc` 自我 dogfood（map 連到自身 `openspec/changes` 與 `docs/superpowers`）。
- Rollback：移除 r24 module 與 `moc` 設定即可。
- Release：merge 當下 PATCH bump（`flat` profile，一個 feature batch）。

## Open Questions

- `moc.triggers` 預設集（`Dockerfile*` / `build/**` / `install/**` / `toolchain/**`）是否提供 profile 預設，或一律 repo 自填。
- 孤兒檢查是否涵蓋 `docs/superpowers/specs/*`（設計文件），或只 plans + openspec changes。
- 靜態 MOC 可為「CLAUDE.md 內一段」而非獨立檔時，鮮度如何判（需 anchor/標記區段）——v1 先限獨立檔 `moc.static`，CLAUDE.md 段落模式留待後續。
