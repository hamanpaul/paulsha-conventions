# doc-reference Specification

## Purpose
R-22（doc-reference）為 doc-alignment 三層治理的 **Tier 2**（確定性 gate）。它在 CI 偵測
`README.md` 與 `docs/**` 對 code 產物（檔案路徑、markdown 內部連結、反引號 symbol）的
**結構化懸空引用**——當被引用的產物被搬移／刪除後文件仍殘留引用時標記，降低文件結構性
陳舊（doc rot）長期累積。Tier 1（agent checklist 預防）與 Tier 3（Copilot 語意複審）為其
互補的 advisory 層；語意陳舊（引用仍在但描述過時）不屬本規格範圍。

## Requirements
### Requirement: 偵測 docs 對檔案路徑與內部連結的懸空引用
R-22 MUST 掃描 canonical doc scope 中的結構化路徑引用（markdown 內部連結與 path-shaped token）。
canonical doc scope 由 `.paul-project.yml` 的 `doc_paths` 決定；當 `doc_paths` 未宣告時，預設為
`README.md` 與 `docs/**`。對在 head 無法解析到 git-tracked 檔案者回報為懸空。嚴重度依
`base..head` diff 判定：本次變更才弄壞者 MUST 為 FAIL；base 與 head 皆不存在的陳年懸空 MUST
為 WARN。

#### Scenario: 路徑目標被本次 PR 刪除
- **WHEN** 一份 in-scope doc 引用某檔案路徑，且該路徑在 base 存在、在 head 已被本次變更刪除
- **THEN** R-22 回報 FAIL

#### Scenario: 陳年懸空路徑
- **WHEN** 一份 in-scope doc 引用某路徑，該路徑在 base 與 head 皆不存在
- **THEN** R-22 回報 WARN

#### Scenario: 內部連結解析到存在的檔案
- **WHEN** 一份 in-scope doc 的 markdown 內部連結指向一個存在的 git-tracked 檔案
- **THEN** R-22 不將該連結列為懸空

#### Scenario: repo 可擴充 in-scope docs
- **WHEN** 專案把 `CLAUDE.md` 納入 `doc_paths`
- **THEN** R-22 會掃描 `CLAUDE.md` 中的結構化路徑引用

### Requirement: diff 驅動偵測 docs 對本次移除 symbol 的引用
R-22 MUST 從 `base..head` diff 找出 Python 原始檔（`*.py`，v1 範圍）中本次被刪除或改名的
`def`/`class` 定義（在 base 有定義、在 head 無）。若任一 in-scope doc 在 head 仍以反引號
引用該 symbol 名稱，MUST 回報 FAIL。R-22 MUST NOT 對 docs 引用的 symbol 做全域稽核
（不得僅因某 symbol 在 repo 找不到、但非本次移除而回報）。

#### Scenario: doc 引用的 symbol 被本次 diff 移除
- **WHEN** 本次變更刪除了某 `def foo` / `class Foo`，而一份 in-scope doc 在 head 仍含反引號 `foo`
- **THEN** R-22 回報 FAIL

#### Scenario: symbol 仍存在則通過
- **WHEN** 一份 in-scope doc 引用的 symbol 其定義在 head 仍存在
- **THEN** R-22 不因該 symbol 回報

### Requirement: 無 diff context 時優雅降級
R-22 MUST 在缺少可解析 base ref 的脈絡（如本地 `python3 -m policy_check --repo .` 非 PR 脈絡）下仍可執行：path/連結懸空 MUST 降級為 WARN（無法證明為本次新破壞），且 symbol prong MUST 關閉。

#### Scenario: 本地無 base ref
- **WHEN** 在無可解析 base ref 的脈絡下執行 R-22，且某 in-scope doc 含懸空路徑
- **THEN** R-22 回報 WARN，且不對任何 symbol 回報

### Requirement: 掃描範圍排除規格文件與自身 fixtures
R-22 MUST 將 `openspec/**`、`docs/superpowers/**` 以及規則自身 fixtures
（`tests/fixtures/doc-reference/**`）排除於掃描之外，即使這些路徑被 `doc_paths` 命中亦然，
因這些路徑會刻意引用尚未建立或歷史性的產物。

#### Scenario: spec/plan 文件不被掃描
- **WHEN** `openspec/**` 或 `docs/superpowers/**` 下的文件引用一個不存在的產物
- **THEN** R-22 不回報該引用

#### Scenario: doc_paths 不覆蓋 built-in exclusions
- **WHEN** `doc_paths` 命中 `docs/superpowers/specs/example.md`
- **THEN** R-22 仍不掃描該檔

### Requirement: 支援豁免 label 與 per-repo allow 清單
R-22 MUST 在 PR 帶 `policy-exempt:doc-reference` label 時回報 SKIP。R-22 MUST 尊重
`.paul-project.yml` 的 `doc_reference.allow`（doc-path glob 清單），命中清單的 doc 不納入
偵測。

#### Scenario: 豁免 label 生效
- **WHEN** PR 帶 `policy-exempt:doc-reference` label
- **THEN** R-22 回報 SKIP

#### Scenario: allow 清單命中的 doc 不被偵測
- **WHEN** 某 in-scope doc 的路徑命中 `doc_reference.allow` 的 glob，且該 doc 含懸空引用
- **THEN** R-22 不因該 doc 回報

### Requirement: project-config schema 驗證 doc_reference.allow 型別
R-08 project-config schema MUST 在 `.paul-project.yml` 出現 `doc_reference` 時，驗證其
`allow`（若存在）為字串陣列；型別不符時 MUST 回報 FAIL。

#### Scenario: doc_reference.allow 非陣列
- **WHEN** `.paul-project.yml` 的 `doc_reference.allow` 被設為非 `list[str]`（如字串或映射）
- **THEN** R-08 回報 FAIL

#### Scenario: 合法的 allow 陣列通過
- **WHEN** `.paul-project.yml` 的 `doc_reference.allow` 為字串陣列
- **THEN** R-08 接受該檔案

