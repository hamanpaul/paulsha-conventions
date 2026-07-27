---
type: fix
scope: distribution
---
修正 release workflow 的安裝 smoke：改以隔離模式（`-I`）啟動安裝出的 CLI 並核對套件版本，不再拿 `policy_check --repo` 的 policy 判定 exit code 當 runtime 健康度依據（tag push 無 PR context，判定必然不過，會擋掉合法 release），同時避免 cwd 的 source 樹與 egg-info 蓋過 venv 中真正安裝的產物。
