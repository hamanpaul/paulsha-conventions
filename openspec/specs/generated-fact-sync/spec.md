# generated-fact-sync Specification

## Purpose
TBD - created by archiving change doc-rule-hardening. Update Purpose after archive.

## Requirements
### Requirement: generated fact sync 為 opt-in deterministic gate
專案設定 SHALL 支援 optional `generated_facts`。當 `generated_facts` 未宣告時，generated-fact
sync rule SHALL 視為 not-applicable 並回報 PASS。當 `generated_facts` 已宣告但格式不完整或型別錯誤時，
rule MUST 回報 FAIL。

#### Scenario: 未宣告 generated_facts 時不啟用 gate
- **WHEN** `.paul-project.yml` 未宣告 `generated_facts`
- **THEN** generated-fact sync rule 回報 PASS（not-applicable）

#### Scenario: generated_facts 格式錯誤
- **WHEN** `.paul-project.yml` 宣告 `generated_facts`
- **AND** 某 entry 缺少必要欄位或型別不符
- **THEN** generated-fact sync rule 回報 FAIL

### Requirement: generic marker protocol 與 command execution model 固定
generic generated-fact sync MUST 使用下列 marker 語法：
`<!-- BEGIN: generated-fact marker="<name>" --> ... <!-- END: generated-fact marker="<name>" -->`。
rule MUST 以 `shlex.split` 且不經 shell 執行 command，`cwd` MUST 為 `repo_root`，`LC_ALL`
MUST 設為 `C`，且 MUST 套用固定 timeout。rule MUST 以正規化 UTF-8 stdout 作為比較內容；
command non-zero exit、marker 缺失或輸出不一致時 MUST 回報 FAIL。

#### Scenario: marker 與輸出一致時通過
- **WHEN** generated fact command 成功執行
- **AND** marker block 內容與正規化 stdout 完全一致
- **THEN** generated-fact sync rule 回報 PASS

#### Scenario: command 失敗或 marker 缺失時失敗
- **WHEN** generated fact command 非 0 結束或目標文件缺少對應 marker block
- **THEN** generated-fact sync rule 回報 FAIL

### Requirement: 既有 CLI help marker SHALL backward-compatible
generic generated-fact sync 的引入 MUST NOT 破壞既有 `R-16` 的 `cli` 設定與 `cli-help` marker。
第一版 SHALL 允許 generic marker-sync 與 `R-16` 並存，且 repo 不需立刻將既有 CLI help 區塊改寫為新 marker。

#### Scenario: 既有 CLI help 文件不需立即遷移
- **WHEN** repo 仍只使用既有 `cli` 設定與 `cli-help` marker
- **THEN** `R-16` 仍能照常檢查該區塊，且 generic generated-fact sync 不要求立即遷移

#### Scenario: generic facts 與 CLI help 可並存
- **WHEN** repo 同時宣告 `cli` 與 `generated_facts`
- **THEN** CLI help sync 與 generic generated-fact sync 皆可各自檢查其對應輸出而不互相覆蓋
