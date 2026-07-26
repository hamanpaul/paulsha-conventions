# Versioned runtime bundle proposal

## Issue

`hamanpaul/paulsha-conventions#48`

## Why

目前 production skill 依賴完整 Git checkout 與單一 mutable symlink，無法讓不同
下游 repo 依自己的 `policy_version` 分批升版，也無法把 engine、dependency
closure、skill 與 installer 視為同一個不可變、可驗證、可回滾的 release unit。

公開 project manifest 亦仍處於雙名過渡期：core 優先讀
`.project-policy.yml`，但 legacy `.paul-project.yml` 的 consumer、衝突偵測與
fleet migration 尚未閉環。

## What Changes

- 新增 versioned runtime bundle builder 與 manifest/checksum contract。
- 新增 installed-bundle verifier、stable selector、offline installer、atomic
  activation、rollback 與 safe uninstall。
- stable selector 依 target manifest 的 exact `policy_version` 選已安裝 release；
  缺版時 fail-closed，禁止 fallback `current` 或最新版。
- deployed runtime 驗證 wheel、skill 與 manifest 來自同一 release identity，
  不要求 source checkout、`.git/` 或 network。
- `.project-policy.yml` 升格為 canonical manifest；legacy-only repo 可相容運作並
  WARN，雙檔語意衝突 FAIL。
- 新產物、active docs、scripts 與 templates 只生成 canonical 名稱。
- 現有 tracked legacy manifest 由各 repo 獨立 PR 遷移。

## Out of scope

- 不決定 Artifactory、內部 PyPI、GitLab Package Registry 或其他 artifact
  authority；publication、認證、retention 與 audit 仍由 issue 39 決策。
- 不移除 GitHub／GitLab 最終 merge gate。
- 不在 patch/minor release 移除 legacy alias。
- 不以中央 engine 自動修改下游 repo。
- checksum 提供 payload integrity，不宣稱取代由發行管道提供的 artifact
  authenticity/signature。
