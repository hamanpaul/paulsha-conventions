# Issue 48 versioned runtime bundle tasks

1. [ ] 建立 runtime-bundle 與 project-policy-manifest OpenSpec contract、plan、
   changelog 與 MOC。
2. [ ] 實作 canonical/legacy config resolution、semantic conflict gate、warning 與
   I/O/encoding fail-closed；本 repo `git mv` 到 `.project-policy.yml`。
3. [ ] 實作 clean-tag bundle builder、manifest schema、payload/tree hashing、
   wheel-only dependency closure 與 deterministic archive。
4. [ ] 實作 thin `install.sh`、stdlib runtime manager、staging/offline venv smoke、
   atomic activation、state、rollback 與 safe uninstall。
5. [ ] 實作 stable exact-version selector與 installed-bundle engine identity；
   禁止 fallback `current`／workflow／source。
6. [ ] 更新 `preflight-ci` wrapper 的 source/deployed dual mode、Python 3.11
   診斷與 selected release attestation。
7. [ ] 收斂 #46 residual：path containment、import identity、all-SKIP verdict、
   config/path/encoding error 與 canonical spec。
8. [ ] 更新 active README、skill、bootstrap/help/drift/template consumers，新產物只
   生成 `.project-policy.yml`；歷史 provenance 保留。
9. [ ] 補 bundle/config/preflight unit tests、tamper negative tests、synthetic
   clean-tag integration、offline install/upgrade/rollback/uninstall smoke。
10. [ ] 主整合者執行 full pytest、policy、OpenSpec、PR-aware canonical preflight
    與 artifact-level evidence review。
11. [ ] Claude Opus 5 對 exact candidate head 對抗審查；未處置缺陷/驗收缺口 FAIL，
    有界且明文列管 residual 不單獨 FAIL。
12. [ ] merge 後發布 patch/tag，從正式 clean tag 建 bundle並在全新暫存 HOME
    完成 offline lifecycle smoke。
13. [ ] 對 10 個下游 legacy repo 分別開遷移 PR，驗證後 merge。
14. [ ] 更新/關閉 issue 48；更新 issue 39，明確保留 artifact authority 決策。
