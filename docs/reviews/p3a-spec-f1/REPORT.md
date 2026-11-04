# P3a F1 獨立 SPEC 重查

## 結論：PASS（exact successor 的 joint P3a SPEC）

2026-11-03。原 F1 已由真正 native 反例重跑確認封閉，另以空 RuntimeError／無指定訊息 Unauthorized() 與 pending native OFF ACK 交叉驗證故障鎖定及 ownership 真相。沒有新增阻擋。**此結論是本次 F1 判斷與第一輪未變範圍審查的組合，不是宣稱第一輪 SPEC 曾 PASS。** 第一輪仍保持 REQUEST_CHANGES；原報告、反例與 raw evidence 未覆寫。

本輪不修產品碼，不自批准品質／發布。整個 P3a 修補預算維持已用 **1/2**，重查沒有重置或另開修補輪。父端可依流程再派獨立品質審查。

## Source binding 與 unchanged scope

- Exact root：`C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-f1-successor/`。
- `MANIFEST.json` SHA256：`1562fbc72421466659e22fd34059e9331ecf1484de267619bb54eca84cae02ff`。
- **135 檔逐檔符合 manifest；每個 child pre/post 均一致**。原 snapshot 133 檔亦逐檔驗證，manifest SHA 保持 `68bb90f7d1c19439b3e93a41f582b4ac0e6fd0f9845b69e55124e01162ac0ab3`。
- `delta.json` 程式化比對確認：原133中只有 `control.py` 與 checkpoint metadata 變動；新增 `tests/test_p3_fault_codes.py` 與 `docs/P3A_F1_HANDOFF.md`。沒有移除。Card、其測試、其他 production、原238測試、契約全未變。
- `control.py` SHA：`7b61e287eb458cf05a7f8d762b211297529f6c24a5a1d38c193e78e7ee41e259`；新7-case測試 SHA：`b73e4bbccf926f1043f84542d7818248637927a67893151d582d21210e6671f1`。
- Exact **76 consumed inputs**（backend custom_components/tests、pyproject、requirements、evidence/兩橋 runner、shipped JS/Node test）的逐檔 SHA 見 `final-verification.json.covered_consumed_inputs`；其包含於完整135 manifest pre/post inventories。命令、cwd、PYTHONPATH、child exit、原始 log SHA 與兩快照／歷史證據 inventories 均在各 receipt，不只驗修改檔。

本次已讀 successor F1 handoff、candidate acceptance map、契約 §8、唯一 fault setter／初始化、所有 fault assignments、原新測試與 fixture，並以 unified diff 確認 production 修改只有 closed-code 邊界。第一輪已讀完整切片、執行238 native／Node10／真 dosing bridge、核對 settings bridge 及相鄰 stop/token probe的未變範圍，依 byte identity 繼承其 SPEC 覆蓋；**本輪沒有重跑 Chromium bridge**。父端提供的修後兩真 bridge、static gates不冒稱本 reviewer 的直接執行。

## F1 封閉判斷

`control.py:18-51,63-67,206-223` 用 exact closed allowlist；只接受精確普通字串且列入集合。未知／空字串／非字串都映射固定 `operation_failed`，僅明確 `None` 清除。初始化將舊 persisted fault 經同一 setter 正規化並回寫 options，不能在 restart 再公開舊 diagnostic。既有受控碼保留原值。

這不是截斷、前綴匹配、UI遮蔽或信任 exception baseclass。`nutrient.py:400-402` 雖仍使用 `str(err)`，但唯一 setter 不再允許任意內容持久化／公開。未改 dispatcher、cleanup、Sensor 或 Card。

### 同一原反例（byte-identical）

原 `test_review_probe.py` 複製至本獨占 OUT，SHA 保持 `3839c83f3573f7525ffa0ed2f6b46dca887b78c02e8fc7392c3324da93a4c7ad`。其 OUT 仍取 `__file__.parent`，沒有從舊位置執行或寫回舊 evidence。

真 Options commissioning → Enable → native start_flow → fake設備 instance ON 丟出原4186字元虛構 diagnostic，結果：accepted=true；fault_length=16；persisted_equals_provider=false；sensor_equals_provider=false；all_outputs_off=true；running=false；flow_state=fault。原 probe 的 stop/token held-ACK 相鄰例亦通過。見 `provider-counterexample.json`、`focused-final.log`。

### 本 reviewer 新鄰界：空 diagnostic／無指定訊息授權例外 + OFF pending

`test_adjacent.py` 只替換 fake設備 instance 的 ON；不替換 Controller、原生 dispatcher 或 SDK。兩例分別 `RuntimeError()` 與 `Unauthorized()`，並 hold nutrient OFF ACK：

- 真 native nutrient／circulation OFF 都送出且輸出皆OFF；ACK未釋放時 **running=true、owns_io=true、master=false**，沒有把觀測 OFF 冒稱 I/O 全結清。
- 持久 options 與實際 Sensor 都為 `operation_failed`；原生重新 Enable 拒絕 `fault_latched`。
- ACK釋放後 running=false、master=false，仍是 fault；兩輸出OFF且 persisted automation_enabled=false。
- 明確確認 fixture／conftest 來自 successor，實際載入 control.py bytes SHA 與 successor 相等。不是指向 working 或舊 source。

Core 的 `Unauthorized()` 雖未提供訊息，實際 str 為 `Unauthorized`，不是空字串；它同樣不屬 allowlist，仍鎖故障。見 `adjacent-RuntimeError.json`、`adjacent-Unauthorized.json`。本鄰界加強的是未知 fault 不可意外清 latch，以及 pending truth，不宣稱模擬了所有真實授權撤銷路線。

## 直接執行結果

使用既有 working backend venv **Python3.14.5** 作 interpreter；cwd、config、tests、PYTHONPATH 及 HA fixture複製源一律 successor。所有 HA／pytest暫存限制在本 OUT；沒有 install。

| Gate | 真 child 結果 | 證據 |
|---|---|---|
| successor完整 native `pytest tests` | **exit0，245 passed，5 upstream warnings，96.95s** | `full.log`、`full-receipt.json` |
| new7 + 原probe2 + reviewer鄰界2 | **exit0，11 passed，5 warnings，4.08s** | `focused-final.log`、`focused-final-receipt.json` |
| shipped Card Node | **exit0，10 passed，0 fail/skip** | `node.log`、`node-receipt.json` |
| final source/evidence驗證 | **exit0；135 successor／133 prior匹配；歷史 top-level artifacts未變** | `verify_final.py`、`final-verification.json` |

Focused7包含在245內，重跑及probe不累加成另一個產品測試總數。

### 保留的 harness 失敗

首次 focused **child1：10 passed/1 failed**，新7＋原2＋空RuntimeError均綠；reviewer誤以為 `str(Unauthorized())==''`，在安裝fake provider及start之前即失敗。第二次 focused 同為 **child1：10 passed/1 failed**，reviewer又誤設 `error.args` 應空，而實際Core自填 `('Unauthorized',)`。兩者都是新 probe 前置假設錯誤，不是產品反例；完整 failed log/receipt、`test_adjacent_v1.py`／`v2.py` 與 runner版本保留，未把它們改標 PASS。修正的只有 reviewer harness，最後原生行為斷言完整執行通過，各次 basetemp 分離。

Raw log SHA256：

```text
focused.log        804ee58eab5219ccb7bb308a29137247f31e6616c868f1fd0fb5005341a8a0ad
focused-retry.log  eda17c70baecd9f2535a5f0d188bf07a47aba3218297eab9556e21439c21d843
focused-final.log  197ee3a3854ab11e7062193bda43cd3c89ededcfccf0d963c188666eea163bfc
full.log           1825ee04c7c5f9dfdbf5b523438d268ebba73d6bfc57ad0a0121a2654026e59a
node.log           075985ba702c94ec305559b0be1343fa35c27cd9d0ea1fbbef42233890ec8fad
```

## 限制與交付

**PASS 僅是本 exact source 的 joint P3a SPEC gate。** 不代表品質／安全審查完成、hosted CI、完整Chromium30重跑、原HA／實機、物理保護認證或發布批准。酸、獨立mix、完整可編四階段仍未交付，不得關 Issue#3。

本輪僅建立本 OUT 的 runner/probes、checkpoint/report、pre/post inventories、receipts/raw logs、隔離native configs；所有候選source、原repo、原審查／repair artifacts唯讀，未stage/commit/push/deploy或存取現場憑證。另將已證實的 Unauthorized預設文案／pending-ACK probe注意事項記入已載入的本profile fault regression技能，未修改其他profile。
