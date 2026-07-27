---
type: feat
scope: distribution
---
新增 tag 觸發的 release workflow：依支援的 Python minor version 逐一建置 runtime bundle、驗證 archive digest 與離線安裝，全數通過後才發布 GitHub Release，並以該版 `CHANGELOG.md` 段落、各 archive 的 SHA-256 對照與前版 compare 連結組成 release notes；`policy-check-changelog` 新增 `extract` 子命令作為 notes 來源。
