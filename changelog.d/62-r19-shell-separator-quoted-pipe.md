---
type: fix
scope: rules
issue: 62
---
R-19：`run` 行的 shell 分隔符不再把單一 `|` 當分隔（只保留 `&&`/`||`/`;`），修正含引號 pipe（如 `pytest -k "a|b"`）被切成無法 shlex 解析的片段、導致漏判實際測試執行的 false negative。
