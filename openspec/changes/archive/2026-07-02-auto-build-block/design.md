# Design: auto-build-block

## Context

`.paul-project.yml` 是 per-repo 的 project config，現由 policy engine 消費；R-08 採
寬鬆白名單（只驗已知 key，未知 key 放行）。issue #30 提案 A 要讓同一檔案承載
build flow 宣告，消費者是 **LLM auto build agent**，不是 engine。
完整決策脈絡見 `docs/superpowers/specs/2026-07-02-auto-build-block-design.md`。

## Goals / Non-Goals

**Goals:**
- 定義 `auto_build` 區塊慣例欄位，LLM 冷讀即可執行 build。
- R-08 形狀驗證抓常見手誤（str/list 型別互錯、整塊寫成非 mapping）。
- 欄位演進不需 engine release（未知 subkey 放行）。

**Non-Goals:**
- engine 執行或解讀 build 命令（永不）。
- 提案 B（project-scan 注入機制）——產物在本 repo 外，另案處理。
- 本 repo 自身宣告 `auto_build`（無 build 產物）。

## Decisions

1. **命名 `auto_build:` 而非 `x-build:`**——成為 engine 已知 key 後，`x-` 要防的
   reserved-key 撞名即不存在；與既有「宣告的區塊皆已知並驗證」慣例一致；對 LLM 自述性佳。
   替代案 `x-build` + `x-*` 永不保留保證：頂層未知 key 本就放行，屬 YAGNI。
2. **A2-lenient 驗證**——仿 `secret_scan`/`moc` 的 `is not None` optional pattern：
   mapping 必須、已知 subkey（`description` str；`setup`/`steps`/`artifacts`/`verify`
   list[str]）型別檢查、未知 subkey 放行、無必填 subkey。
   替代案 A1（純 YAML 不驗）：手誤無提示；A2 全嚴格（未知 subkey FAIL）：每次欄位
   演進綁 engine release，R-23 lockstep 下游代價高。
3. **不動 `policy_check/config.py`**——engine 不消費 `auto_build`，不設 default，
   維持最小變更面。

## Risks / Trade-offs

- [未知 subkey 放行 → subkey 名打錯不會被抓（如 `step:`）] → 已知欄位集寫進 README
  慣例段；LLM 消費端對此類漂移天然寬容；必要時後續可加 WARN 級提示（不擋）。
- [`auto_build` 含命令字串，可能被誤會 engine 會執行] → README 與 rule 註解明寫
  「只驗形狀、永不執行」；R-08 實作不含任何 subprocess。
- [提案 B 未落地前，區塊只服務有引 conventions 的 repo] → 接受；B 落地後同一 schema
  直接複用（注入檔案內容即含 `auto_build`）。
