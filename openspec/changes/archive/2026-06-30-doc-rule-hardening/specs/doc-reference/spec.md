## MODIFIED Requirements

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
