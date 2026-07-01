## Context

`policy_check` 有 26 條規則（R-01~R-26），報告平鋪、依 `rule_id` 排序。`report.emit()` 是唯一輸出點（caller 僅 `cli.py:58`）。規則以 `@register` 自動收集，各自帶 `rule_id`／`exempt_label`／`check()`。既有 R-26 `generated_facts`（opt-in、`_marker_sync` 支撐）能守「文件生成事實」漂移，但本 dogfood repo 未對自己啟用。完整設計見 `docs/superpowers/specs/2026-07-01-rule-families-and-version-fact-design.md`。

## Goals / Non-Goals

**Goals:**
- 報告依 family 分組呈現；family 分類集中單一可審視處；新增規則漏分類時測試會擋。
- 任何被 summary 計數的規則結果，都必須出現在 body 逐條清單（body 區塊數 == summary 計數不變量）。
- README 手抄版號（L271／L21）不再能無聲漂移：L271 由 R-26 marker 強制、L21 去字面。

**Non-Goals:**
- 不做 auto-fix／regenerate script（R-26 FAIL 由 agent 手動修 marker）。
- 不把規則數／inventory 做成 fact（屬 CHANGELOG／RELEASES）。
- 不新增 CLI flag（分組為預設；`--help` 不變 → R-16 cli-help marker 不受影響）。
- 不新增、不合併、不改號任何 `rule_id`；不改任何 exemption label；不動 R-26 規則本體語義。

## Decisions

1. **中央有序分類 `families.py`（而非每條 rule 加 `family` 屬性）**：taxonomy 是跨切面分類、使用者要能一眼審視／調整；集中單檔 churn 最小，且報告需要 family 順序。提供 `family_of(rule_id)->str`（未分類回 `"OTHER"`）與 `ordered_families()`。
2. **`emit(results, families=None)` 向後相容 + OTHER catch-all**：`families=None` 回舊平鋪。分組時走訪 `ordered_families()`，並在尾端固定輸出 `OTHER` 區段收納「family 不在 `ordered_families()`／`rule_id` 不在 map」的結果——保證不變量、防未分類規則被靜默吞掉（runtime 不跑完整性測試）。per-rule 區塊格式、summary、`return 1 if fails` 全不變。
3. **完整性由測試守**：`registry.load_all()` 每個 `rule_id` 剛好屬一個 family；`FAMILIES` 無未知/重複 id。
4. **版號守門用既有 R-26，不新增規則**：`.paul-project.yml` 宣告一個 `generated_facts` entry（`cat VERSION` ↔ README `repo-version` marker）。marker 名檔內唯一；字面 `repo-version` pair 不得現身於 README 散文（`marker_block` 綁第一個 match）。
5. **L21 去字面而非再加 marker**：符合「只守 repo 版號、不重抄真相」；無字面即無漂移。

## Risks / Trade-offs

- **R1 未分類規則被漏印** → 由 Decision 2 的 OTHER catch-all + 不變量測試消除。
- **R2 marker 正規化不等**（尾端換行/CRLF/散文混入）→ `normalize=.strip()` 吞尾端換行；marker 區塊只放版號一行；red-case 測試涵蓋。
- **R3 family 分類主觀** → 集中單檔、測試守完整性、純呈現零 ID 成本，可後續無痛調整。
- **R4 marker 名撞 R-16 cli-help** → tag 隔離（`generated-fact` vs `cli-help`），已驗互不匹配。
