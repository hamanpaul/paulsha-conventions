---
type: feat
scope: doc-drift
issue: 25
---
新增語言無關、零設定的 doc↔code 漂移共用核心 `policy_check/doc_drift/`（refs/paths/symbols/coverage/langs/provision primitive），symbol 以 universal-ctags scoped identity `(language, kind, scope, name)` 差集判定 removed。
