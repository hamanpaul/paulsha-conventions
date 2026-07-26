# project-policy-manifest Specification

## Purpose
定義平台中性的 canonical project policy manifest、legacy alias 相容期、雙檔
語意衝突的 fail-closed 行為，以及由各下游 repo 自主完成的 migration 邊界。
## Requirements
### Requirement: `.project-policy.yml` 是 canonical public manifest
所有新 bootstrap、template、active docs、installer與 selector SHALL 生成或引用
`.project-policy.yml`。`.paul-project.yml` SHALL 在相容期內作 deprecated legacy
alias，不得於 patch/minor release移除支援。

#### Scenario: canonical-only repo
- **WHEN** repo 只有合法 `.project-policy.yml`
- **THEN** 所有 policy/preflight/drift/help/selector consumer 正常使用它

#### Scenario: legacy-only repo
- **WHEN** repo 只有合法 `.paul-project.yml`
- **THEN** consumer 相容運作並發出 deprecation WARN

### Requirement: 雙檔 policy semantics 必須 fail-closed
當兩檔同時存在，loader MUST 解析兩者完整 YAML policy semantics。完全相同時
MAY 使用 canonical 但 MUST WARN；任一 semantics 不同時 MUST FAIL，禁止 silent
precedence。

#### Scenario: 雙檔相同
- **WHEN** canonical/legacy YAML mapping 語意相同
- **THEN** 使用 canonical、輸出 migration WARN

#### Scenario: 雙檔衝突
- **WHEN** policy_version 或其他 policy semantics 任一不同
- **THEN** config gate FAIL，policy/preflight/selector 不得繼續

### Requirement: config error 必須有界且無 traceback
Manifest missing/malformed/unreadable/encoding error與 runtime path race SHALL 收斂為
config/usage failure；輸出 MAY 含檔名與錯誤類別，但 MUST NOT 洩漏 config content、
token或完整 command output。

#### Scenario: manifest 不可讀
- **WHEN** selected config 是 directory、permission denied 或 invalid encoding
- **THEN** CLI 回傳有界非零 verdict，不印 traceback

### Requirement: fleet migration 必須 repo-owned
既有 tracked legacy manifest SHALL 由各 repo 的獨立 PR 以 rename 並同步 active
scripts/docs/agent markers；中央 engine MUST NOT 自動改寫下游 checkout。

#### Scenario: downstream migration
- **WHEN** 某下游 repo 仍 tracked legacy name
- **THEN** migration 在該 repo branch/PR 完成，保留該 repo 自有 gate 與 review
