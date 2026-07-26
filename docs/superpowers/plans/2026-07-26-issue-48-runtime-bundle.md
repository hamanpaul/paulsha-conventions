# Issue #48 versioned runtime bundle 實作計畫

## 目標與完成定義

從 v1.0.13 main 建立候選實作，交付不可變 runtime bundle、exact-version
selector、offline atomic installer/rollback、installed engine identity 與
`.project-policy.yml` canonical migration。中央 PR merge 後立即發布 v1.0.14，
從真正 clean annotated tag 建正式 artifact並完成 offline lifecycle smoke；
再逐 repo 合併 10 個下游 manifest migration PR，最後才關閉 issue。

## 不可跨越的 authority

- #48 定義「發布什麼、如何驗證／安裝／選版／回滾」。
- #39 決定「發布到哪個公司 artifact authority、誰擁有認證／retention／audit」。
- 不修改全域 Cortex persona catalog；builder 若因 persona write paths 停下，由主
  整合者記錄並在本 repo 既定 branch 內完成最小實作。
- 不在測試中寫入真實 HOME、`~/.agents/skills` 或現有 runtime root。
- 不覆寫 unmanaged skill target，不執行未驗證 bundle payload。
- 不以 `current`、default branch、workflow cache或其他已安裝版本 fallback。
- 中央 branch 不直接修改下游 repos；遷移在中央 release 後各自開 PR。

## 交付切片

### Slice A — config authority

1. 新增 config resolution metadata與完整雙檔 semantic comparison。
2. legacy-only/dual-identical WARN，dual-conflict/config I/O error FAIL。
3. 本 repo `git mv .paul-project.yml .project-policy.yml`。
4. 更新 current code/scripts/templates/docs；歷史 archive/changelog 保留 provenance。

### Slice B — bundle build/verify

1. 新增 `policy_check.runtime_bundle` package與 CLI。
2. clean origin/tag/status/version/wheel attestation。
3. wheel-only closure、skill/runtime tree hash、manifest schema 1、
   SHA256SUMS、deterministic tar.gz與外部 archive digest。
4. 所有 archive/path/member name 做 traversal/duplicate/symlink 防護。

### Slice C — installer/lifecycle

1. thin checksum-first `install.sh` + stdlib manager。
2. staging venv、offline install、temp HOME fixture smoke、VERIFIED marker。
3. immutable release rename、atomic current/state/managed skill link。
4. offline rollback與 ownership/containment-aware uninstall。

### Slice D — selector/preflight integration

1. stable launcher嚴格解析 target exact policy_version。
2. installed manifest、wheel、skill與 imported package identity交叉驗證。
3. source mode保持現行 canonical checkout contract；deployed mode不讀 `.git`。
4. 收斂 #46 residual：dot-segment/cache containment、`-P` spec、all-SKIP FAIL、
   Python 3.11診斷、config/path/encoding final verdict。

### Slice E — tests/docs/release/fleet

1. unit + synthetic clean-tag integration + offline/tamper/rollback tests。
2. README/skill/gotchas/runbook/MOC/OpenSpec/changelog。
3. Opus 5 exact-head adversarial review與主整合 full gates。
4. merge、v1.0.14 release、正式 clean-tag bundle smoke。
5. 10 個下游 repo各自 rename/pin/agent docs PR與 merge。

## TDD 與驗收命令

Codex Spark candidate 與主整合者至少執行：

```bash
python3 -m pytest -q tests/test_runtime_bundle.py tests/test_config.py \
  tests/test_preflight.py tests/test_preflight_skill.py
python3 -m pytest -q
python3 -m policy_check --repo .
openspec validate --all --strict
/home/paul_chen/.agents/skills/preflight-ci/scripts/preflight.sh --pr <PR>
```

Packaging 環境可用時另跑：

```bash
PACKAGING=1 python3 -m pytest -q tests/test_wheel_offline.py \
  tests/test_runtime_bundle_integration.py
```

候選 integration 必須使用 temp git repo + clean synthetic tag，不得加
`--allow-dirty` production bypass。正式 release 後必須記錄：

- bundle archive path/size/SHA-256；
- manifest policy/tag/commit/wheel/skill hashes；
- fresh HOME offline install與 fixture full preflight；
- two-version selection、missing-version FAIL、tamper FAIL；
- failed upgrade保持 current、offline rollback成功；
- unmanaged skill target保留；
- source checkout/`.git`/network 無依賴。

## Cortex 派工與對抗審查契約

- builder executor/model：`codex` / `gpt-5.3-codex-spark`。
- reviewer executor/model：`claude` / `claude-opus-5`。
- 2026-07-26 最終執行 override：使用者指示取消 Claude gate，改由主整合者
  對 exact head 執行相同判定契約的對抗審查與驗收。
- 主整合者逐項 trace builder diff與測試證據，不因模型回報成功直接接受。
- 首輪 reviewer 契約：未處置缺陷或驗收缺口為 FAIL；已明文承認、影響分析
  有界且列管的 residual 不單獨構成 FAIL，reviewer 若反對必須具體反駁影響分析。
- 預期輸出較大，review只列最多 12 項 BLOCKER/MAJOR，每項一行
  `path:line / failure scenario / required correction`；無則
  `VERDICT: PASS / NONE`。
- reviewer finding由主整合者獨立重現後分類為修正／駁回／列管，再決定下一輪。

## Fleet 邊界

read-only inventory 目前確認 11 個 tracked legacy manifest，扣除本 repo後有
10 個下游：`paulsha-labu`、`paulshaclaw`、`paulsha-hippo`、
`homeclaw-builder`、`custom-skills`、`serialwrap`、`IntelliDbgKit`、
`paulsha-cortex`、`paulsha-patchmud`、`health-integrator`。

`paulshaclaw`、`custom-skills`、`serialwrap` 的主要 checkout 有既有 dirty state，
只能使用隔離 worktree。每個 repo 先讀自身 AGENTS/policy、`git pull --ff-only`、
以 `feature/48-project-policy-manifest`（或符合該 repo 命名規則）工作，通過各自
canonical preflight與 thread-aware review後才 merge。
