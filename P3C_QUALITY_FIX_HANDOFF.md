# P3C Q1/Q2 修補交接 — 最後授權第4/4輪

## 狀態
**IMPLEMENTED / 本地回歸通過 / 待父端 freeze、affected SPEC 與獨立品質重查；不是批准。**
USER額外授權 receipt `C:/Users/ivanl/.hermes/cache/scratch/p3c-round4-authorization.json`。同slice used=4 / limit=4，不得第五輪、改名重置、發布、部署或關閉 Issue3。

唯一可寫範圍為本隔離backend。未stage/commit/push/install/外網/siteHA/憑證/實機/tag/deploy；Card、根baseline、契約/wire、原兩庫、sealed source與舊evidence未改。SDK僅原庫interpreter，不import原庫custom_components。

## 已完成
### Q1
- accepted row admission所需來源凍結為 `frozenset`，儲存在coordinator的per-owner `required_sources`；不隨已保存的下輪plan變更。
- `source_state` 與當前 `source` 共用健康判斷（available/finite/unit/last_reported freshness）。Controller對active owner先交捕獲event payload給監督者；無效event latch `source_invalid`，同tick restored不能消失。
- flow監督全部active owners、MixStage在validate/dispatch路徑亦檢查。來源失效走原全flow fault/所有owner並行結清，未變pending/unknown、獨立OFF或closed-fault setter。
- 不把condition閾值當continuous numeric control；正常EC .6跨出admission .65仍繼續。condition=null的v5 level-only mix不綁無關ph/ec，原exact probe陽性保留。
- 非mix原本必需level/ph/ec不縮減；同一frozen mechanism適用refill/N/acid，不新增routing或框架。

### Q2
- fresh admission、啟active之前，確認無lease、session start/cutoff為null、每stage無owned IO/pending operation、已知owner binding狀態皆off，才刪除所有共同stage的 `circ_physical_cutoff` / `circ_dispatch_at` 前輪欄位。
- N/acid/mix沿同一fresh admission reset。不改validate cutoff安全檢查；同session最早ON/new lease/retry ON/未確認OFF不會觸發reset。
- 原Q2 nutrient nativeOptions合法C6/F1、真正常完成且OFF、真sleep超過舊C-F、再開新run原probe全部assert保持，已GREEN。永久新case另驗新run_id、新session start在舊cutoff後與新cutoff。
- mix補充case走真第一輪completion/OFF及第二輪新dispatch；**明示logical mix completion與stale-field seam**，不冒稱其等待1800s實體期限；原N另保留真實等待，不能互相替代。

## 真執行與source-bound handles
所有下列path相對本repo：

| run | 真結果 | raw SHA256 |
|---|---|---|
| `quality-round4/red-native` | 6 collected / 4 passed / 2 failed / 0 skipped，child1；Q1/Q2原assert確實失敗 | `a3e2799f6bb0b9cb142b58f61a0cc54a4b546319f33c1a507b1e674a93b7c484` |
| `quality-round4/red-boundaries` | 7 collected / 1 passed / 6 failed，child1；健康閾值對照原已pass，不算RED | `d7b48d9d1605ba4ef0a9cc21e71e9ddc461f7dea7eb17f07ac51e35fca91a757` |
| `quality-round4/green-focused` | 13 passed / 0 skipped，child0；pre-final-format中間checkpoint | `1979970dbcfb9cb1b6893082bbdfd0d38f365adac5230576d1068c27de13fdb9` |
| `quality-round4/final-full` | **339 collected / 339 passed / 0 failed / 0 skipped，child0，174.86s** | `17546cbb1bccceca4c92fd32b951a467b4de6097c949303e4882d998f8d5bf7d` |

每run含 `raw.log`、`receipt.json`、`build/uninus-nutriculture`完整真source/test snapshot；argv/cwd/env/time/child code、source before/after、snapshot before/after、actual imports均在receipt。raw閉檔後hash。RED與GREEN重疊cases不可加總。

Final完整包含原327、永久新增8 cases與fresh build複製的4個原品質probe cases（原heldcircON與twocircowner已在327內，不再加算）。原probe字節：quality `98ef93eab2ab8ff3473adff549e3416428db1502aa42cfc2b4a04e054dd11640`、repeat `411f73296567514affe626b177ae5a17d6a0d1eca96ba1c905187dee6a36d830`；每次copy到新owned build，從未執行舊會覆寫OUT的runner、未xfail/縮assert。

永久case：ph失效、ec錯unit、ph invalid→restored、ec非finite、ph stale、健康EC跨閾值繼續、mix兩個closed runs、N真physical-expiry後新run。原level-only、heldcircON獨立OFF/pending truth、兩circ owners/釋lease不重置cutoff亦在final full通過。R3 nativeOptions/兩revision/namespaceCAS/immutable snapshot/只熱收緊/legacy suites均在final full，未重新設計路由。

SDK：`D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe`，實際 Python3.14.5 / pytest9.2.0（既有Core2026.10.4 SDK）。Card Python兩環境變數明設sibling venv；Chromium固定已提供路徑。build中Card沿manifest frozen bundle `4fd326a406531c601e490393d77e4ac1632a2e72cd1df9bc424aaa1909250e0f`。Final真85個imports全owned、hash match、無mismatch。初始production/tests對frozen manifest完全一致；final source before/after且交接驗hash一致，原198前後一致。

## Modified inventory（不含新增output/cache）
只有四個既有production path相對exact198變更：
- `custom_components/uninus_nutriculture/control.py` final SHA `05d634ebf7876dd5159559edbe8a96b1b23a5ea61c72bbe0931999323883d7d4`
- `custom_components/uninus_nutriculture/flow.py` final SHA `dbc8f599b9a2b7b7c66a7d85e5fb984d8b2ccf9b04f63314a444ac6085223989`
- `custom_components/uninus_nutriculture/flow_settings.py` final SHA `81b681b1d87fa7f59afad14db77fb53db1476885ed754c12f18f5b8173b44e06`
- `custom_components/uninus_nutriculture/mix.py` final SHA `1fac78f56e658e5c3c719d0dcb0159f02553d0712ff8666e3d7d2645e39e14c9`

新增 `tests/test_p3c_quality_lifecycle.py`、`tools/quality_round4.py`、`P3C_QUALITY_FIX_PROGRESS.md`、本handoff及 `quality-round4/` source/raw receipts。fixture reexport保留；未修改既有tests/assertions或tools/evidence.py。

Machine-readable最終摘要：`quality-round4/FINAL.json` SHA **`183c1369ac13cf382a0dc63675d05af51a20a0f080e7e18248f9b65cc828894e`**；含baseline→final inventory、final所有source hash在full receipt、raw/receipt/static handles hashes。

## Static與問題
- Ruff0.17.3：`check custom_components tests tools/quality_round4.py` 真exit0；`format --check`同scope真exit0、85 files already formatted。詳 `quality-round4/static/scoped-{0,1}.log`、FINAL內command與hash。
- 如實額外跑 `check custom_components tests tools` / `format --check ... tools`，歷史tools全scope非綠：含舊工具lint及13個format debt（tools/evidence.py亦未改）。完整原輸出在static/raw-2.log與raw-3.log；不是runtime blocker，不聲稱repo-wide tools全綠，也沒為此擴修。
- 首次 `red-original` setup掃描nativefixtures歷史outputs/venv，terminal150s逾時，未啟pytest、無raw；保留partial build且不當RED。修正runner source掃描範圍，nativefixtures只依frozen manifest複製，不複製歷史runtime。沒有approval拒絕/approval逾時，沒有繞過授權。
- Native共5個既有SDK deprecation warnings（aiohttp/backoff）；無skip，原raw未修飾。

## 剩餘／禁止推論
- 父端須freeze新source後做affected SPEC及獨立品質；必要fresh S5雙向join由父端安排。本修補不冒稱舊fresh1的13 requests覆蓋新bytes。
- Node13/browser38/UI320px64 controls/trusted typing舊證據僅可由父端驗hash後compose，不是本輪新跑。
- ephemeral runtime `.storage`/auth不列交接artifacts、不打包臨時capabilities。
- 無siteHA、硬體或外部物理cutoff認證；沒有窮舉矩陣。若新產品blocker僅保存升級，不自開第五輪。

## Owned workflow lesson（不寫profile skill）
先讀authorizing receipt與exactmanifest、原native反例byte-copy到全新owned build→原assert真RED及相鄰陽性→最小共同source/closure機制→永久邊界→format凍結source→full真child/actual-imports核對→所有raw關檔hash/舊198不變→交父端獨立freeze+SPEC+quality。source掃描嚴禁遞迴歷史nativefixtures/runtime/venv；複製fixture僅依manifest。
