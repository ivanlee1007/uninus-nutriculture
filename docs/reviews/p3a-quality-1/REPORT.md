# Joint P3a 獨立品質／安全審查

## Verdict：REQUEST_CHANGES

2026-11-03。**1 項 Important 阻擋（Q1），未發現已證實 Critical；Minor 無獨立阻擋。** 不改實作、不發布。這是整個 joint P3a slice 品質審查，不是只審 F1，也不是把 Ruff gate 當品質 review。SPEC successor 的 source-bound PASS 仍是有效的先行審查證據；本次發現其未覆蓋的真跨層生命週期缺口，不偽改原第一輪 SPEC 的 REQUEST_CHANGES 歷史。

## Q1 — Important：正常停機後關閉總開關，後端產生 shipped Card 拒收的 schema3，Card 無法再啟用／設定

### 重現（原生 Core + 未改的 fake hardware fixture；再餵真正 shipped JS）

1. 經原生 Options 設置 nutrient-only commissioning，開 master／nutrient Enable。
2. 由實際已註冊 `start_flow` 受理，等待 fake nutrient 實體真正 entered-ON。
3. 原生 `flow_run` OFF，等待正常停止（aborted，兩輸出 OFF）。
4. 原生 `automation_enabled` OFF，drain native 更新。
5. 實際 `sensor.tank_control_status`：`state=flow_state='disabled'`，但 `stage_states.nutrient='disabled'`。
6. 把第5步完整原生 states（沒有手工替換 state／map）載入 snapshot 根目錄 shipped JS，真 Chromium156.0.8078.4：`controls_attached=false`、`master_disabled=true`、`emergency_disabled=true`、`settings_disabled=true`。頁面顯示「狀態缺失或不相容」，直接呼叫同一 shipped invokeControl 也 `calls=[]`；`page_errors=[]`。

這不是瀏覽器 fixture 自造的非法投影，也不是 Mock API／CSS 不可見的誤判。`test_quality_adjacent.py::test_post_run_master_off_keeps_shipped_schema3_reoperable` 在真正原生公開投影斷言失敗；`check_native_capture_ui.py` 用該真捕捉結果再確認實際 consumer 拒絕。

### 根因與位置

- `control.py:400-417`：已停止後 master OFF，把全域 flow_state 設成 disabled；保留 accepted `run_stage='nutrient'` 本身是正確的。
- `sensor.py:182-193`：曾有 nutrient run 時，只轉換 dosing/mixing/waiting_sample/stabilizing 為 running；其他全域 flow_state 原樣投射到 nutrient stage，因此把 disabled 當成 stage state。
- 契約 §4／§8 的 nutrient stage enum 沒有 disabled（亦沒有 uncommissioned）；shipped `uninus-nutriculture-card.js:34-44` 對非法 stage 正確 fail-closed，`update():359-368` 移除 controls。不能把此問題「修」成關閉 consumer 嚴格驗證或捏造樂觀 master ON。

**實際影響：** 使用者執行合理的「停運→關總開關」後，這張已支持 P3a 的 Card 不能再次開 master，也失去 native emergency/reset 與 settings 操作介面，必須改用原生控制介面恢復。這阻擋可重複操作的主要交付路徑，非可選重構。

**安全真相：** 此例 persisted `automation_enabled=false`，`running=false`、`owns_io=false`，nutrient/circulation 真輸出均 OFF；calls 恰為 circulation ON、nutrient ON、nutrient OFF、circulation OFF。沒有證據表明這例停泵失敗、持續加藥或秘密洩漏。問題是合法後端生命週期投影與嚴格 shipped consumer 不相容。

**要求修補：** 在後端維持全域與 stage state 的分離，讓 master OFF 後仍有合法且真實的 nutrient stage 投影；保留 accepted stage 身份／aborted outcome 與 Card fail-closed。永久 regression 必須走上述真 native→shipped JS 路線，並相鄰檢查 fault reset／completed 後設定更新，不只手造合法 browser fixture。父端處理限定修補；本 reviewer 未修改產品。

證據：`post-run-master-off.json`（持久、實際輸出、calls、全 native states）、`post-run-shipped-ui.json`、`probe.log`、`capture-ui-current.log`。前兩個真產品 assertion child 均 exit1。

## 其餘整片審查與相鄰安全執行

已讀 candidate、finish、F1 handoff、契約（§8優先）、GOAL_ALIGNMENT；逐讀 production `control.py`、`nutrient.py`、`control_auth.py`、`control_entity.py`、`control_settings.py`、`dosing_settings.py`、`manager.py`、`config_flow.py`、`services.py`、`number.py`、`sensor.py`、`switch.py`、entry lifecycle 與完整 shipped JS，並對照 native dosing/finish/bounds/samples/io/recovery/settings 測試、fixture、Card browser/workflow。檢查 ON admission／await 後 authority、generation／registry identity、事件撤銷、樣本token與value配對、保守時間額度、hot tightening、normal/acute cleanup差異、pending IO union、pre-entry cancellation、持久 fault／restart、CAS排隊重驗、Options零致動、native map與stale promise／版本 fail-closed。

在目前可達行為（不共享跨entry輸出、獨立mix不支援）下，NutrientStage 的單owner記錄足以表達必要循環所有權；沒有以未使用 DAG／通用資源框架作為阻擋。程式仍有長控制方法與動態屬性，但沒有把可選重構列為必修。

**新鄰界真 PASS：** `test_timestamp_invalid_recovery_during_normal_off_pending_latches` 在正常 stop 已進 nutrient OFF、ACK仍 hold 且 circulation ON 時，送未來 timestamp再同loop恢復原有效token。循環在0.75秒有界等待內收到 native OFF，未等 held ACK釋放；persisted `fault='sample_invalid'`、master false，pending時 `running/owns_io=true`、兩觀測輸出 OFF；ACK釋放後 running/owns_io false，fault仍持久及實際Sensor可見。未 monkeypatch Controller／fixture source／原生 SDK。

F1 exact allowlist 與 legacy初始化路徑已再讀；沒有回歸到信任 provider exception text／prefix，未知空值不清 latch。245 native／11 focused／10 Node 綠證據從先行 SPEC 可驗證 logs及child receipts重用，不重複加總、不冒稱本 reviewer 又跑一輪。修後兩真 bridge 由父端已驗76 consumed-source不變的證據提供；本次新 native-state→shipped consumer 反例揭露既有 bridge 未覆蓋的後續操作。

## 本次執行與命令

所有完整 argv／cwd／child exit／prepost map 見同名 receipts。`PY_BACKEND=D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe`；`PY_CARD=D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe`。以 working venv 當 interpreter，不從 working tree 取產品 source。

| Gate | 真結果 |
|---|---|
| frozen backend cwd：`PY_BACKEND -B -m pytest -c <frozen>/uninus-nutriculture/pyproject.toml <OUT>/test_quality_adjacent.py -v -s -p no:cacheprovider --basetemp <OUT>/pytest-probe` | child1，1 failed／1 passed，5 upstream warnings；4.01秒pytest，非harness failure |
| frozen Card cwd：`PY_CARD -B -m unittest discover -s tests -p test_browser.py -v` | **child0，完整30 tests，26.268秒，Chromium156.0.8078.4** |
| workspace cwd：`PY_CARD -B <OUT>/check_native_capture_ui.py` | child1，真 native capture 被 shipped JS拒絕；不是未裝套件 |
| 先行 SPEC logs查驗 | full245／focused11／Node10的原log SHA符合其報告與receipt child0 |
| final source／receipts驗證 | exit0，135 manifest檔全部匹配；135檔加MANIFEST本身136 inputs pre=post；全部本次 receipt raw-log SHA相符 |

保留的**環境失敗**：第一次 browser完整入口與capture入口誤用 backend venv，均 child1 `ModuleNotFoundError: playwright`，尚未執行產品；`browser.log`／`capture-ui.log`及receipts保留。改用現有Card venv後完整30通過、真正native-capture UI assertion才失敗。沒有install或改source。Python wrapper本身成功不冒充失敗child成功。

### Raw log SHA256

```text
probe.log                 dc4267e6c68969e66a48fd4dac19b2887858dc4315bcf522e0999b0cd349570a
capture-ui-current.log    af1ca156db714ea1b358ec0bec7d66ad0e8860e6e6810f64493714ef5d5ab06a
browser-current.log       2d92d8565984a9650a7aa3283ae4e16e76700f354654892be5f87cab320b0dc3
browser.log               653888b7531b8b5353bdcd921bda5fd5db8e9e3ab88857bcb28a7e3f128f1ec1
capture-ui.log            45bcad5101f8c7e1e124ae67d71a1318baf81dd4688be6b5368ca04d82840414
inherited full.log        1825ee04c7c5f9dfdbf5b523438d268ebba73d6bfc57ad0a0121a2654026e59a
inherited focused-final   197ee3a3854ab11e7062193bda43cd3c89ededcfccf0d963c188666eea163bfc
inherited node.log        075985ba702c94ec305559b0be1343fa35c27cd9d0ea1fbbef42233890ec8fad
```

## Source binding、產物與限制

- 唯讀 exact source：`C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-f1-successor/`。
- MANIFEST SHA256 `1562fbc72421466659e22fd34059e9331ecf1484de267619bb54eca84cae02ff`；135逐檔匹配。
- control.py `7b61e287eb458cf05a7f8d762b211297529f6c24a5a1d38c193e78e7ee41e259`；shipped JS `8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f`。
- `source-pre.json`、`source-post.json`：完整135 source + MANIFEST的136檔 byte hashes相等；`final-verification.json`包含manifest／receipts／繼承log驗證。新native probe還逐一斷言fixture/conftest路徑及實載control/nutrient/sensor bytes等於candidate。
- 新產物全在 `C:/Users/ivanl/.hermes/cache/scratch/p3a-quality-review-20261103/`：本報告/checkpoint、兩審查probe/runner、native JSON／browser JSON、receipts/raw logs、隔離pytest configs與browser幾何/screenshot evidence。候選／原repo實作／既有證據沒有改動，沒有重用sealed probe OUT。另依工作流程要求，在目前 default profile 的 `native-ha-actuator-tdd-checkpoints` 技能加入「真native post-run snapshot→shipped strict consumer」回歸規則；未修改其他profile。
- 本結論非hosted CI／部署／原HA或實機保護認證。僅隔離fixture及本地shipped browser；沒有全站、憑證、原HA網路、外網API、stage/commit/push/tag/release。
- P2已發布；P3a仍未批准／發布。酸、獨立mix與完整四階段可編流程仍待後續，Issue#3不得關閉。整片修補預算仍已用1/2；本次審查不重置也不自動消耗修補輪，由父端決定剩餘限定修補。
