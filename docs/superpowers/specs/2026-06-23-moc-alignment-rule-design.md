---
title: MOC-alignment 規則（R-24）— 專案層地圖與本次變更同步
date: 2026-06-23
status: approved
profile: flat
policy_version_at_design: 1.0.6
related_issue: "#20 引擎內部化 / GitLab 發行（解耦）"
---

# MOC-alignment 規則（R-24）

> 本設計經 explore 模式討論成形（含模型分界與 D1–D8），回填為正式 brainstorm 設計文件。對應 openspec change `moc-alignment-rule`。

## 1. 背景與問題

`superpowers:brainstorming` / `openspec` 都是**單一 feature 視角**，對整個專案全貌太片面。兩個具體痛點：

1. **動態（stage 連續性）**：大型重構切成 10+ 個互相相依的 stage，做到一半發現某根本性改變需把前面「已完成」的 stage postpone 重做。若沒有專案層、跨 session 存活的地圖，新 session（或忘記此事的人）會把該 stage 當成已完成跳過 → 前後架構衝突。
2. **靜態（操作脈絡）**：專案的 platform / vendor / toolchain / build docker / build flow / profile / situation profile（如 debug 開 ebpf）/ install flow 改了，卻沒更新對應文件，agent 進場就讀到陳舊資訊。

## 2. 模型分界（最關鍵的探索結論）

```
 內部 GITLAB（專案 repo，tier 私有）        paulsha-conventions（GitHub, shareable）
 ┌──────────────────────────────────┐      ┌─────────────────────────────┐
 │ 靜態 MOC（獨立檔 moc.static）      │      │  只住「規則」R-24            │
 │ 動態 MOC（地圖 moc.map：link 到    │◀─盯──│  通用、platform-agnostic    │
 │   specs/plans/openspec + 狀態）    │      │  不存任何專案內容            │
 │ agent 進場讀（teach-face）         │      └─────────────────────────────┘
 └──────────────────────────────────┘
```

- **內容跟著專案走**，留在各自 repo（內部 GitLab）。platform/vendor/build 等機敏脈絡放在 shareable 引擎會直接命中 **R-21 / AI-SEC-001** 的禁列（雇主標記、廠商、裝置型號）——所以**不能**放 paulsha。
- **paulsha 只出規則**，盯 agent 有沒有在「該改的時候」同步 MOC。
- CLAUDE.md 以**連結**引用 `moc.static`（teach-face：agent 讀 CLAUDE.md → 跟連結找到靜態脈絡）。

## 3. 目標與非目標

**目標**
- 通用、platform-agnostic 的 R-24，盯 repo 宣告的 MOC 與本次變更同步。
- 對上引擎現有 pattern：靜態鮮度≈R-18、連結懸空≈R-22、孤兒≈新增。
- opt-in（未宣告 `moc` → NA）；舊專案漸進導入不被打掉。

**非目標**
- MOC「狀態語意對齊」（stage 宣稱 done 是否真 done）→ L2 advisory（Copilot），不入確定性規則。
- 引擎內部化 / GitLab 發行（issue #20）→ 本案不依賴；規則邏輯不碰平台。
- 規範 MOC 檔的內部欄位 schema（platform/vendor…）→ 那是專案自己的事，引擎不管內容。

## 4. 設計：R-24（三瓣，diff-aware）

`.paul-project.yml` 宣告後生效：
```yaml
moc:
  static: docs/project-context.yml   # 靜態脈絡檔（獨立檔；CLAUDE.md 連結它）
  map:    docs/MOC.md                  # 動態地圖：link 到 specs/plans/openspec + stage 狀態
  triggers:                            # 這些一動 → static 必須同步（repo 自填，無預設）
    - "Dockerfile*"
    - "build/**"
```

| 瓣 | 觸發 / 對象 | 嚴重度 | 對應既有規則 |
|---|---|---|---|
| 靜態鮮度 | `moc.triggers` 命中檔在 diff 變、`moc.static` 不在同 diff | **WARN** | ≈ R-18 |
| 連結懸空 | `moc.map` 連到不存在的 spec/plan/openspec 產物 | **本次新破壞 FAIL / 陳年 WARN** | ≈ R-22（diff-aware） |
| 連結孤兒 | active openspec change / plan / **spec** 未被 `moc.map` link | **WARN（永不 FAIL）** | 新增 |

彙整：任一瓣 FAIL → FAIL；否則任一 WARN → WARN；皆無 → PASS。`moc` 未設或無 diff context（本地）→ 對應降級（NA / WARN）。豁免 `policy-exempt:moc-alignment`。

## 5. 設計決定（D1–D8）

- **D1** 單一規則 R-24、三瓣（比照 R-22 prong P/S），共用一個 ID 與豁免。
- **D2** platform-agnostic：只用 `ctx.changed_files` + `ctx.repo_root` + repo 檔，不讀 GitHub/GitLab env → 與 #20 解耦。
- **D3** 只有「確定性破壞」（連結懸空、本次新破壞）硬 FAIL；啟發式（鮮度、孤兒）一律 WARN。
- **D4** L2 狀態對齊為 advisory（Copilot），記於 CLAUDE.md，不入 R-24。
- **D5** opt-in（`moc` 未設 → NA）。
- **D6** `moc.triggers` 一律 repo 自填，不給 profile 預設（非每個 repo 都 embedded）。
- **D7** 孤兒涵蓋 specs + plans + openspec changes，但一律 WARN（永不 FAIL，支援舊專案漸進導入）。
- **D8** `moc.static` 一律獨立檔，CLAUDE.md 連結引用；不做 CLAUDE.md 內嵌段落模式（v1 不強制檢查該連結）。

## 6. 測試計畫（TDD，全走 fixture）
- R-08：`moc` schema（`static`/`map` str、`triggers` list[str]）。
- R-24：未設→NA、豁免→SKIP、靜態鮮度命中/未命中、連結懸空（本次新破壞 FAIL / 陳年 WARN / 無 diff 降 WARN）、孤兒（specs/plans/changes，WARN，驗證永不 FAIL）、三瓣彙整取最嚴。
- dogfood：本 repo 自宣告 `moc`，map 連到自身 `openspec/changes` 與 `docs/superpowers`。

## 7. policy / 程序
- 分支 `feature/moc-alignment-rule`（已開）。改 engine → `CHANGELOG [Unreleased]`。
- 慣例檔：CLAUDE.md 補 R-24 claim-done、白名單 `policy-exempt:moc-alignment`、新增「MOC 狀態對齊 advisory」段；README 規則總覽補 R-24。
- merge 當下 PATCH release bump（`flat`，一個 feature batch）。

## 8. 風險與待解
- 靜態鮮度誤報（trigger 因無關原因變）→ WARN + 可豁免 + triggers repo 自訂縮範圍。
- 「連結」定義 → 重用 R-22 link/path token 抽取，對象限 `openspec/changes/**`、`docs/superpowers/{specs,plans}/**`。
- 內部化（#20）後 R-24 自動在 GitLab 生效；本案不等它。

## 9. 後續
1. 引擎內部化 / GitLab 發行（issue #20）。
2. enforce「CLAUDE.md 有連結 moc.static」（teach-face 連結性，v1 後）。
3. MOC 狀態語意對齊的 L2 層（Copilot reviewer 強化）。
