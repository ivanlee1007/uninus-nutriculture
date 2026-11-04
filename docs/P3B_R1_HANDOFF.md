# P3b R1 第一次限定修補（1/2）交接

**狀態：修補及回歸完成，待獨立 SPEC 重查；不是自批准，不發布。** P3a 不重開，P3c 完整可編流程仍未完成，Issue3 不關。

## 變更與根因

唯一 production 變更 `custom_components/uninus_nutriculture/control.py`：
- emergency N arm 的 owns_io 判斷及 stage 明確使用 `self.nutrient_stage`，不以 active execution_stage 代理。
- `nutrient_dispatch(..., stage=None)` 的 legacy N 預設同樣明確使用 nutrient_stage；酸/mix 原本傳入 explicit stage，不改其 owner。第一輪只有 arm 修補仍 FAIL，證明只改 arm 不足；這次失敗完整保留。
- 沿用原 Registry resolve、stage operations、late-ON settled/cleanup、fault 時 concurrent OFF、正常 dose OFF→circ OFF、internal Context(parent_id)；沒有新 generic framework，沒有改 nutrient.py / schema / parser / contract / demo / Card JS。

永久 `tests/test_p3b_emergency_owners.py`：真 Options save all commission，先透過原生 Number 設 mix_duration=1 min，四個不同 Registry physical roles。singleEligible acid 兩 held（acid/circulation）及鄰近 singleEligible mix held N。外部 ON 的 N/refill/foreign；mix case 酸亦外部 ON。hold 未放前已驗各 known role OFF；foreign 持續 ON、零 OFF；各 owner pending/owns_io 獨立斷言，共用 circ 的三 owner 可同時 pending。OFF Context 無 user_id 且 parent_id 保留起點。Teardown 在產品成功斷言之後，明示不當成功證據。Native SDK 無 monkeypatch，只 fake-device barriers。

## 精確 source SHA256

- control 原：`00323483a4befbe602a0b6dd695fa7946565701907927e5e0683514cca917917`
- control 修後：`3e98f95da22cd11ca806458120d4cdf77ec1f07b851d48357638f26e8804f7f7`
- 新永久 test：`01293313cde1e43235e65a57d89ae071ce5afc31c7681a704ff456d995fc82f3`
- nutrient 未變：`4c7fbaa5ab8d6e330d3d089257882dd0797648e5ed389a5c5e838f2a1acfa918`
- contract 未變：`77df237d88acbf313327c6c959b54de4e161b8f8cc16a287322a30f570d318b7`
- shipped JS 未變：`4d6615afa83d736677fcf8f8791c695dcbd92b22b0e9d9aeeb731e2d75ab41bd`

## 執行證據

共同 OUT：`C:/Users/ivanl/.hermes/cache/scratch/p3b-r1-repair-1`。每 run 保存當時 source/test byte snapshots、argv/cwd/env、raw.log、實際 child exit、log hash、frozen pre/post。借原 backend interpreter/SDK，不改 venv；Python 3.14.5 / pytest 9.2.0。

| run 子目錄 | native child | raw.log SHA256 |
|---|---|---|
| p3b-r1-red | 1；3 FAIL，兩 acid 直接漏 N OFF，mix 缺 N pending truth | c910b9e68296d93aa9767a15992d450f62f1181dce9e2b309e6bc0ed1c9db4c6 |
| p3b-r1-green | 1；arm-only 仍 3 FAIL，不稱 GREEN | 88268966ca86d994882f58eb52fd5e0692121757b9d6f14d58321944aaf8173d |
| p3b-r1-green-2 | 0；3 PASS | 8956fa74ebc8929435f64b8406befd7472d69f1317b6da6d9d1cb4aaa5d5a12b |
| p3b-r1-original-probe | 0；6 PASS（原兩 FAIL + 原四 PASS） | 778d87e4264383776b7426bb34296223a20f35fc5bd9fa34cc4d1d926e2eeef8 |
| p3b-r1-full-native | 0；290 PASS / 0 skip | 4de8f1a275683136b298780b8e8f18234a187c8e5c68ce8116f20dfef65fd365 |
| p3b-r1-full-bound | 0；290 PASS / 0 skip | 15ae769f206386316d0faff732af1f64335d01f27f5f65848023d54a3b4971fb |

所有 run 為 5 upstream deprecation warnings。兩次完整 suite 是原287+新增3；不與 focused/probe 相加。

最終 full-bound `run.json` SHA：`002cdfee7d425d9aea673e45f01ac2e79892d44d5f4d36744faea9332775cde6`。
`source-binding.json` SHA：`c05e3d8cac6c162c4c815517adcc285d491f0be953850b6cac0f7fa8ddca66f1`，290 distinct case records，實際 imported control path 為 isolated-development，hash 如上。read-only plugin 不改 SDK；清單表示每 case 後實際 imported modules，不假稱每 module/每 broad snapshot file 都在每 case 執行。

各 run frozen pre.json/post.json SHA 相同：`9b525d4d98d5592c53431edeaa99af16255bd4fdb29ada6cdc85e33eabaa64c6`（candidate 與原 SPEC evidence 的完整實體檔 inventories，candidate 169 tracked + MANIFEST 本身）。Candidate MANIFEST 仍 `573604ef8a815c1a10dac905f9004e214d706597503040b8999c38fec42ee635`。原 REPORT 仍 `a8188e8d2699bb5abb4a558baa9f8396c27d7dbeb0469ebd94f9437866fb17b1`。

## 原 SPEC probe 不弱化

`original/test_review_native.py` byte exact archive SHA `1452c00c7a0090e06e7adbe79b76d190bcf0e933d12ea076cd3427029932aa86`。執行副本只改 ROOT 指向隔離 source、OUT 指向新 probe-output；assertions 完全不變，overlay SHA `64c0a17175f79bc7245a41688c83f137657c7bc298a22b85003fbda488a0dabc`，`probe-overlay.json` 記錄可逆比對。舊 JSON/log 未覆寫。

兩 held 皆 N_on=false、foreign_on=true。acid held：N owner 已 settle false、acid true、mix false、aggregate running true；circ held：三 stage owns_io true、aggregate running true。原 hot tighten/relax 與 C-F helper-clock equality PASS（保留 domain seam 界線，不宣稱實等）。

原 probe run 的兩 role terminal wire acid/mix 各實跑 aborted/fault/completed，六 browser child 由原 assertions 檢查 exit0、Apply/Enable native replay 零額外硬體 calls。完整 bound run 又實跑相同六 terminal captures，另有 v4 wire，一共可解析7 browser receipts，page_errors 全空。Chromium 156.0.8078.4（installed chromium-1248）；P3B_CARD_PYTHON 指向原 sibling Card venv，實際 shipped JS 為隔離 sibling 檔案，receipt hash 已驗。

## 重用／未覆蓋／交接

- Card JS 與既有 Card test inputs 無改，既有 Node12/browser33 依父端 actual-consumed 驗證重用；本輪不重新宣稱全 browser matrix。原 SPEC v4 PendingBrowser 已通過，這輪沒有重造；hot/C-F 原 probe 則已重跑。
- 僅 native fake-device / offline Chromium capture-and-replay，未連原 HA、憑證、實機或外網；不宣稱實機安全驗收。
- 改/新增檔：control.py、test_p3b_emergency_owners.py、docs/P3B_R1_PROGRESS.md、本 handoff；另 OUT 下新獨立證據與只讀 runner/helpers。原庫/frozen/歷史 logs 不改，無 stage/commit/push/tag/deploy/install。
- 待父端凍結修補候選並送獨立 SPEC 重查；SPEC PASS 前不進品質 gate、不發布。
