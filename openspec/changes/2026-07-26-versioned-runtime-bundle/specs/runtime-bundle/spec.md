## ADDED Requirements

### Requirement: runtime bundle 必須來自 clean tagged canonical source
Builder SHALL 只從 canonical、clean、tagged source commit 建立 versioned runtime
bundle。`VERSION`、tag、wheel metadata 與 manifest policy/package version MUST
一致；dependency closure MUST 全為 wheels，且每個 resolved dependency
distribution/version MUST 命中 exact constraint。

#### Scenario: dirty 或 tag/version skew
- **WHEN** source dirty、HEAD 未被指定 release tag 指向，或版本 identity 任一不一致
- **THEN** builder FAIL，且不得留下可被誤認為成功的 archive

#### Scenario: deterministic output
- **WHEN** 相同 source commit、toolchain input 與 dependency wheels 重建兩次
- **THEN** archive payload ordering、normalized metadata 與 SHA-256 相同

### Requirement: manifest 與 checksum 必須覆蓋 engine/skill/runtime identity
Bundle SHALL 原子包含 engine wheel、wheel-only dependency closure、
`preflight-ci` skill、runtime manager、source/manager 共用的 stdlib verifier、
installer、manifest 與 checksums。
Manifest MUST 記錄 schema、policy/skill/package version、repo、tag、commit、
build interpreter/ABI/platform compatibility、prerequisites 與 payload hashes。

#### Scenario: 安裝 runtime 不相容
- **WHEN** host Python major/minor、implementation、ABI 或 platform 不等於 manifest
- **THEN** installer 在建立 staging 前 FAIL，不嘗試用不相容 wheel closure 安裝

#### Scenario: 任一 payload 被竄改
- **WHEN** wheel、skill、runtime manager 或 manifest 在 build 後被修改
- **THEN** installer/verifier FAIL，且不得執行未驗證 payload

### Requirement: installer 必須 staging、offline smoke、atomic activation
Installer SHALL 先驗證 bundle，再於新 staging 建隔離 venv，以
`--no-index --find-links` 安裝 dependency closure並執行 artifact smoke；全部成功
後才 MAY 原子 activation。失敗 MUST 保持原 active release/state/skill link。
Installer SHALL 在 staging 前消費 manifest prerequisites，驗證 `git`、
`sha256sum`、JSON-capable `universal-ctags` 與 `venv/ensurepip` 可用，失敗訊息
MUST 指出缺少的能力。Policy smoke 失敗 MUST 保留 bounded gate diagnostic。

本 change 的 mechanized guarantee 涵蓋 manager 可捕捉的 step failure；程序
遭 `SIGKILL`／主機斷電時，identity/digest 仍 MUST fail-closed，但跨多個
filesystem replace 的自動收斂列為 #52 的 bounded availability residual。

#### Scenario: install smoke 失敗
- **WHEN** venv install、policy smoke 或 preflight smoke 任一步失敗
- **THEN** installer FAIL，原 current/state 不變，staging 不可被標為 VERIFIED

#### Scenario: active release tamper 後重裝
- **WHEN** active release 驗證失敗，操作者以同版已核對外部 digest 的 bundle
  明確要求 force reinstall
- **THEN** installer MUST 先完成新 staging/venv/smoke，再交換 state-owned
  release；失敗時 MUST 保持原 state/current ownership

#### Scenario: unmanaged skill target
- **WHEN** agent skill target 是非 installer 管理的真檔、目錄或外部 symlink
- **THEN** installer FAIL 並保留原 target

#### Scenario: source installer 遇到 bundle-managed skill
- **WHEN** source-checkout skill installer 要替換 bundle-managed skill symlink
- **THEN** 普通 replace MUST FAIL；只有 distinct explicit migration flag 才可改變
  agent discovery，且不得改寫 runtime state/current

### Requirement: selector 必須依 target exact version，禁止 fallback
Stable launcher SHALL 讀 target project manifest 的 exact `policy_version`，只使用
相同版本的 VERIFIED installed release。`current` MUST NOT 作為缺版 fallback。

#### Scenario: 兩版本並存
- **WHEN** target A 要求版本 X、target B 要求版本 Y，且兩者均已安裝
- **THEN** launcher 分別使用 X/Y release 的 engine 與 attested skill identity

#### Scenario: 要求版本未安裝
- **WHEN** target 要求版本 X，但只有 Y/current 已安裝
- **THEN** launcher 明確 FAIL，不降級、不升級、不 clone/fetch

### Requirement: deployed runtime 不依賴 source checkout 或 network
Installed-bundle mode MUST 以 manifest、checksums、wheel metadata與 imported
distribution attestation identity；attestation MUST 驗證所有 bundled wheel 的
installed version 與 RECORD payload。Bootstrap/source/deployed launcher MUST 使用
isolated import，不得採用 ambient `PYTHONPATH`/`PYTHONHOME`。MUST NOT 要求 `.git`、
source checkout，亦 MUST NOT 讀/執行 GitHub Actions workflow或執行 network resolver。

#### Scenario: installed dependency 或 startup path 被竄改
- **WHEN** venv interpreter/`pyvenv.cfg` 或 bundled dependency payload 被修改，
  或 site-packages 新增 `.pth`、site/user customization、同名 module shadow
- **THEN** stdlib selector MUST 在啟動 selected venv/import 第三方 code 前 FAIL

#### Scenario: active bootstrap manager 被竄改
- **WHEN** current release 的 manifest 或 runtime manager 不符合 activation 時
  stable launcher 的 digest anchor
- **THEN** launcher MUST 在執行 current manager 前 FAIL

#### Scenario: fresh offline HOME
- **WHEN** 全新暫存 HOME 僅有已驗證 bundle且 network/source checkout 不可用
- **THEN** install 後對 fixture target repo 的 full preflight PASS

### Requirement: rollback/uninstall 只操作已驗證受管 release
Rollback SHALL 只切回已安裝且重驗通過的 release，不下載或 rebuild。
Uninstall MUST 驗證 state ownership/path containment，且不得移除 active release
或非受管 user data。Deployed host SHALL 提供不依賴 renamed venv shebang 的 stable
lifecycle launcher，並暴露 exit-0 `activate` repair。

#### Scenario: rollback offline
- **WHEN** current Y、previous X 均 VERIFIED，且 network 不可用
- **THEN** rollback 原子切回 X，後續 target X preflight 可執行

#### Scenario: rollback target 已是 current
- **WHEN** 操作者要求 rollback 到目前 active version
- **THEN** manager MUST 重驗/修復 managed links 並回報成功 no-op，且不得把
  previous 改成 current
