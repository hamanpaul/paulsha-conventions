# Versioned runtime bundle design

## 1. Release identity 與 trust boundary

Bundle 僅能從 clean tagged canonical source 建立。Builder 必須驗證：

- origin 為 `hamanpaul/paulsha-conventions`；
- worktree 無 tracked/untracked/ignored 汙染；
- `HEAD` 是完整 commit SHA，release tag 指向該 commit；
- `VERSION`、wheel metadata 與 tag 版號一致；
- Python dependency closure 依 bundle-owned constraint 鎖版並全部下載成 wheel，
  不保留 sdist。

輸出為 deterministic archive：

```text
paulsha-conventions-vX.Y.Z/
├── wheels/
├── skills/preflight-ci/
├── runtime/runtime_manager.py
├── install.sh
├── manifest.json
└── SHA256SUMS
```

`manifest.json` schema 1 至少包含 policy/skill/package version、canonical repo、
tag、commit、build Python implementation/major-minor/platform compatibility、
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
│   ├── venv/
│   ├── wheels/
│   ├── skills/preflight-ci/
│   ├── manifest.json
│   ├── SHA256SUMS
│   └── VERIFIED
├── current -> releases/<version>
├── bin/policy-preflight
└── state.json
```

`current` 只代表 activation/rollback 狀態，不是 engine selector fallback。
Stable launcher 先從 target repo 解析 canonical/legacy manifest，取得 exact
`policy_version`，再選 `releases/<version>`。要求版本未安裝、未 VERIFIED、
manifest/payload 重驗失敗或 installed distribution version 不符時皆 FAIL。

Launcher 必須清除 `PYTHONPATH`／`PYTHONHOME`、啟用 safe-path/isolated import
語意，並把 selected manifest 明確傳入 `policy_check.preflight`。Preflight
驗證 selected manifest、wheel/skill identity 與實際 imported distribution，
不得 fallback source checkout、workflow cache、default branch 或 `current`。

## 3. Installer、activation、rollback 與 uninstall

`install.sh` 是薄 bootstrap：先用 host checksum tool 驗整個 bundle，再執行已
驗證的 stdlib runtime manager。Manager：

1. 驗 manifest schema、path containment、hash、version 與 wheel closure。
2. 在 runtime root 內建立唯一 staging directory。
3. 建立 venv，以 `--no-index --find-links` 安裝 wheel closure。
4. 在暫存 HOME 與 fixture repo 執行 policy/preflight artifact smoke。
5. 把完整 staging rename 到新的 immutable `releases/<version>`。
6. 以 temp file/symlink + `os.replace` 原子更新 state/current/managed skill link。

失敗不得改變 active state。Rollback 只可切到已安裝且重新驗證通過的 release，
不下載、不 rebuild。Uninstall 不可移除 active release；移除全部時只處理由
state/target containment 證明為 installer 管理的產物。

`~/.agents/skills/preflight-ci` 若是非受管真檔／目錄／外部 symlink，installer
必須拒絕且保留原內容。所有測試使用暫存 HOME/runtime root，不碰真實 user state。

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
- `-P`/isolated import 升格 canonical spec；
- full preflight 所有 conditional steps 都 SKIP 時 FAIL；只有明確
  `--policy-only` 可縮小；
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
