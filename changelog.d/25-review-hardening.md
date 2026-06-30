---
type: fix
scope: doc-drift
issue: 25
---
依 code review 硬化：R-22 改真正委派共用核心 `refs.extract_refs`（移除自家 `_BARE_RE` 副本，純單字不再誤報、與 standalone Action 判定一致）；CI 主 pytest job 安裝 universal-ctags；Action 補 `map`/`governed-prefix` 輸入；`parse_ctags_json` 容忍非物件 JSON 行；inline-ignore 僅認 HTML 註解形式；R-24 治理前綴沿用廣義 `docs/superpowers/`。
