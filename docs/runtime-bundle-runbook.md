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
├── runtime/runtime_verifier.py
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

發行建置環境需提供 Python 3.11+、`build` 與 pip。安裝主機另需 `git`、
GNU `sha256sum` 與支援 JSON output 的 `universal-ctags`；installer 會依
manifest prerequisites 在 staging 前驗證命令存在且可用。Python dependency 版本由
`policy_check/runtime_bundle/constraints.txt` 鎖定；builder 會先檢查每個
`[project].dependencies` 都有一筆 exact `name==version` constraint，下載後再要求
完整 resolved dependency wheel closure 的每一個 distribution/version 都命中該
constraint，未鎖的 transitive wheel 直接 fail-closed。接著正規化 archive
mode/mtime/owner/order，並把 build interpreter、ABI 與 platform 寫入 manifest。
constraint 檔也會包含在 wheel package data，避免 source/wheel 交付內容漂移。

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

`install.sh` 先以 `sha256sum --check --strict` 驗證所有 payload，再確認
Python 3.11+ 與 `venv/ensurepip` 可用，之後才執行 <!-- doc-drift-ignore -->
bundle 內 stdlib manager。Debian/Ubuntu 若顯示 `python3-venv` 診斷，先由系統
管理者安裝與該 Python minor version 相符的 venv 套件；manager 也會在建立
staging 前重做相同能力檢查。manager
與 source engine 共用同一份 stdlib verifier；manager 在同一 runtime root 建 staging venv，
使用 `pip --no-index --find-links` 離線安裝，於暫存 HOME 與獨立 git fixture
執行完整 `PREFLIGHT PASS`，成功後才 rename 成 immutable release。activation
會把 `state.json`、`current`、兩個 stable launcher 與 managed skill link 視為
單一 transaction；任一步失敗都回復先前 snapshot。 <!-- doc-drift-ignore -->
若 host 的 Python major/minor、implementation、ABI 或 platform 不等於 manifest 的
`runtime_compatibility`，會在建立 staging 前 fail-closed；這避免把建置主機的
ABI/platform-specific wheel closure 誤當成任意 Python 3.11+ 通用 bundle。

預設版型：

```text
~/.local/share/paulsha-conventions/
├── releases/<version>/
│   ├── artifact/
│   ├── venv/
│   └── VERIFIED
├── current -> releases/<active-version>
├── bin/policy-preflight
├── bin/policy-runtime-bundle
└── state.json
```

可用 `--root <PATH>`、`XDG_DATA_HOME` 或 `PSC_CONVENTIONS_ROOT` 調整 root，
並可用 `--skill-target <PATH>` 指定受管 skill symlink。部署後的 skill 先從
自身解析後的 `current/artifact/skills/preflight-ci` 實體位置反推 runtime
root，再退回環境變數與預設值，因此 custom `--root` 不要求永久 export。
安裝器不覆寫實體 skill directory，也不接管指向 runtime root 外的既有 symlink。

既有 source checkout 安裝通常會留下實體目錄或指向 repo 的 symlink；首次切換
到 runtime bundle 前必須由操作者明確備份，不可讓 installer 自動接管：

```bash
skill_target="$HOME/.agents/skills/preflight-ci"
skill_backup="$HOME/.agents/skills/preflight-ci.pre-runtime-bundle"
test ! -e "$skill_backup" && test ! -L "$skill_backup"
mv "$skill_target" "$skill_backup"
./install.sh
```

若安裝失敗，在確認 `$skill_target` 仍不存在後用
`mv "$skill_backup" "$skill_target"` 還原。安裝成功並完成 smoke 後才可保留或
人工移除 backup；不要以覆寫、遞迴刪除或自動 adopt 取代這個可逆步驟。

反向從 bundle-managed skill 切回 source checkout 時，普通 `--replace` 會拒絕
覆寫受管 symlink。先確認目前不需切換到另一個 VERIFIED bundle release（需要時
用 `policy-runtime-bundle rollback --version X.Y.Z`），再由 source checkout
明確執行：

```bash
scripts/install-preflight-skill.sh --replace-managed-runtime
```

這只改變 agent skill discovery；不會偽造 `state.json`、移除 active release <!-- doc-drift-ignore -->
或刪除 runtime root。非 active 舊版本仍須用受管 `uninstall --version X.Y.Z`
移除；若要恢復 bundle discovery，重新執行已驗證 bundle 的 install/activate
流程，不要手動改 `current` 或 `state.json`。 <!-- doc-drift-ignore -->

## Exact selection

stable launcher 以自身實體位置決定 runtime root，不接受 ambient
`PSC_CONVENTIONS_ROOT` 改寫既有 launcher 的 ownership；deployed skill 會把其已
定案 root 傳給 launcher。兩者與 source wrapper 都以 Python isolated mode 執行，
不消費 ambient `PYTHONPATH`/`PYTHONHOME`。selector 只從目標 repo 的
`.project-policy.yml`（legacy alias 相容）
讀 exact `policy_version`，要求 `releases/<version>/VERIFIED`、artifact checksum、
manifest、每個 installed wheel 的 distribution version/RECORD payload 全部相符。
`current` 僅供 agent skill discoverability，
不是 engine version fallback。目標版本未安裝時應安裝該精確 release，不應切換
到最新版或較舊版。bootstrap launcher 本身由 active release 提供，但它只負責
載入共用 verifier 與 selector；真正執行的 engine/skill/manifest identity 仍由
目標 repo 的 exact version 決定。

## Rollback and uninstall

部署主機使用 runtime root 下的 stable lifecycle wrapper，不依賴 venv 內含 staging
shebang 的 console script。`activate` 可用 exit 0 修復 current/launcher/skill link；
rollback 不下載、不重建，只 activation 已驗證 release：

```bash
~/.local/share/paulsha-conventions/bin/policy-runtime-bundle \
  activate --version X.Y.Z
~/.local/share/paulsha-conventions/bin/policy-runtime-bundle \
  rollback --version X.Y.Z
```

rollback target 已是 current 時會重驗並修復 managed links，回報成功且不改寫
`previous`。省略 `--version` 時使用 `state.json.previous`。uninstall 必須指定版本，
且拒絕 <!-- doc-drift-ignore -->
移除 active release：

```bash
~/.local/share/paulsha-conventions/bin/policy-runtime-bundle \
  uninstall --version X.Y.Z
```

任何 staging/smoke 失敗都不得改變 `current`。若驗證回報 tamper，可 uninstall
由 `state.json` 明確列管且非 active 的精確 release，<!-- doc-drift-ignore --> 再從已核對外部 SHA-256
的 artifact 重裝。若 tamper 發生在 active release，使用同一份已核對外部
SHA-256 的 bundle 執行：

```bash
./install.sh --force-reinstall
```

manager 會先完成全新 staging/venv/smoke，再原子交換 state-owned 同版 release；
交換成功後才清理 displaced 舊目錄。清理失敗只輸出含精確路徑的 warning，
不把已完成的 state/link 切換誤報為失敗；操作者可在確認路徑是
`releases/.replaced-<version>-<uuid>` 且不是 active/current 後人工清理。不得以
手動刪除 active directory 或整個 runtime root 代替。

## Publication boundary

#48 的正式 artifact 可先作本機/CI evidence，但在 #39 決定公司 authority 前，
不得把任一任意位置宣稱為公司 production registry。#39 仍需明確決定：

- artifact service 與 owner；
- runner/network reachability；
- authentication 與 least-privilege upload/download；
- retention、immutability、audit 與 incident rollback；
- upload automation、canary 與 rollout owner。
