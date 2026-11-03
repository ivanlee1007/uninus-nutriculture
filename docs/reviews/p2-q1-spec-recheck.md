# Q1 七行修補獨立 SPEC 重查 — source-bound PASS

## 判定

PASS：精確 control.py `2038ec1b06b8c3966981e17988b2b87986731fd70708b6a74ec30f8bead58990` 的 Q1 修補符合既有必要來源安全契約。未發現本次受影響範圍 must-fix。不是完整 P2 重審，也不是 P3、實機或發布認證。

永久測試 SHA256：`25b8a74dbddce64088fe2ea157344ed6682bba7ac7ae7297dfe793508096e0cb`。

## 獨立執行

測試 cwd：`C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p2-exact-index-41cab5e6c8/uninus-nutriculture`（精確 index blob snapshot，並非讀取可能漂移的 worktree 程式）。

執行命令（以下 snapshot 路徑均為上述 cwd 的完整絕對路徑，receipt 保存原始 argv）：

```text
D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider --basetemp C:/Users/ivanl/.hermes/cache/scratch/p2-q1-spec-173e38b360/native-temp -q <snapshot>/tests/test_p2_start_source.py <snapshot>/tests/test_p2_context.py <snapshot>/tests/test_p2_start_bounds.py
```

環境：`PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=<snapshot>/tests`。

**實際 child exit 0：15 passed, 5 warnings in 5.25s。** 無跳過；warnings 為 HA/backoff deprecation。

- 新八例：pH/EC/level × 持續失效/返回前恢復共六例，皆拒絕啟動、確認 OFF、fault=source_invalid、running=false，硬體 calls 精確 turn_on/turn_off，OFF parent 指向啟動 Context。
- 必要來源在 refilling 短暫失效恢復仍鎖故障，不續跑。
- 合法 starting 的來源變化、輸出尚未 ON 不誤判 output fault；release 後成功 refilling。
- Context 五例：人類 flow_run/master/refill/emergency stop 溯源保留；ON 等待中刪除使用者不阻礙內部安全 OFF。
- starting bounds 二例：timeout 收緊後放寬不遺失保守界限；高水位於 ON acknowledgement 期間出現仍停止。

獨立 owned 證據目錄：`C:/Users/ivanl/.hermes/cache/scratch/p2-q1-spec-173e38b360/`。

- `run.json`：原始 argv/cwd/child exit、60 個 snapshot Python production/test 檔的前後 SHA256；前後完全相同。
- `pytest.log`：未修改的原始結果。
- `composition.json`：基線比較與精確七行 diff。
- run.json SHA256：`1cec0bf8f3504d9320c56ab6f0508503a419544bb6aac28c2a8fdf5faeb32c00`
- pytest.log SHA256：`cfb3eb7941de6937077c2a7ef2971b0e0f0ec1b5bea41fd3ca63ba7bd851a2cf`

## 來源審查與組合

實讀 control.py 的事件調度、evaluate、start admission/post-await 驗證、stop 世代撤銷與有界 OFF，以及八個新永久測試、Context 五例、bounds 二例。實讀未變 `docs/P2_CONTROL_CONTRACT.md`、原 `docs/reviews/p2-quality-initial.md`、`docs/reviews/p2-spec-recheck-final.md`。

新增分支僅限 running && starting；snapshot invalid 同步鎖 source_invalid，再 await 既有 stop。stop 在等待 start lock 前同步遞增 generation，所以恢復不會讓原 admission 再成功；start 原有 post-provider 檢查會拒絕，原有 cleanup 完成 OFF。合法 pending output OFF 被明確排除 refilling 專用輸出遺失檢查。未新增授權豁免或更動 Context/late-ON/有界清理契約。

與 p2-47 RED snapshot 的 47 個 Python 來源/測試實際比較：只有 control.py 是非換行內容差異（精確新增七行）；其餘七個 raw-byte 差異逐一證明僅 CRLF/LF。該基線 control.py SHA256 為 `944a26cfb67b53d63fee390aa3bb54e41ed886d58177458641b03c739d21b2d5`，等於原 SPEC/品質審查來源。基線內全部既有測試保留，無測試移除/弱化。新 test 檔於 RED 時已存在且固定 SHA，本輪相同。

因此本次 bounded PASS 可與父端提供、原 SPEC 報告記錄的其餘未變範圍結論組合；不將這項 47 檔比較冒稱全庫 raw-byte 相同。Card 不改，本輪不重跑 native151/Node9/Chromium23/bridge；父端的新精確全套及橋接驗證另行負責。本次只宣稱上述真執行 15 例。

原 Q1 紅結果保持不覆寫：三個恢復案例是真新增拒絕/OFF 缺陷；三個 held-invalid 原本即安全 OFF，新增斷言改進 fault 歸因，不稱它們原本 OFF 失效。

## 限制與工具事件

只讀 repo；沒有修改原測試/fixtures/舊證據、沒有讀憑證、連原 HA、commit/push。只新增此 scratch 報告與獨立 owned 執行產物。

第一次 discovery 印出過大的 identity JSON；下一個 read-only 命令因精確 snapshot 不含 docs/P2_CONTROL_CONTRACT.md 而 exit 1（已先成功讀到七行差異與新測試）。改從 repo 唯讀契約文件後完成，非產品或測試失敗。未因此改動 snapshot 或原 repo。
