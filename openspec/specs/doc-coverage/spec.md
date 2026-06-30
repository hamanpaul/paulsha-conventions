# doc-coverage Specification

## Purpose
TBD - created by archiving change doc-rule-hardening. Update Purpose after archive.

## Requirements
### Requirement: doc coverage rule 為 opt-in 並支援 `changed` 與 `all` 模式
專案設定 SHALL 支援 optional `doc_coverage`。當 `doc_coverage` 未宣告時，coverage rule SHALL
視為 not-applicable 並回報 PASS。當 `doc_coverage` 已宣告時，rule MUST 支援 `mode: changed`
與 `mode: all`：`changed` 僅檢查 `base...HEAD` 新增的 facts，`all` 檢查 extractor 產出的全部 facts。

#### Scenario: 未宣告 doc_coverage 時不啟用 gate
- **WHEN** `.paul-project.yml` 未宣告 `doc_coverage`
- **THEN** coverage rule 回報 PASS（not-applicable）

#### Scenario: changed 模式只檢查本次新增 facts
- **WHEN** `doc_coverage.mode` 為 `changed`
- **AND** 本次 PR 新增 fact `session.renumber`
- **AND** 既有 fact `session.close` 未在 target docs 被 mention
- **THEN** coverage rule 只要求 `session.renumber` 被 mention，而不因 `session.close` 回報 FAIL

#### Scenario: all 模式檢查全部 facts
- **WHEN** `doc_coverage.mode` 為 `all`
- **AND** 任一 extractor 產出的 fact 未被 target docs mention
- **THEN** coverage rule 回報 FAIL

### Requirement: changed 模式缺少 diff context 時優雅降級
當 `doc_coverage.mode` 為 `changed` 且執行脈絡缺少可解析 base ref 時，coverage rule MUST 回報
WARN，且 MUST NOT 在該次執行中對 omission 回報 FAIL。

#### Scenario: 本地無 base ref
- **WHEN** 在無可解析 base ref 的脈絡下執行 coverage rule
- **AND** `doc_coverage.mode` 為 `changed`
- **THEN** coverage rule 回報 WARN，且不因缺少 diff context 對 facts 漏記回報 FAIL

### Requirement: target docs 與 extractor config 必須明確且合法
`doc_coverage.targets` MUST 解析到 canonical doc scope 內的文件。若 target 超出 `doc_paths` 範圍、
目標文件不存在、或任一 extractor 缺少必填欄位，coverage rule MUST 回報 FAIL。

#### Scenario: target 超出 canonical docs 範圍
- **WHEN** `doc_coverage.targets` 指向未納入 `doc_paths` 的檔案
- **THEN** coverage rule 回報 FAIL

#### Scenario: extractor 缺少必填欄位
- **WHEN** 某 extractor 缺少其 `kind` 所需的必填欄位
- **THEN** coverage rule 回報 FAIL

### Requirement: built-in extractors 與 mention 判定 SHALL deterministic
v1 coverage rule MUST 支援四種 built-in extractors，且其 fact identity MUST 固定如下：
`modules` 產出 repo-relative POSIX 路徑、`rpc_methods` 產出 regex capture 的 method 名稱、
`env_vars` 產出 prefix 命中的環境變數名、`cli_tree` 產出 command stdout 中一行一個完整命令路徑。
facts 的 mention 判定 MUST 採區分大小寫的精確 token/phrase 比對，MUST NOT 以子字串命中算覆蓋。

#### Scenario: modules extractor 不以 basename 混淆不同檔案
- **WHEN** repo 同時存在 `pkg/a/auth.py` 與 `pkg/b/auth.py`
- **THEN** modules extractor 產出的 facts 分別為 `pkg/a/auth.py` 與 `pkg/b/auth.py`

#### Scenario: 子字串命中不算 coverage
- **WHEN** target doc 僅包含較長字串中的局部片段，而非完整 fact 名稱
- **THEN** coverage rule 不將其視為該 fact 已被 mention
