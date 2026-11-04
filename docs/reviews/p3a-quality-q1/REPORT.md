# P3a Q1 exact successor — 最後 affected 品質重查

## Verdict：APPROVED（joint P3a source 品質／安全審查）

- **Critical：無已證實問題。Important：原 Q1 已封閉，無新阻擋。Minor：無本輪獨立必修項。**
- 本次 affected 品質判斷，與 `C:/Users/ivanl/.hermes/cache/scratch/p3a-quality-review-20261103/REPORT.md` 所記完整 joint P3a 未變範圍組合，形成這個 exact successor 的整片 source verdict。不是只審兩行便批准整片；也不把前報告的 **REQUEST_CHANGES** 改寫成歷史 APPROVED。
- 先行 SPEC PASS 已讀，並獨立驗證其 source-pre/source-post、3個 receipts、child exit、raw log SHA 與實跑 harness bytes；不是只相信父端摘要。修補預算 **2/2 用盡**，本 reviewer 沒有修 source/test。

## Exact binding 與差異

Snapshot：`C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-q1-successor/`。

MANIFEST SHA256：`9dd070aa362481bcbda54c8e20a392bbe3875fa4d4ecbe7bb743fe8b3a17d6f0`；**138檔逐檔符合，所有本輪執行前後相等**，manifest 本身另外驗 SHA。

與前 F1 snapshot（manifest `1562fbc72421466659e22fd34059e9331ecf1484de267619bb54eca84cae02ff`，135檔）程式化比較：

- changed：production `nutrient.py`、`sensor.py`，以及 `docs/P3A_LOCAL_CHECKPOINT.json` 狀態 metadata。
- added：`docs/P3A_Q1_HANDOFF.md`、`tests/test_p3_stage_projection.py`、`tools/p3a_postrun_check.py`。沒有 removed。
- `control.py`、F1 closed allowlist、實際 dispatcher、其他 production、所有舊 tests、Card 全庫及 contract 完全不變。故前完整品質報告中 Controller/N/CF/CAS/services/Number/Sensor/Card 的未受影響交互分析可沿用。
- control SHA：`7b61e287eb458cf05a7f8d762b211297529f6c24a5a1d38c193e78e7ee41e259`；shipped JS SHA：`8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f`。

已讀 handoff、candidate、contract §8、前完整品質及本輪 SPEC 報告；直接審查 production unified diff，追 `start`→task→`run`→cleanup/stop、pre-body cancellation、master/stage Enable、reset、emergency 與 Sensor 投影。完整 diff 保存在 `reviewed-source-diff.txt`。

## Q1 封閉：真 native → 真 shipped consumer → native replay

本 reviewer 真跑 frozen permanent4，明設 Card interpreter，因此沒有略過其 optional browser gate：

1. aborted／fault-reset／completed 各經設定更新、master OFF 後，root/state/flow_state 合法 disabled，nutrient stage 保留實際 aborted／fault／completed。
2. 三份真 native states 未改寫即載入 shipped JS，真 Chromium **156.0.8078.4**；controls attached，master/emergency/reset 可用，page_errors=[]。
3. 真填 ph_low=5.3、Apply enabled，發出的 master ON 與整組 settings payload **原樣**經註冊 Core services replay；持久 options 讀回 master=true、ph_low=5.3，兩輸出仍 OFF、hardware calls 不增加。必須再次明確 start 才致動，再 stop 結清。
4. accepted pre-entry／held OFF ACK 不假報 completed/aborted/idle。

另 byte-exact 複製前品質原 probe/checker 到本輪獨占 OUT，保留原副本，分開建立 **只替換 frozen ROOT/JS 路徑**的 successor overlays；程式化反向替換證明 assertions 完全不變。原正常 stop→master OFF 反例真 native capture 現為 stage aborted/root disabled，running/owns_io=false、nutrient/circulation OFF。原 checker 真接受且能發出 master/emergency requests。

clean draft 的 Apply disabled 是正確行為，不能誤報設定壞掉；有草稿 Apply 的可操作與 native 持久讀回已由 permanent4 真驗。此 evidence 是 **capture→shipped UI→native payload replay**，不冒稱單瀏覽器即時雙向 live bridge。

## 相鄰安全與品質判斷

### reviewer 新增、直接執行的可達鄰界

`test_adjacent.py::test_stage_disable_reenable_then_settled_emergency_keeps_truth`：

- 真 entered-ON 後 stage disable，結清為 aborted。stage re-enable，再 master OFF/ON，root idle 但 stage/result 仍 aborted、accepted run_stage 保留；零新增 ON，不能用目前 Enable 猜歷史。
- 對這個已 settled run 真按原生 emergency：追加的硬體操作只有兩個 OFF，持久 `fault=emergency_stop`、master=false；root與stage/result 都 fault，running/owns_io=false、兩輸出 OFF。舊 aborted 沒有遮住新故障。
- 原生 master re-enable 被 ServiceValidationError 拒絕，fault latch 保留。明確安全 reset 後 root disabled、fault=None，但歷史 stage/result 仍 fault；再切 stage Enable 仍無致動。
- `emergency_stop` 是明確操作造成的運行故障鎖定，不是檢出物理設備損壞。

### 原鄰界與已驗 SPEC 鄰界

本輪原 probe 的 timestamp-invalid→同loop recovery／normal OFF ACK pending 也真 PASS：兩觀測輸出 OFF 時 running/owns_io 仍 true，sample_invalid 持久；ACK 結清後才 false，fault 保留。沒有把觀測 OFF 當作所有 I/O 完成。

SPEC 自增 next-run 鄰界已讀測試並獨立驗 raw/receipt/source binding：前 run aborted→下一 accepted `result=None`→held OFF pending `stage=stopping/result=None`→ACK 結清才 aborted。本 reviewer 不冒稱重跑該 SPEC 自增案例。

### 實作合理性

`result` 初始化 None；新 run 在 admission/authorize/guard 通過、取得 owns_io 時清為 None，不在 Enable/settings 更新時清歷史。cleanup 是唯一 terminal writer，僅 owns_io=false 後記錄實際 flow terminal；未 entered task 的 stop 仍走既有 cleanup('aborted')。Sensor 僅無 owned I/O 且有 outcome 才使用歷史，否則保留 active flow（dosing/mixing/waiting_sample/stabilizing→running）。故不遮 starting/pending，不放寬 consumer enum，不動 F1 privacy 邊界，不清 accepted stage 身份，亦不以參數或 Enable 推測結果。

既有長控制函式／動態屬性不是本輪新阻擋；為此新增通用框架不屬必要修補。

## 真執行、raw hashes 與驗證

OUT：`C:/Users/ivanl/.hermes/cache/scratch/p3a-quality-q1-recheck/`。

| 本 reviewer gate | 真結果 | raw log SHA256 |
|---|---|---|
| postrun permanent4，含3次真 browser＋native replay | child0，4 passed，5 upstream warnings，13.41s pytest | `ae96e1142261affa714ed37695ee5c699c7dd25a193ea9181f08780cb1107f33` |
| 原 native probe2＋reviewer 新鄰界1 | child0，3 passed，5 upstream warnings，3.72s pytest | `ab4701bf632b64052b440aa3e2e25d8ada99a98074a1a1702ae71f7f7bc35a87` |
| 原 checker path-only overlay，消費本輪 native capture | child0，controls attached、page_errors=[] | `25a5e6ebb071e773473a2da195408195bf47ab00b12668db5acf616c0dfd431d` |
| independent authentication / final verifier | exit0，138 source、prior135、sealed inputs 前後一致，18歷史receipts＋3本輪receipts核對 | 見下列 JSON |

完整 argv/cwd/env/elapsed/child exit 在 `postrun-receipt.json`、`probe-receipt.json`、`capture-receipt.json`。入口 `PY_BACKEND -B OUT/run_recheck.py {postrun|probe|capture|verify}`；另跑 `PY_BACKEND -B OUT/verify_independent.py`。原 SPEC runner byte-exact copy 已保存，新 runner 僅加封存 SPEC evidence 範圍與本輪 checkpoint 標題；執行設定／assertions 不改。

- backend interpreter：`D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe`（實跑 Python3.14.5），僅作 interpreter。
- cwd/config/PYTHONPATH/tests/fixtures 均為 exact snapshot；原 probe 真核 conftest/test_p3_dosing 路徑及實載 control/nutrient/sensor bytes。
- P3A_CARD_PYTHON：`D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe`。
- Chromium：`C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe`。
- source-pre.json 與 source-post.json **bytes完全相等**，SHA 均 `a36d1c6ac09a2e464b0e10b281fdb599756e6e23e5768cbc5d5b8aa4d69f7b1f`。
- final-verification.json SHA：`04e4492392741905ab85d88b479fdcffa3740cb76ac8313d97ff8301e364f33d`。
- independent-authentication.json SHA：`f273ecc527d41015d39fe483493279a63ba45ebc58638c512cfffb8594a6b47b`。
- reviewer 新鄰界 SHA：`e06545222407cbdb3ec925b4176316f2c507ca7ae2496d7aa2c512200a724c02`。

sealed prepost 另涵蓋原 quality、Q1 repair、F1 SPEC、Q1 SPEC evidence；沒有回頭跑會改寫原證據的 verifier。Q1 SPEC 三 raw SHA分別 `45aa96a2634317061e91dee5d13a804918702daaa98ef68b3b6ee31104b9e262`／`d8dc3aadef755aec7f47eba6e99273bd46d2c61d60c3315d3277db23b28c6d0c`／`7a154cfb4ef51450e497bbccc72ff0db07b0ba521797a40c7c39ad7f57973f26`；已自行驗證，包含已封存 run_recheck_v1.py 與 receipt 中當時 runner SHA 一致。

## 歷史 coverage 重用界線

本輪自行驗18 repair receipts 的 raw SHA、pre=post、真 child（RED三者child1，其餘child0）及逐檔 broad-inventory delta，保存在 `historical-gates.json`。沿用 source-bound **full-final249、Node10、browser30、兩 live bridges、postrun-final4** 綠證據；不冒稱本 reviewer 又跑完整249，不將 focused 次數疊加。

83 是 broad inventory，**不是每個命令實際消費83檔**：full-final/postrun-final/ruff-final/format-final 全83與final相符。較早 Node/browser/兩 bridges/原 probe/capture 只有後加 subprocess-timeout-cleanup 的 `test_p3_stage_projection.py` 不同；production/JS/tools/實用fixture相同，這些入口不 import 該模組（snapshot *.py 搜尋亦確認沒有其他引用）。因此可重用其實際 consumed-input 覆蓋，不能假稱每次83都等於final。較早 full/postrun 不替代final對應 gate。

## 產物、遇到的問題與限制

本輪新 runner、原腳本byte-exact副本、path-only overlays、reviewer probe、native captures、logs/receipts、source prepost/delta/diff/authentication、checkpoint及本報告都只在上述 OUT。沒有產品／環境 gate 失敗；最初 handoff 讀取少了 backend 子目錄，發現後按實際 snapshot 結構讀取，未因此改路徑或來源內容。

未改 snapshot、原repo source/test、sealed logs；未碰隔離 P3b worker。沒有 install、原HA、憑證、實機、外網、stage/commit/push/tag/deploy。此 APPROVED 是 joint P3a 本地 exact-source 品質批准，不等於 hosted CI、source publication、部署或物理保護驗收。酸、standalone mix、可編排完整 P3 仍未完成，Issue #3 保持 open；後續發布／CI gate 由父端處理。
