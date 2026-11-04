# P3a F1 修補交接 — 第 1/2 輪，未批准

本輪只修 F1（provider diagnostics → 持久／公開 fault），沒有重置整個 P3a 兩輪預算。**待獨立 SPEC 重查；其 PASS 後才可派品質審查。** 本文不是自批准。

## 修補與安全真相

- 唯一 production 修改：`custom_components/uninus_nutriculture/control.py`。在唯一 fault setter 加 exact closed-code allowlist；未知字串（包含空字串、已知碼加 diagnostic 前綴／後綴）、非字串值一律 `operation_failed`，僅 `None` 清除。不能因為 exception 是 `ServiceValidationError` 就信任其 text。
- 初始化也經同一 setter：舊 options 任意 diagnostic 在 publish 前轉成固定碼並回寫 options，保持 fault latch／automation disabled。既有 `ec_timeout`、`source_invalid`、`stop_unconfirmed` 等受控碼保持原值。
- `nutrient.py`、物理 dispatcher、cleanup／ownership 邏輯、Sensor、Card、既有測試與契約均未改。不是截字串、前綴匹配或 UI 遮蔽。未知 fault 仍阻止 Enable。
- native 反例確認：失敗的設備 ON 之後，nutrient／circulation OFF 都送出且 outputs OFF；最終 state=fault、running=false、master=false，不能稱運行成功，也不能將本例說成停泵失敗。payload 全為明示虛構資料，沒有真秘密外洩之主張。

## Exact source

| 檔案 | SHA256 |
|---|---|
| `custom_components/uninus_nutriculture/control.py` | `7b61e287eb458cf05a7f8d762b211297529f6c24a5a1d38c193e78e7ee41e259` |
| `tests/test_p3_fault_codes.py`（新增） | `b73e4bbccf926f1043f84542d7818248637927a67893151d582d21210e6671f1` |
| shipped Card（未改） | `8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f` |

76 consumed inputs 的逐檔 pre/post SHA：下述 scratch `baseline.json`、各 `*-receipt.json`。四組 `docs/evidence/p3a-f1-*` 有完整 pre-run exact source/test snapshots，不是只有 hash。`verify_f1.py` 實讀 snapshot 與 current bytes：所有 GREEN snapshot 匹配本候選；既有 238 測試未改。

## 真 TDD 與命令

cwd 固定：`D:/UNiNUS Projects/AI project/uninus-nutriculture`。
所有 Python 使用本庫 `.venv/Scripts/python.exe`（實測 native Python 3.14.5）。

```text
.venv/Scripts/python.exe -B tools/evidence.py p3a-f1-01-native-red tests/test_p3_fault_codes.py -q -p no:cacheprovider
.venv/Scripts/python.exe -B tools/evidence.py p3a-f1-02-native-green tests/test_p3_fault_codes.py -q -p no:cacheprovider
.venv/Scripts/python.exe -B tools/evidence.py p3a-f1-03-native-full tests -q -p no:cacheprovider
```

| Gate | 實際結果 |
|---|---|
| RED，production 未改 | exit1：4 failed／3 passed；三種 provider diagnostic 與 legacy native reload 都在 fault 行為斷言真失敗。三個已知碼保留案例即綠，不冒稱 RED |
| 首 GREEN | exit0：7 passed，5 upstream deprecation warnings |
| 最終 native full | exit0：245 passed，5 upstream warnings，pytest 94.16s；原238＋新增7，focused 不重複加總 |
| 原獨立 probe byte-identical rerun | exit0：2 passed，5 upstream warnings |
| shipped Card Node | exit0：10 passed，0 fail/cancel/skip；有 Node experimental runner warning |
| Ruff `check custom_components tests` | exit0，All checks passed |
| Ruff `format --check custom_components tests` | exit0，64 files already formatted |
| shipped dosing bridge | exit0，Chromium156.0.8078.4；midpoint OFF 0.002688s、mix retained、fresh sample completed、page_errors=[] |
| shipped settings bridge | exit0，Apply/Cancel/native conflict/value readback 均真；hardware_calls=[]、page_errors=[] |
| `git diff --check` | exit0；僅既有 manager/sensor CRLF normalization 提示，沒有修改它們 |

## 原 probe 不改內容的新位置重跑

獨占 scratch 根（以下稱 OUT）：
`C:/Users/ivanl/.hermes/cache/scratch/p3a-f1-repair-20261103/`

- 原：`C:/Users/ivanl/.hermes/cache/scratch/p3a-spec-review-20261103/test_review_probe.py`。
- 副本：`OUT/test_review_probe.py`；**兩者 SHA 相同**：`3839c83f3573f7525ffa0ed2f6b46dca887b78c02e8fc7392c3324da93a4c7ad`。
- 已執行 handle：`.venv/Scripts/python.exe -B C:/Users/ivanl/.hermes/cache/scratch/p3a-f1-repair-20261103/run_f1.py probe`。
- 真 inner argv：`.venv/Scripts/python.exe -B tools/evidence.py p3a-f1-04-original-probe -c D:/UNiNUS Projects/AI project/uninus-nutriculture/pyproject.toml C:/Users/ivanl/.hermes/cache/scratch/p3a-f1-repair-20261103/test_review_probe.py -v -s -p no:cacheprovider`（完整逐參數 JSON 見 `probe-receipt.json`）。
- PYTHONPATH 為本次 working backend `tests` 與 repo 根；不是 frozen backend。`OUT=__file__.parent` 保持原樣，新 JSON 落在新 OUT。
- `OUT/provider-counterexample.json` readback：accepted=true；fault_length=16；persisted_equals_provider=false；sensor_equals_provider=false；all_outputs_off=true；running=false；flow_state=fault。原相鄰 held-ACK sample_invalid stop probe 亦通過。
- 所有本輪命令和 exact cwd 在 `OUT/*-receipt.json`，raw stdout 在 `OUT/*.log`；原 probe 的原始失敗 log／JSON 保留不動。**不要重用上述 sealed labels/OUT 覆寫結果；下一個獨立重跑須再建新位置。**

## 完整性驗證

`.venv/Scripts/python.exe -B C:/Users/ivanl/.hermes/cache/scratch/p3a-f1-repair-20261103/verify_f1.py` 真 exit0；`OUT/final-verification.json`：

- frozen manifest SHA 保持 `68bb90f7d1c19439b3e93a41f582b4ac0e6fd0f9845b69e55124e01162ac0ab3`；133 檔逐一匹配 manifest。
- 每個 gate 76 consumed inputs pre=post=baseline；七個 final gates 真 child0。
- 原 review top-level artifacts（含 raw logs、原 counterexample、REPORT、probe）hash 完全不變；本輪獨立副本與原 probe byte-identical。
- 四組 TDD snapshots 逐檔 SHA 自洽，GREEN／full／probe snapshots 與目前 source/test bytes 一致。
- `git diff --cached --name-only` 空；未 stage／commit／push／deploy。
- working `docs/P3A_LOCAL_CHECKPOINT.json` 已是父端 F1 in-progress 狀態，與 frozen 版不同；**本修補沒有修改該檔**，不冒稱所有工作目錄 docs 等於 frozen。

## 修改清單與剩餘

本輪 repo 修改／新增：control.py、新 tests/test_p3_fault_codes.py、本 handoff、四個新 `docs/evidence/p3a-f1-*` 目錄。另有上述獨占 scratch runner／receipts／logs／bridge artifacts 及 `C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-f1-progress.md`。其他原 dirty P3a 檔案不歸本輪新增修改。

沒有更版本、README、共同契約、Card 或酸／獨立 mix。未接原 HA、憑證、真設備；bridge 是隔離 native Core + fake hardware，不是物理設備認證。未做 hosted CI／完整 Chromium30重跑／發布。下一步僅獨立 SPEC 重查 exact successor，通過後由父端派品質；本輪消耗仍為整個 P3a 修補 **1/2**。
