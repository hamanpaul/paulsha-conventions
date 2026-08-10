---
type: fix
scope: distribution
issue: 52
---
修補 activation journal 的兩則審查缺陷：（1）三處 atomic-write 站點統一抽成共用 helper，temporary 檔內容在 `os.replace()` 前先 flush + `os.fsync()`，避免斷電時 rename 已提交但內容未落盤；（2）`recover()` 在需要改寫 skill_target 的還原路徑上，未指定時改為預設 `_default_skill_target()` 並強制與 journal 記錄比對，不一致即 fail-closed 拒絕，避免可寫 journal 單方決定改寫任意路徑。
