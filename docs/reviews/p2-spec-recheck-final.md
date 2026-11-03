# SPEC-1 修補獨立重查 — source-bound PASS

## 判定

**PASS：本次指定的 SPEC-1 停止 Context 修補及相鄰 native 反例均實際執行通過，沒有發現 must-fix。** 原審查其餘已核對範圍依父端提供的未變範圍沿用；本報告不是重新執行完整 P2，也不是 P3、實機、發布或全面安全認證。

實讀保留的舊報告 `docs/reviews/p2-recovery/nutriculture-p2-spec-review.md`，其 SPEC-1 歷史 BLOCKED 保留，不覆寫。對本次精確來源，該 blocker 已由以下獨立執行關閉。

## 本輪真正執行

工作目錄：`D:/UNiNUS Projects/AI project/uninus-nutriculture`。

使用既有 `.venv/Scripts/python.exe`；環境 `PYTHONDONTWRITEBYTECODE=1`，pytest `-p no:cacheprovider`。獨立 owned scratch：
`C:/Users/ivanl/.hermes/cache/scratch/p2-spec-recheck-independent-zr7xir6a/`。

1. 已讀 `docs/reviews/p2-recovery/p2_spec_context_harnessfixed.py`，只在 scratch 副本改獨立 fixture 路徑，不改 repo／測試邏輯：
   ```text
   .venv/Scripts/python.exe C:/Users/ivanl/.hermes/cache/scratch/p2-spec-recheck-independent-zr7xir6a/probe.py
   ```
   **exit 0**，程序約 9.72 秒。真 native HA ServiceRegistry → 原生 Switch handler → 真 SwitchEntity 假硬體，沒有替換 service dispatch。
   - 非 admin 啟動被 HomeAssistantError 拒絕，假硬體 calls 長度不變（此 probe 的無副作用斷言精確限硬體呼叫）。
   - admin 啟動、不同 user（owner）正常 OFF：實際輸出 OFF 的 `parent_id == stop.id`。
   - 新一輪由 admin 啟動後刪除該 user，再觸發高水位：實際 OFF 成功，`user_id is None`，硬體狀態 off，controller.running false。
   - 此輪 OFF parent 等於新一輪 start Context，且不等於上一輪 stop Context：
     ```text
     new_run_origin = 01M6G5F0JY52QJA88HBBF5XYDK
     previous_stop_origin = 01M6G5F0JWH96DAE1J06AZMNEN
     off_parent = 01M6G5F0JY52QJA88HBBF5XYDK
     ```
   - 原始輸出：`run0.log`；只有 custom integration 常規提示。
2. 只重跑修補的窄測試，不重跑已綠全套：
   ```text
   .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=C:/Users/ivanl/.hermes/cache/scratch/p2-spec-recheck-independent-zr7xir6a/pytest-temp tests/test_p2_context.py
   ```
   **exit 0；5 passed, 5 warnings in 2.86s**（程序約 5.41 秒）。
   - 覆蓋 flow_run／automation_enabled／refill_enabled 正常停止及 emergency_stop 的人類因果 Context。
   - 額外覆蓋 ON 尚未結束時刪除 admin，原啟動被拒絕但安全 OFF 仍完成並保留 origin parent。
   - 原始輸出：`run1.log`；5 warnings 為既有 HA/backoff dependency deprecation。

完整命令、退出碼、stdout/stderr、執行耗時及指紋另存同目錄 `receipt.json`。

## Source 核對

`control.py:145–175,180–194` 傳遞 action／press 的停止 Context；`:265–267` 每輪清除 stop_context、設定新 run_context；`:303–316` 異常／取消收尾保留 origin；`:351–388` 停止以內部 `Context(parent_id=origin.id)` 執行安全 OFF，避免已刪除 user 的權限重查阻擋關閉。未把內部安全關閉改成人類啟動權限豁免。

SHA256（本輪開始與結束相同）：

| 來源 | SHA256 |
|---|---|
| backend control.py | `944a26cfb67b53d63fee390aa3bb54e41ed886d58177458641b03c739d21b2d5` |
| tests/test_p2_context.py | `7118baa0c62894a8c3a4ddb65aa39aa473781719b42d6d650890e83cfc806b68` |
| tests/p2_fixtures.py | `d6935a57b593abcbe3de7bc6d6aa570c5317f6c693de941ffc67c2df01f1e515` |
| harnessfixed repo 原始檔 | `c45764f57935a340679560a72c470937281418f8c86e15a5ae3facc8ed5caf90` |
| backend control_auth.py | `5ea382f4827835c99580df166f9fe825a9062aeacb8da2c34193594fe91833e5` |
| backend services.py | `5c9f03e5030609d7a607df97db50c772c1f0394933f2a78c12f6c396661fdd65` |
| shipped Card JS | `04304bc0f62c5a26bbaa4a28018543a0ab46728e5148c44f1f2e221bb4a8d25f` |

另驗 `git show :custom_components/uninus_nutriculture/control.py` 的 SHA256 與 worktree 完全相同；backend 完整 `git ls-files --stage` 執行前後相同；`git diff --name-only` 前後均空。此為指定修補的 source/index binding，不冒稱本輪重新做全庫 exact-index inventory gate。

## 範圍與保留事項

- 沒有改 repo、commit／push、讀憑證、連外部 HA；僅 scratch 報告及測試產物。
- 沒有重跑 native143／Node9／Chromium23／跨層橋接；這些仍是父端既有證據，不冒稱本輪新執行。
- 原 SPEC 已核對且父端確認未變的其餘範圍沿用；不重開 P3 未實作議題。
- 本輪首次 Python orchestration 命令發生 shell quoting 導致 SyntaxError（exit 1，尚未執行 probe）；已修正命令後真執行兩項均 exit 0。這是本輪工具命令錯誤，非產品缺陷；不隱藏該失敗。
- 先前 reviewer 的 ConfigEntry.sources harness typo 不作產品缺陷；本輪使用已讀取的 runtime_data.sources 更正版，只有 owned fixture 路徑調整。

**最終：指定精確 control.py 來源上的 SPEC-1 修補及所要求相鄰邊界 PASS，無新增 BLOCKED。**
