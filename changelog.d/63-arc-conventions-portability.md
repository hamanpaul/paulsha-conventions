---
type: feat
scope: portability
issue: 63
---
新增 distribution identity（`policy_check/identity.py` + `policy_check/data/distribution.yml`），把 canonical authority 從原始碼常數下移為安裝期決定、執行期唯讀的發行身分，讓同一份 codebase 能以不同發行身分部署；`.project-policy.yml` 只能宣告一致、不能改指向的既有信任邊界不變。
