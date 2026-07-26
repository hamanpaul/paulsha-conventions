# Issue 48 versioned runtime bundle tasks

1. [x] 建立 runtime-bundle 與 project-policy-manifest OpenSpec contract、plan、
   changelog 與 MOC。
2. [x] 實作 canonical/legacy config resolution、semantic conflict gate、warning 與
   I/O/encoding fail-closed；本 repo `git mv` 到 `.project-policy.yml`。
3. [x] 實作 clean-tag bundle builder、manifest schema、payload/tree hashing、
   wheel-only dependency closure 與 deterministic archive。
4. [x] 實作 thin `install.sh`、stdlib runtime manager、staging/offline venv smoke、
   atomic activation、state、rollback 與 safe uninstall。
5. [x] 實作 stable exact-version selector與 installed-bundle engine identity；
   禁止 fallback `current`／workflow／source。
6. [x] 更新 `preflight-ci` wrapper 的 source/deployed dual mode、Python 3.11
   診斷與 selected release attestation。
7. [x] 收斂 #46 residual：path containment、import identity、all-SKIP verdict、
   config/path/encoding error 與 canonical spec。
8. [x] 更新 active README、skill、bootstrap/help/drift/template consumers，新產物只
   生成 `.project-policy.yml`；歷史 provenance 保留。
9. [x] 補 bundle/config/preflight unit tests、tamper negative tests、synthetic
   clean-tag integration、offline install/upgrade/rollback/uninstall smoke。
10. [x] 主整合者執行 full pytest、policy、OpenSpec、PR-aware canonical preflight
    與 artifact-level evidence review。
11. [x] 依使用者最終指示改由主整合者對 exact candidate head 對抗審查；
    兩項 MAJOR 已以 RED→GREEN 修正，斷電級 availability residual 明文列管 #52。
12. [x] merge 後發布 v1.0.14 annotated tag；從 release commit
    `451c2680fb3a1f977fcbc8007baaa7dbe415cf03` 建正式 clean-tag bundle，
    並在全新暫存 HOME 完成 offline lifecycle smoke。正式 archive SHA-256：
    `2bb24fdd47cbce8162a0094ab95922e7b838f447978cf5cda83dfd27af3e0703`。
13. [x] 10 個下游 legacy repo 均由獨立 PR 遷移、通過 exact local preflight、
    remote checks 與 thread-aware review後以 merge commit 合併：
    [labu #3](https://github.com/hamanpaul/paulsha-labu/pull/3)、
    [paulshaclaw #269](https://github.com/hamanpaul/paulshaclaw/pull/269)、
    [hippo #61](https://github.com/hamanpaul/paulsha-hippo/pull/61)、
    [homeclaw #57](https://github.com/hamanpaul/homeclaw-builder/pull/57)、
    [custom-skills #33](https://github.com/hamanpaul/custom-skills/pull/33)、
    [serialwrap #151](https://github.com/hamanpaul/serialwrap/pull/151)、
    [IntelliDbgKit #14](https://github.com/hamanpaul/IntelliDbgKit/pull/14)、
    [cortex #207](https://github.com/hamanpaul/paulsha-cortex/pull/207)、
    [PatchMUD #10](https://github.com/hamanpaul/paulsha-patchmud/pull/10)、
    [health-integrator #46](https://github.com/hamanpaul/health-integrator/pull/46)。
14. [x] issue #39 已更新為 `[needs_human] OPEN`，保留公司 artifact authority、
    owner、權限、audit/retention 與 rollout/rollback 決策；本 archive closeout
    合併後關閉 issue #48。
