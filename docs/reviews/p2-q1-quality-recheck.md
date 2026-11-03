# Q1 最終獨立 QUALITY 窄重查

## Verdict: APPROVED（組合原品質完整 bounded 範圍與本次修補）

無剩餘具體 must-fix。原 `docs/reviews/p2-quality-initial.md` 的唯一 Q1 已由精確七行修補關閉；原其他後端／前端／權限／取消／綁定邊界的未變範圍結論保留。此結論不是全產品重新審查、P3、實機或發布認證。README／P2_ACCEPTANCE 的 pending 收尾不列為產品 defect。

## 精確來源與組合依據

- controller worktree、Git index、精確 index snapshot、三個實際 native HA fixture 消費的 controller 複本 SHA256 均為 `2038ec1b06b8c3966981e17988b2b87986731fd70708b6a74ec30f8bead58990`。
- Card worktree SHA256 為 `04304bc0f62c5a26bbaa4a28018543a0ab46728e5148c44f1f2e221bb4a8d25f`。
- 獨立讀取原 QUALITY report、原反例兩支腳本與 source-bound SPEC PASS 報告；實讀新 controller 全文及事件／admission／stop cleanup 相鄰流程。
- 與原 QUALITY `source-manifest.json` 逐項比較 Git index：backend 原列 52 檔中 51 檔 raw SHA 完全相同，僅 control.py 改變；Card 原列 6 檔 raw SHA 全相同。另驗證精確 snapshot 的原列 52 檔逐一等於目前 index bytes（全通過），因此不是僅靠相同 HEAD 推論未變。
- 新永久測試 SHA256 `25b8a74dbddce64088fe2ea157344ed6682bba7ac7ae7297dfe793508096e0cb`。舊既有測試沒有移除或弱化。
- 與 p2-47 RED snapshot 的文字比較確認 production 唯一實質差異是 evaluate() 開頭新增七行；其他 raw 差異是換行格式。以原品質 raw-index manifest 作為主要未變性證據，不把 RED snapshot 換行差異誤稱完全 raw 相同。

新增分支只處理 running && starting：必要來源 snapshot invalid 時同步鎖 source_invalid，接著 await 既有 stop；stop 在等待 lock 前撤銷 generation，start 的既有 post-await 檢查因此拒絕並走原有有界 OFF cleanup。來源恢復不能消除 fault／撤銷。合法 pending output OFF 不進入 refilling-only output fault 分支。沒有新增授權豁免、服務路由或 Context 變更。

## 本輪真正執行：原 immutable 品質反例 + 鄰近控制，3 passed

將原 `test_quality_start_source.py` 和 `test_quality_adjacent.py` 原始 bytes 複製至唯一 owned scratch，SHA 一致，未修改原腳本。透過真 control_hass fixture、native switch service 與 SwitchEntity，僅硬體為 fixture 假體。

測試 cwd：
`C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p2-exact-index-41cab5e6c8/uninus-nutriculture`

實際 argv 完整保存在 run.json；核心命令：

```text
D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider -p conftest -c D:/UNiNUS Projects/AI project/uninus-nutriculture/pyproject.toml --basetemp C:/Users/ivanl/.hermes/cache/scratch/p2-q1-quality-ce0a9ba6bf/native-temp -q -s <owned>/test_quality_start_source.py <owned>/test_quality_adjacent.py
```

環境 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=<精確 snapshot>/tests`。

**真 pytest child exit 0：3 passed, 5 warnings in 4.94s。** warnings 僅 HA/backoff deprecation。

1. applied ON、provider 尚未返回、pH 持續 invalid：during starting 已 fault=source_invalid；返回後 ServiceValidationError、fault 狀態、output OFF、calls 精確 turn_on/turn_off。
2. 同樣 pending ON，但 pH 於 provider 返回前恢復（原 Q1 真反例）：同樣拒絕、source_invalid 不遺忘、output OFF、calls turn_on/turn_off。
3. 正常已 refilling 後短暫 invalid 再恢復：fault=source_invalid、running=false、output OFF，不自動續跑。

本輪 consumed source/test Python 與兩個配置檔共 49 檔前後 SHA 相同。三個 fixture controller copy hash 另行核對一致。

## 證據

獨立 owned 目錄：`C:/Users/ivanl/.hermes/cache/scratch/p2-q1-quality-ce0a9ba6bf/`

- `run.json`：完整 argv、cwd、env、實際 child exit、before/after hashes、probe hashes。
- `pytest.log`：原始 pytest log，SHA256 `d4edcd53f7d4cc72ffab57a7c0b4bb6ec64fbdcf84e16049ea64ebacf6834cae`。
- run.json SHA256 `2cbd26a6ac479be771147bc0060a8e016e151b6658882cf492228a73006c3115`。
- `composition.json`：原品質 manifest 的逐檔 raw-index 比較、RED snapshot 差異及三份實際 consumed controller hash。
- `snapshot-binding.json`：52 檔 snapshot/index byte equality 與新測試 hash。
- 原兩支 probe 的不改內容副本、唯一 native-temp 執行目錄。

## 限制／工具事件

本輪只宣稱真正重跑上述 3 例；不冒稱重跑完整 151、Node9、Chromium23、shipped Card bridge 或 physical hardware。父端及 SPEC 的其他新綠結果各由其自己的 source-bound 證據承擔。本次 APPROVED 明確組合原完整 bounded 品質審查之未變範圍與本輪修補確認，不以零散新測試替代原審查。

未修改 repo、tests、fixtures 或舊證據，未讀憑證、連原 HA、commit/push。只新增此報告及上述 owned scratch 產物。第一次 manifest comparison helper 遇到頂層非 repo list 欄位，產生 TypeError；改為明確指定兩個 repo keys 後完成，原失敗未當作產品失敗或測試結果。初次 status 輸出過大被工具截斷，沒有以截斷資料推論範圍；組合判斷採逐檔原 manifest 比較。
