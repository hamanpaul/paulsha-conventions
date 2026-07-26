# Versioned runtime bundle design

## 1. Release identity 與 trust boundary

Bundle 僅能從 clean tagged canonical source 建立。Builder 必須驗證：

- origin 為 `hamanpaul/paulsha-conventions`；
- worktree 無 tracked/untracked/ignored 汙染；
- `HEAD` 是完整 commit SHA，release tag 指向該 commit；
- `VERSION`、wheel metadata 與 tag 版號一致；
- Python dependency closure 依 bundle-owned constraint 鎖版並全部下載成 wheel；
  下載後逐一要求 resolved distribution/version 命中 exact constraint，不保留
  sdist 或未鎖 transitive wheel。

輸出為 deterministic archive：

```text
paulsha-conventions-vX.Y.Z/
├── wheels/
├── skills/preflight-ci/
├── runtime/runtime_manager.py
├── runtime/runtime_verifier.py
├── install.sh
├── manifest.json
└── SHA256SUMS
```

`manifest.json` schema 1 至少包含 policy/skill/package version、canonical repo、
tag、commit、build Python implementation/major-minor/ABI/platform compatibility、
prerequisites、每個 wheel 的 filename/hash、skill tree hash 與 runtime manager
hash。Installer 只接受相同 runtime compatibility，避免把 ABI/platform-specific
closure 當作通用 wheel 集合。`SHA256SUMS` 覆蓋 manifest 與所有 payload；
builder 另輸出 archive SHA-256 供 issue 39 的 authority 發布。

Bundle 內 checksum 只證明取得後的完整性。能替換 bundle 與 checksum 的攻擊者仍
可重建整組內容；artifact authenticity/signature 由 issue 39 的可信發行管道負責。

## 2. Installed layout 與 exact selector

預設 root：

```text
~/.local/share/paulsha-conventions/
├── releases/<version>/
│   ├── artifact/
│   │   ├── wheels/
│   │   ├── skills/preflight-ci/
│   │   ├── runtime/
│   │   ├── manifest.json
│   │   └── SHA256SUMS
│   ├── venv/
│   └── VERIFIED
├── current -> releases/<version>
├── bin/policy-preflight
├── bin/policy-runtime-bundle
└── state.json
```

`current` 只代表 activation/rollback 狀態，不是 engine selector fallback。
Stable launcher 先從 target repo 解析 canonical/legacy manifest，取得 exact
`policy_version`，再選 `releases/<version>`。要求版本未安裝、未 VERIFIED、
manifest/payload 重驗失敗或 installed distribution version 不符時皆 FAIL。

Launcher 必須清除 `PYTHONPATH`／`PYTHONHOME`、啟用 safe-path/isolated import
語意，並把 selected manifest 明確傳入 `policy_check.preflight`。Preflight
驗證 selected manifest、所有 wheel/skill identity、實際 installed distribution
version 與 RECORD payload，
不得 fallback source checkout、workflow cache、default branch 或 `current`。
Stable launcher 在 activation 時內嵌 active manifest digest；每次啟動先用 isolated
host Python核對 manifest，再依 anchored manifest 的 runtime hash 核對 current
manager，防止 bootstrap manager 先執行後自驗。

## 3. Installer、activation、rollback 與 uninstall

`install.sh` 是薄 bootstrap：先用 host checksum tool 驗整個 bundle，再執行已
驗證的 stdlib runtime manager。Manager：

1. 以 source/manager 共用的 stdlib verifier 驗 manifest schema、path
   containment、hash、version 與 wheel closure。
2. 在任何 staging 寫入前依 manifest prerequisites 確認 host 提供 `git`、
   `sha256sum`、JSON-capable `universal-ctags` 與 `venv/ensurepip`。
3. 在 runtime root 內建立唯一 staging directory並建立 venv，以
   `--no-index --find-links` 安裝 wheel closure。
4. 移除只供 bootstrap 的 pip/setuptools；由 host/current manager 內的 stdlib
   verifier 直接驗 site-packages 的每個 wheel RECORD，並拒絕 `.pth`、
   site/user customization 與同名 module shadow，因此不先執行 selected venv code。
5. 在暫存 HOME 與 fixture repo 執行 policy/preflight artifact smoke。
6. 把完整 staging rename 到新的 immutable `releases/<version>`。
7. 以 snapshot + temp file/symlink + `os.replace` transaction 更新
   state/current/stable launchers/managed skill link；任一步失敗即回復全組。

失敗不得改變 active state。Rollback 只可切到已安裝且重新驗證通過的 release，
不下載、不 rebuild。Uninstall 不可移除 active release；移除全部時只處理由
state/target containment 證明為 installer 管理的產物。

active release 若被竄改，以 `install --force-reinstall` 從已核對外部 digest
的同版 bundle 修復；新 staging 通過 venv/smoke 後才交換 state-owned release，
並在 state/link 成功後 best-effort 清理 displaced 舊目錄。部署 root 的
`bin/policy-runtime-bundle` 以 isolated Python 啟動 current manager，避免依賴
rename 後含 staging shebang 的 venv console script。`activate` 提供 exit-0 link
repair；rollback target 已是 current 時修復受管 links 並回報成功 no-op，禁止把
previous 汙染成 current。

`~/.agents/skills/preflight-ci` 若是非受管真檔／目錄／外部 symlink，installer
必須拒絕且保留原內容。所有測試使用暫存 HOME/runtime root，不碰真實 user state。
反向 source installer 若遇到 bundle-managed symlink，普通 `--replace` 也必須
拒絕；distinct explicit migration flag 只可改 skill discovery，不改 runtime
state/current。部署 skill 從自身 resolved physical path 優先反推 custom runtime
root，避免公開 `--root` 安裝成功後因未 export 環境變數而失聯。

## 4. Canonical project manifest 與 conflict gate

`.project-policy.yml` 是 canonical public name；`.paul-project.yml` 是 deprecated
legacy alias。

- canonical-only：正常載入。
- legacy-only：相容載入並發出 deprecation WARN。
- 雙檔且 YAML policy semantics 完全相同：載入 canonical 並 WARN。
- 雙檔但任一 policy semantics 不同：ConfigError/FAIL，不 silent precedence。
- malformed/unreadable/encoding error：收斂成 usage/config failure，不 traceback。

Selector 可用嚴格的 stdlib top-level `policy_version` parser 做首次選版；完整
YAML semantics 與雙檔 conflict 仍由 selected engine 再驗。新 bootstrap、
template、help updater、drift、skill docs 與 active README 只生成 canonical 名稱。
歷史 changelog/archived plans 保留原名作 provenance，不做機械改寫。

## 5. #46 residual hardening

本 change 一併重裁決前輪列管觀察：

- engine repo/ref path 必須拒絕 dot-segment，cache path 保證 containment；
- source/bundle import path 與 attested manifest identity 交叉驗證；
- `-I` isolated import 升格 canonical spec，bootstrap/source/deployed 路徑皆忽略
  ambient `PYTHONPATH`/`PYTHONHOME`；
- full preflight 所有 conditional steps 都 SKIP 時 FAIL；明確 `--skip-tests`
  可略過 tests，且其他 optional path 不存在時不應產生假性 FAIL；
- wrapper 在 Python < 3.11 時提供可行動錯誤；
- config、path resolution、command I/O/encoding 例外收斂為最終 verdict；
- engine I/O 錯誤提供減敏但可行動的 release/version/path-class 診斷。

## 6. Delivery 與驗收分層

候選 PR 用 synthetic clean tagged fixture 驗 builder 與 full offline lifecycle。
PR merge 後立即發布下一個 flat-profile patch release，再從真正 clean annotated
tag 建正式 bundle，於全新暫存 HOME 做無 source checkout／無 `.git`／無網路
install + preflight + rollback smoke。

下游 tracked legacy manifests 在中央 release 穩定後，以各 repo 的獨立 branch/
worktree/PR 執行 `git mv`、active docs/scripts/agent marker 與 engine pin 同步。
中央 issue 在正式 artifact smoke 與下游 PR 全部完成前保持 open。
