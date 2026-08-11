---
type: refactor
scope: portability
issue: 74
---
測試套件（`test_preflight.py`／`test_runtime_bundle.py`／`test_runtime_bundle_integration.py`）與 `release.yml` 的產物命名／verify／install smoke／release notes 四處，改為從 `identity()` 動態推導 repo 短名與 distribution name，取代寫死的 `hamanpaul/paulsha-conventions` 字面值；upstream 內建身分與既有行為零變更，僅縮小與 distribution fork 的 divergence。
