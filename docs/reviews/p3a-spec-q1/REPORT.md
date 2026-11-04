# P3a Q1 exact successor — affected SPEC 重查

## Verdict：PASS（joint P3a SPEC；不是品質或發布批准）

Q1 的真 native 後續生命週期／shipped strict consumer 不相容已封閉，未發現新 SPEC 阻擋。本判斷組合本次 affected 檢查與先前 F1 joint SPEC 報告中 byte-identical 未變範圍，不把先前 REQUEST_CHANGES 歷史改成 PASS。原品質 Q1 報告也保持原樣；父端仍需派獨立 affected 品質重查，批准前不可發布。

修補預算 **2/2 已用盡**；本 reviewer 沒有修產品、沒有第三輪。完整 P3 酸、standalone mix、可編排流程未完成，Issue #3 不可關閉。

## Exact source 與 unchanged 範圍

- Snapshot：`C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-q1-successor/`。
- MANIFEST SHA256：`9dd070aa362481bcbda54c8e20a392bbe3875fa4d4ecbe7bb743fe8b3a17d6f0`。
- **138 檔逐檔符合 manifest，所有本次 child 前後一致**。MANIFEST 本身另驗 SHA；`source-pre.json`、`source-post.json` 包含138檔與manifest，並封存 prior135 及原 quality／Q1 repair／F1 SPEC 目錄檔案 hash，前後全等。
- 程式化 delta：prior135 沒有移除；僅兩 production `nutrient.py`、`sensor.py` 及 checkpoint metadata 改變，新增 Q1 handoff、新4-case test、新 postrun checker。`control.py`／F1 allowlist、Card 全庫、契約、舊 tests 和其他 production 均相等。
- `control.py` SHA：`7b61e287eb458cf05a7f8d762b211297529f6c24a5a1d38c193e78e7ee41e259`；shipped JS SHA：`8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f`。
- joint 未變範圍沿用 `C:/Users/ivanl/.hermes/cache/scratch/p3a-spec-f1-recheck/REPORT.md` 的 source-bound SPEC 覆蓋，限定改變的 outcome／projection 與相鄰 pending ownership 由本次重新實跑。不是重做完整品質審查，也不是只審兩行就宣稱整片首度驗證。

已讀 Q1 handoff、review candidate、contract（§8優先）、原 Q1 品質報告、先前 F1 SPEC 報告；比對兩 production unified diff，追 accepted start、run／cleanup／stop、Controller running union／Enable／reset 及 Sensor 投影。

## affected SPEC 判斷

`NutrientStage.result` 初始化 None，真正受理新 run 才清成 None；cleanup 在 `owns_io=false` 後才保存當次實際 flow terminal。Sensor 僅在無 owned I/O 且 outcome 已存在時用這個歷史 outcome，其餘保留原 active 狀態與 dosing/mixing/waiting_sample/stabilizing→running 映射。

因此 master OFF 可以合法令 root/state/flow_state 為 disabled，fault reset 可以令全域不再帶 fault，但 accepted stage 的 aborted／fault／completed 仍合法且真實；不清 accepted run_stage，不由目前 Enable 推測歷史，也不放寬 shipped strict enum。pending I/O 不會被已觀測 OFF 冒稱完成。

### 真 native → shipped consumer → native replay

本 reviewer 直接執行 frozen `tests/test_p3_stage_projection.py` 的4 cases，明確設 P3A_CARD_PYTHON 與 Chromium 路徑：

- aborted → 設定更新 → master OFF；fault → 原生 reset → 設定更新 → master OFF；completed → 設定更新 → master OFF。
- 三例完整真 native states 各載入 sibling 根目錄 shipped JS，Chromium **156.0.8078.4**，controls attached，master/emergency/reset 可用，page_errors=[]。
- 真填 ph_low=5.3 後 Apply enabled；consumer 發出 switch.turn_on 與完整 apply_control_settings payload。test 不改 payload，逐一經已註冊 Core service 執行，讀回 entry options master=true、ph_low=5.3，hardware calls 不增加、兩輸出仍 OFF。
- 再明確 start 才有 ON，stop 再次結清；Enable／Apply 沒有自動致動。
- 第4例 accepted pending／held OFF ACK 不允許 completed、aborted 或 idle 假終態。

這是 capture→真 shipped UI→payload replay→native service/readback；不是假造合法 snapshot，也不冒稱單一瀏覽器內即時雙向 bridge。既有兩 live bridges 另外依實際 consumed bytes 相等的 evidence 重用。

### reviewer 自增鄰界與原反例

原品質 native probe 與 checker **byte-identical 複製**至本 OUT，另建立獨立 `_successor.py` overlay，只換唯一 snapshot ROOT／JS 路徑；assertions 不變，OUT 仍由新 `__file__.parent` 決定。原 sealed scripts／captures／logs 未寫入。

原反例重跑通過：正常 native stop 後 master OFF，root disabled、stage aborted，persisted master=false、running/owns_io=false、nutrient/circulation OFF。原 checker 真 consumer 接受，master/emergency 可呼叫。其 clean draft `settings_disabled=true` 合理，不能誤報 settings 壞掉；有實際草稿的 Apply 已由上述永久 gate 驗證。

原相鄰 timestamp invalid→同loop recovery／held OFF ACK 也通過：pending 時兩觀測輸出 OFF 但 running/owns_io=true、sample_invalid 持久；ACK 釋放後才 running/owns_io=false，fault 保留。

新增 `test_next_accepted_run_clears_history_until_off_ack_settles`：首輪 aborted → OFF/Enable 保留歷史但零 ON → 新 accepted run **result=None、owns_io/running=true** → held nutrient OFF ACK 時 pump OFF、circulation 仍 ON、stage stopping、result 仍 None → ACK 釋放後才 result=aborted、兩輸出 OFF，master OFF 後 stage 仍 aborted。這個鄰界避免上一輪 outcome 遮住下一輪 pending，也沒有把未結清當完成。JSON：`second-run-pending.json`／`second-run-settled.json`。

## 直接執行結果與命令

使用原 working backend `.venv/Scripts/python.exe`（實跑 Python3.14.5）僅作 interpreter；cwd／pytest config／fixture 來源／PYTHONPATH 均為 exact successor。原 probe 還明確核對 conftest/test_p3_dosing 路徑及實載 control/nutrient/sensor bytes。未安裝套件。

| 本 reviewer gate | 真 child 結果 | raw log SHA256 |
|---|---|---|
| postrun：frozen 新4 cases，含3次真Chromium及 native payload replay | exit0；4 passed，5 upstream warnings，11.83s | `45aa96a2634317061e91dee5d13a804918702daaa98ef68b3b6ee31104b9e262` |
| probe：原品質2例＋reviewer鄰界1例 | exit0；3 passed，5 upstream warnings，4.29s | `d8dc3aadef755aec7f47eba6e99273bd46d2c61d60c3315d3277db23b28c6d0c` |
| capture：原checker的獨立 successor overlay，消費本輪真 native capture | exit0；controls attached，page_errors=[] | `7a154cfb4ef51450e497bbccc72ff0db07b0ba521797a40c7c39ad7f57973f26` |
| final verifier | exit0；138 source／prior135／sealed evidence 前後一致；18歷史receipts及3本次receipts raw SHA符合 | `final-verification.json` |

完整 argv/cwd/env/elapsed/實際 child exit 在 `postrun-receipt.json`、`probe-receipt.json`、`capture-receipt.json`。入口為 `PY_BACKEND -B OUT/run_recheck.py {postrun|probe|capture|verify}`；pytest 使用 `-B -m pytest -c <snapshot>/pyproject.toml ... -v -s -p no:cacheprovider --basetemp <OUT>/pytest-*`。

P3A_CARD_PYTHON=`D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe`；CHROMIUM_EXECUTABLE=`C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe`。

## 歷史 gate provenance 的限定結論

自行程式化核對 repair 的 **18** receipts：raw log SHA 全相符、每次83 broad inventory pre=post；red/probe-red/capture-red 真 child1，其餘真 child0。原始實跑 full-final **249 passed**、postrun-final4、Node10、browser30、dosing/settings兩 bridges 與 static final 綠結果可重用，沒有冒稱本 reviewer 又跑 full249，也不把focused次數加到249。

- full-final／bridge-postrun-final／ruff-final／format-final 的 **全部83 broad inventory** 都符合本 successor bytes。
- 較早 Node/browser/兩舊bridges/probe-green/capture-green 的83表，只有 `tests/test_p3_stage_projection.py` 與現在不同。逐檔比較及全snapshot程式引用搜尋確認：它是未被這些入口 import 的後加 timeout cleanup test helper；相應 production／JS／tools／實用fixture均相等。不是產品漂移，也不宣稱所有歷史83都final一致。
- 較早 full/green/postrun 與final test helper不同，故不以那些舊run取代final full249／postrun4。RED 的兩production與測試/tool差異正常保留。
- 全18 labels／child exits／raw hashes／逐檔delta見 `historical-gates.json`；full-final raw SHA `16392da1ff9348d1930ca131a2a1f07d49c3676f1c6759105eb4250414a8b06d`；postrun-final `0850338ff9bb31f0735e1563a358d461c199630f402299e5ce5bc67d2112f146`。

handoff 稱83 consumed不精確：本報告明確改稱 broad inventory，並依實際使用範圍判斷重用，不以無關testhelper漂移否定產品。

## 產物、問題與限制

本輪 source、原repo及sealed evidence 唯讀；新 runner／byte-exact copies／path-only overlays／reviewer probe／native captures／receipts／logs／prepost inventories／checkpoint／本報告均在 `C:/Users/ivanl/.hermes/cache/scratch/p3a-spec-q1-recheck/`。

沒有本次產品或環境 gate 失敗。final verifier 只加強歷史receipt assertions並優化重複hash；實際執行三gate的原runner bytes保存在 `run_recheck_v1.py`（SHA與receipts一致）。保存該版本時曾遇Windows LF/CRLF hash不等的內部封存斷言，改以原LF bytes保存後精確SHA驗證通過；不是測試產品失敗或改標child成功。另依工作流程把 broad inventory／consumed scope 區分規則補入目前 default profile 的既有 native-card-jsonlines-wire-verification skill，未改其他profile。

本結論只限隔離 native Core＋fixture fake hardware＋本機真shipped Chromium與先前未變範圍。不是原HA、實機保護、hosted CI或發布認證。未連現場HA／憑證／外網，未stage/commit/push/deploy。後續仍需父端獨立品質 affected 重查；若發現阻擋交父端升級，不能自修第三輪。
