# P3a 第一輪獨立 SPEC 審查

## 結論：REQUEST_CHANGES

2026-11-03；只審凍結的「可操作加養 P3a」兩庫 joint slice，不要求先完成完整 P3。發現 **1 項阻擋：任意設備 provider 例外全文被當成持久／公開 fault code**。這是實際 native 反例，不是依測試總數或父端推論決定 verdict。沒有修改實作，沒有啟動修補輪，沒有發布或接觸原 HA。

## Source binding

- 凍結根：`C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-20261103-224149/`
- `MANIFEST.json` SHA256：`68bb90f7d1c19439b3e93a41f582b4ac0e6fd0f9845b69e55124e01162ac0ab3`。
- **133 檔全部驗證匹配**；每個 child 的 before/after 都相同，最後 post 仍與 pre 完全相同。完整 exact source/test inventory 與每檔 SHA 見 `pre-consumed.json`、各 `*-receipt.json`、`post-consumed.json`，不是只驗挑出的程式。
- backend 原基準 HEAD：`bc3915af2bd42870620d11c396bd53e62f072324`；Card：`c3d4fd8fbde34823ed0cbe581b1e3007f76f0e2c`。這些是 manifest 的來源 metadata，不代表 dirty P3a 已 commit。

主要 finding 路徑（均相對凍結根）：

| 檔案 | SHA256 |
|---|---|
| `uninus-nutriculture/custom_components/uninus_nutriculture/nutrient.py` | `ef58a801a48bcfe8241e45e42e34fa3ea3ee49bc4348c8599eb1dc5ecde75428` |
| `uninus-nutriculture/custom_components/uninus_nutriculture/control.py` | `607abae6ce9ec58585fb0fbe9a2aca2091d047f8d93b12f344e2d55ba792f503` |
| `uninus-nutriculture/custom_components/uninus_nutriculture/sensor.py` | `d2dca234b3e27d1b33d155a791c7156bb509b1d94476f6c34334407b16bc7ae8` |
| `uninus-nutriculture-card/uninus-nutriculture-card.js` | `8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f` |

## F1 — 阻擋：provider diagnostics 穿透 bounded fault-code 契約

**規範依據**：`docs/P2_CONTROL_CONTRACT.md:59` 明定 fault 為「有界 code 字串或 null」；`docs/P3A_NUTRIENT_CONTRACT.md:87-90,204` 延續 P2 既有 attributes。`docs/DEVELOPMENT_SPEC.md:11` 保留敏感來源資訊不得公開的原則。此處不虛構某個既定 64/128 字元上限：問題是 fault 可直接成為無界任意 diagnostic，而不是已定的受控 code。

**可達原始路徑**：

1. 原生 Options fixture commissioning → native Enable → 真 `uninus_nutriculture.start_flow` → native Switch provider。
2. 只替換 **fake 設備 instance** 的 `async_turn_on`，讓本機 provider 丟出含假 token、`example.invalid` URL 與 4096 個填充字元的 `RuntimeError`。未 monkeypatch Native SDK、Controller 或 dispatcher。
3. `nutrient.py:398-402` 的 generic `except Exception` 執行 `self.control.fault = str(err)`。
4. `control.py:165-178` 把字串存入 `entry.options.control.fault`；`sensor.py:199-200` 直接投影；shipped Card `:366` 直接顯示 fault（使用 text，不是 XSS）。

**實測**：`provider-counterexample.json`、`probe.log`：

```json
{"accepted":true,"fault_length":4186,"persisted_equals_provider":true,"sensor_equals_provider":true,"all_outputs_off":true,"running":false,"flow_state":"fault"}
```

`test_provider_exception_is_not_persisted_or_published_as_fault` 真失敗；probe child exit **1**。這證明 arbitrary provider text 可持久化並進入 Sensor/Card 邊界；測試文字完全虛構，**沒有觀察到／宣稱真憑證外洩**。安全 OFF 本例成功，不能將此 finding 說成停泵失敗。

**最小必要修補方向**：native domain 自有的預期錯誤使用受控／有界 code；未知 provider／generic 例外映射固定 fault code，不把任意 `str(err)` 放進持久 options 或公開 attributes。保留原有停止、fault latch 與 ownership 真相。不可只在 Card 截短或截斷字串前綴，因為敏感資訊可能位於開頭。修後應讓同一 probe 與既有 native suite 通過；本審查未代修。

**重現**：

```text
"D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe" -B C:/Users/ivanl/.hermes/cache/scratch/p3a-spec-review-20261103/run_review.py probe
```

原始 run 的 exact argv、cwd、child exit、全 133 檔 before/after 在 `probe-receipt.json`；若再跑，請先改為新的 evidence 目的地，不覆寫此 sealed run。

## 真正執行與覆蓋

| 執行 | 結果 | 原始證據 |
|---|---|---|
| 凍結 backend 完整 `pytest tests` | **child0，238 passed，5 upstream warnings，96.54s** | `native.log`、`native-receipt.json` |
| shipped Card Node contract | **child0，10 passed** | `node.log`、`node-receipt.json` |
| 審查自有 native probes | **child1，1 failed / 1 passed** | `probe.log`、`probe-receipt.json`、`test_review_probe.py` |
| shipped JS → 真隔離 Core native Switch → circulation/pulse/midpoint OFF/mix/new sample/completed | **child0，Chromium156.0.8078.4；page_errors[]；midpoint OFF 0.001519s；IRR false** | `dosing-bridge-retry.log`、`dosing-bridge-retry-receipt.json`、`dosing-bridge-retry/receipt.json`、其 source manifest |

完整 238 是單次完整執行，不與 probe 或其他 focused counts 相加。全套實際包含：Options Save/Cancel/reopen；共同 CAS/revision、排隊授權；initial/inflight selected token；same report/attrs/old-token bursts；send-time pulse/deadline/保守額度；monotone 熱收緊及新 run 放寬；各 ON 後授權/active/identity；actual first-ON weekday；circulation loss；late I/O/unknown quarantine；mixed P2+N 三角色 owner union；phantom runID／receipt64；native 即時 OFF pre-body cancellation；normal stop 先 N OFF-confirm 再 circulation；停止途中急危險／收緊；實際 output event 投影；保留 P1/P2。

**額外鄰近反例（既有斷言之外）通過**：正常 Stop 已送 nutrient OFF、故意 hold 其 native ACK，循環仍 ON；再由真 Core 發 sequence=2 → bool True → 2 的 invalid/recovered burst。循環在 ACK 未釋放時 prompt OFF，`sample_invalid`、master OFF、pending running truth 仍保留。這把既有「token burst」與「正常 stop 途中升級」交叉到一個新可達邊界，未改 SDK。見 `test_normal_stop_sequence_token_invalid_burst_escalates_all_off` 與 `probe.log`。

## Joint 邊界與已讀原證據

已讀 acceptance map、finish handoff、P3a 契約全篇（§8 優先）、DEVELOPMENT_SPEC／GOAL_ALIGNMENT，並追查 nutrient/controller/service/sensor 與 shipped Card group/control 路徑。沒有將歷史 §0 的 refill-only/無 CAS 當成現況。

原 `docs/evidence/p3a-{dosing,settings}-bridge-08-final-source` 僅讀；兩個 receipt 的 JS SHA 一致。另逐項驗證其 source-manifest：各 **70** 個 consumed inputs 都能對應本候選且 SHA 相等，before=after；無未映射或不符。驗證摘要在 `post-consumed.json`。Settings 原 bridge 證明 Apply/Cancel/conflict/value readback 與 hardware_calls[]；**本輪沒有重新跑 settings Chromium bridge**，不能稱為重新執行。Dosing bridge 本輪已獨立重跑。

現行單槽 `NutrientStage` 明確持有 bindings/generation/Context/operations/owns_io，跨 entry sharing 拒絕且獨立 mix 未可運行；在本切片未找出第二合法 circulation owner 的具體可達反例。**不要求為未交付的 workflow 先建 unused generic framework**。酸／獨立 mix／完整可編四階段仍是後續原始需求，不是本輪隱含刪除；不得因此關 Issue#3。

## 限制／環境事件

- 首次 dosing bridge **child1**，原因是 Playwright 預設 `chromium_headless_shell-1194` 不存在；保留 `dosing-bridge.log` 和 receipt。改用本機已存在 `chromium-1248/chrome-win64/chrome.exe` 後另目錄重跑成功，未 install，未修改 source。這與 handoff 所述歷史兩次真 product-projection 失敗不同，不將那些舊失敗重分類為 harness。
- 實測 backend venv Python **3.14.5**；不是依環境摘要猜版本。未重新跑 30-case Chromium frontend suite；Node 與 native/shipped dosing bridge 為本輪直接前端執行證據。完整 static quality/security gate 不由本 SPEC 代替。
- 無 hosted CI、P3 commit/push/tag/release、HACS/deployment、真 MQTT/設備、原 HA 或憑證存取。所有 I/O 是隔離 fake hardware；fixture 的保護聲明不是物理認證。

## Artifacts 與完整性

本輪僅新增／更新本目錄的 runner、probe、checkpoint、report、receipts、raw logs 及其隔離 HA/pytest 暫存；沒有修改凍結候選、原 repo、原測試或歷史 evidence。`run_review.py` 的 wrapper exit0 **不是**測試 PASS；每項 verdict 都用 receipt 的真 `child_exit`。

Raw log SHA256：

```text
native.log               c7e6abf0ad839827d704a1496b89fb5a5ceecf3a1107f3f732202e1dda8d3306
node.log                 3069208bb15233ee1976924f8c7df4f229b4bf7d2b781bfb27a31336ec259c70
probe.log                e036b5ec23fdfd0d89f1e7cc98299dc03997f318e95fe63d8d101489b528720a
dosing-bridge.log        820c75c95806fca0b887c0661a6ebb24e526f16a914f27804e35ddcd10bbe5ee
dosing-bridge-retry.log  c4c6888735bc10ff3bfe3221d7660dcbe550799455b8f03e3b7faa5ae2a3dd17
```

**關閉本次審查：REQUEST_CHANGES，F1 未修。** 238 綠與成功 bridge 不能抵銷獨立反例。修補仍受整個 P3a 的兩輪具體預算約束，不因 probe／候選更名而重置。
