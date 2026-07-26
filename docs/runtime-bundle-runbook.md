# Runtime bundle runbook

本文件描述 #48 交付的 production runtime unit。它回答「如何 build、驗證、
安裝、精確選版與回滾」；公司 artifact registry、上傳權限、retention、audit
與 canary owner 仍由 #39 決策。

## Artifact contract

正式 bundle 只能由 canonical origin 的 clean annotated tag 建立。builder
交叉驗證 `VERSION`、tag、HEAD、wheel metadata 與 release manifest，下載
wheel-only Python dependency closure，產生 deterministic `tar.gz` 與外部
archive SHA-256。

解包後版型：

```text
paulsha-conventions-vX.Y.Z/
├── wheels/
├── skills/preflight-ci/
├── runtime/runtime_manager.py
├── install.sh
├── manifest.json
└── SHA256SUMS
```

`SHA256SUMS` 是封閉檔案集合：缺檔、多檔、duplicate name、dot segment、
traversal、symlink 或任何 payload hash 不一致都 fail-closed。`manifest.json` <!-- doc-drift-ignore -->
再交叉驗證 policy/package/skill/tag/commit/wheel/skill/runtime identity。
發行來源真實性由外部 archive digest 與 #39 未來選定的 artifact authority
承擔；checksum 不等於 registry authentication。

上述 legacy alias 與 bundle root 的 `install.sh`、`manifest.json`、`state.json` <!-- doc-drift-ignore -->
是相容／artifact contract 名稱，不是 source repo root 檔案；同一行使用既有
`doc-drift-ignore` marker 做局部列管，不涵蓋其他任意懸空路徑。

## Build and verify

輸出目錄應位於 source repo 外，且不得預先存在同名 archive：

```bash
policy-runtime-bundle build \
  --repo /path/paulsha-conventions \
  --tag vX.Y.Z \
  --output-dir /path/release-output
```

在任何 Python 3.11+ 主機以外部 digest 驗證 archive 與 member，再原子解包：

```bash
policy-runtime-bundle extract \
  --archive /path/paulsha-conventions-vX.Y.Z.tar.gz \
  --sha256 <published-archive-sha256> \
  --output-dir /safe/staging
```

`extract` 拒絕 digest mismatch、duplicate/traversal/dot-segment member、
symlink/hardlink/device、多重 root 與已存在 destination；解包後再次執行完整
bundle payload 驗證。已安全解包的目錄仍可另跑
`policy-runtime-bundle verify --bundle <dir>`。

## Install and state

`install.sh` 先以 `sha256sum --check --strict` 驗證所有 payload，之後才執行 <!-- doc-drift-ignore -->
bundle 內 stdlib manager。manager 在同一 runtime root 建 staging venv，
使用 `pip --no-index --find-links` 離線安裝，於暫存 HOME 與獨立 git fixture
執行完整 `PREFLIGHT PASS`，成功後才 rename 成 immutable release 並原子切換
`current` 與 `state.json`。 <!-- doc-drift-ignore -->

預設版型：

```text
~/.local/share/paulsha-conventions/
├── releases/<version>/
│   ├── artifact/
│   ├── venv/
│   └── VERIFIED
├── current -> releases/<active-version>
├── bin/policy-preflight
└── state.json
```

可用 `XDG_DATA_HOME` 或 `PSC_CONVENTIONS_ROOT` 調整 root。安裝器不覆寫實體
skill directory，也不接管指向 runtime root 外的既有 symlink。

## Exact selection

stable launcher 只從目標 repo 的 `.project-policy.yml`（legacy alias 相容）
讀 exact `policy_version`，要求 `releases/<version>/VERIFIED`、artifact checksum、
manifest、venv distribution 全部相符。`current` 僅供 agent skill discoverability，
不是 engine version fallback。目標版本未安裝時應安裝該精確 release，不應切換
到最新版或較舊版。

## Rollback and uninstall

rollback 不下載、不重建，只 activation 已驗證 release：

```bash
policy-runtime-bundle rollback --version X.Y.Z
```

省略 `--version` 時使用 `state.json.previous`。uninstall 必須指定版本，且拒絕 <!-- doc-drift-ignore -->
移除 active release：

```bash
policy-runtime-bundle uninstall --version X.Y.Z
```

任何 staging/smoke 失敗都不得改變 `current`。若驗證回報 tamper，隔離該精確
release 或 bundle，從已核對外部 SHA-256 的 artifact 重裝；不要刪除整個
runtime root。

## Publication boundary

#48 的正式 artifact 可先作本機/CI evidence，但在 #39 決定公司 authority 前，
不得把任一任意位置宣稱為公司 production registry。#39 仍需明確決定：

- artifact service 與 owner；
- runner/network reachability；
- authentication 與 least-privilege upload/download；
- retention、immutability、audit 與 incident rollback；
- upload automation、canary 與 rollout owner。
