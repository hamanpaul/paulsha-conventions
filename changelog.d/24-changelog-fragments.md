---
type: feat
scope: changelog
issue: 24
---
CHANGELOG 改 per-PR fragment（`changelog.d/<issue>-<slug>.md`）消除並行 agent 的 `[Unreleased]` 衝突：R-09 改驗本 PR 有無 fragment、R-04 不再要求 `[Unreleased]`、新增 `python3 -m policy_check.changelog collate --version X.Y.Z --date YYYY-MM-DD` 於 release 時把碎片依 type 收斂成 Keep-a-Changelog dated 段並清空目錄。Hard cutover（行為綁版本，不向下相容）。
