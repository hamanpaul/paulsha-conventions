## ADDED Requirements

### Requirement: runtime bundle 必須來自 clean tagged canonical source
Builder SHALL 只從 canonical、clean、tagged source commit 建立 versioned runtime
bundle。`VERSION`、tag、wheel metadata 與 manifest policy/package version MUST
一致；dependency closure MUST 全為 wheels。

#### Scenario: dirty 或 tag/version skew
- **WHEN** source dirty、HEAD 未被指定 release tag 指向，或版本 identity 任一不一致
- **THEN** builder FAIL，且不得留下可被誤認為成功的 archive

#### Scenario: deterministic output
- **WHEN** 相同 source commit、toolchain input 與 dependency wheels 重建兩次
- **THEN** archive payload ordering、normalized metadata 與 SHA-256 相同

### Requirement: manifest 與 checksum 必須覆蓋 engine/skill/runtime identity
Bundle SHALL 原子包含 engine wheel、wheel-only dependency closure、
`preflight-ci` skill、runtime manager、installer、manifest 與 checksums。
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

#### Scenario: install smoke 失敗
- **WHEN** venv install、policy smoke 或 preflight smoke 任一步失敗
- **THEN** installer FAIL，原 current/state 不變，staging 不可被標為 VERIFIED

#### Scenario: unmanaged skill target
- **WHEN** agent skill target 是非 installer 管理的真檔、目錄或外部 symlink
- **THEN** installer FAIL 並保留原 target

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
distribution attestation identity；MUST NOT 要求 `.git`、source checkout，亦
MUST NOT 讀/執行 GitHub Actions workflow或執行 network resolver。

#### Scenario: fresh offline HOME
- **WHEN** 全新暫存 HOME 僅有已驗證 bundle且 network/source checkout 不可用
- **THEN** install 後對 fixture target repo 的 full preflight PASS

### Requirement: rollback/uninstall 只操作已驗證受管 release
Rollback SHALL 只切回已安裝且重驗通過的 release，不下載或 rebuild。
Uninstall MUST 驗證 state ownership/path containment，且不得移除 active release
或非受管 user data。

#### Scenario: rollback offline
- **WHEN** current Y、previous X 均 VERIFIED，且 network 不可用
- **THEN** rollback 原子切回 X，後續 target X preflight 可執行
