# Issue 42：Release ledger tag SHA 修正計畫

**Issue:** `hamanpaul/paulsha-conventions#42`

**Builder boundary:** 只修改 release ledger、對應自我檢測、CI checkout 深度、必要文件與本 issue changelog fragment。

## Live evidence

`RELEASES.md` 的 `1.0.5` 至 `1.0.12` 使用 feature PR merge commit，而 annotated tag 解引用後實際指向下列 release commits：

| version | authoritative tag commit |
| --- | --- |
| 1.0.5 | `484f963adddf384d30fa0dd85aef35dddf822ee7` |
| 1.0.6 | `572d364ef8101bbcf3c08548ddf059e46ef8d0fb` |
| 1.0.7 | `a35ef15acec1022bcbe721d81bbd461945588369` |
| 1.0.8 | `8337bea081422302707a39d2b03fb4eded132dda` |
| 1.0.9 | `376cc3c5dabcccae8a97e7e7129591daa7f539ed` |
| 1.0.10 | `ee87a6d5ed91209d944934a2559f4f2622fd1ac2` |
| 1.0.11 | `1d653c97c8c8c3409c61576d4f306118d476094e` |
| 1.0.12 | `25d31e021e45c2991c718923ae2dd49bc3d0b542` |

`1.0.2` 至 `1.0.4` 已與 tag commit 一致；`1.0.0`、`1.0.1` 沒有 tag，維持事後考據值。

## 實作步驟

1. 先新增 `tests/test_releases_ledger.py`：
   - 解析 `RELEASES.md` tagged rows。
   - 對每列執行 `git rev-parse <tag>^{commit}`，斷言等於表列 SHA。
   - 讀取 `<tag>:VERSION`，斷言等於表列 `policy_version`。
   - 明確忽略無 tag 的 `1.0.0`、`1.0.1`，不可把 `—` 當 ref。
2. 將 `RELEASES.md` 的 `1.0.5` 至 `1.0.12` 全部改為 authoritative tag commit。
3. 將升版 SOP 改為：
   - 先以 `git rev-list -n1 vX.Y.Z` 取得完整 commit SHA；
   - 再與 ledger 交叉核對；
   - workflow 仍 pin 完整 40 字元 SHA，不能改成 tag，因 reusable workflow 明確拒絕非 SHA。
4. `.github/workflows/self-test.yml` 的主 pytest checkout 改為 `fetch-depth: 0`，確保 CI 有 tag history 可跑自我檢測；doc-drift shallow checkout job 維持原樣。
5. 新增 `changelog.d/42-release-ledger-tag-sha.md`，`type: fix`、`issue: 42`。

## 不在此 slice

- 不改歷史 tag。
- 不 force-move tag。
- 不修改 `VERSION` 或做 release bump；batch 整合完成後由主 agent統一 release。
- 不把 reusable workflow 改成接受 tag。

## 驗收

- `python3 -m pytest -q tests/test_releases_ledger.py`
- `python3 -m pytest -q`
- `python3 -m policy_check --repo . --pr-title "fix(release): 修正 release ledger tag SHA" --pr-body "Fixes #42" --pr-base-ref feature/42-46-open-issues-batch --pr-head-ref feature/42-release-ledger`
- `RELEASES.md` 每個 tagged row 的 SHA、tag 與 tag 內 `VERSION` 三者一致。
- Foreign reviewer 無未處置 critical/important finding。

## 對抗審查判定

- 未處置的實作缺陷或驗收缺口 ⇒ FAIL。
- 已明文承認、影響分析有界且在文件列管的殘餘風險，不單獨構成 FAIL；reviewer 若不接受，必須具體反駁其影響分析。
