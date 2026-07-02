---
type: feat
scope: policy-config
issue: 30
---
`.paul-project.yml` 新增 optional `auto_build:` 區塊（LLM auto build 慣例欄位：`description`/`setup`/`steps`/`artifacts`/`verify`），R-08 做 lenient 形狀驗證（未知 subkey 放行、engine 永不執行其中命令）。
