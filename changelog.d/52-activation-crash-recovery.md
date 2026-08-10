---
type: feat
scope: distribution
issue: 52
---
activation 新增 fsync hash-chain journal、明確 recover 入口與逐步 hard-exit recovery，讓斷電後 managed state 自動收斂至完整舊世代或已提交的新世代。
