# P3a 工程來源交付（2026-11-04）

P3a 補齊可操作加養、必要循環、脈衝／中點停泵／混合／新樣本穩定確認、原生 Options／整組 CAS 及 schema3 Card。已完成獨立 SPEC、品質及發布等價性批准；這不是完整 P3 或實機驗收。

## 不可變的已驗功能來源

| 儲存庫 | Commit | 精確來源 CI |
|---|---|---|
| backend | `ba40214d8756b73879940cb53563b9479c49ec5e` | Actions `41774224570` completed/success；249 native passed |
| Card | `342f19c0aa88bf8b5ac0473c836cf27b109d24b5` | Actions `41774237676` completed/success；Node10、Chromium30 |

原生 CI 與 Card CI 各驗自己的精確 commit；兩庫整合已另外在本機 exact Git tree 驗證，不冒稱 hosted 執行了跨庫 bridge。Hosted Chromium 是141.0.7390.37，本機是156.0.8078.4，不把瀏覽器版本與案例數混寫。後續只有狀態文件的提交不改此表的功能來源身分，最新 HEAD 的 CI 仍應另讀 Actions。

## 已驗與限制

- Enable／Apply 不開泵；須明確 start_flow 或原生整輪 Switch 才啟動。原生輸出與持久讀回是唯一權威。
- F1 provider 任意診斷不再成為持久／公開 fault；未知文字映為有界碼，仍鎖故障。
- Q1 修復正常停止、master OFF、reset／設定更新後的合法 stage outcome；真 shipped UI 可再次操作。未結清 I/O 不假成功。
- 本機 exact-index native249（明設 browser 子程序）、canonical Chromium30、兩真 shipped/native bridges、靜態檢查通過。Node18 exact-index log 僅有1個成功 file wrapper，不冒稱該 log parsed10；上述 hosted Node22 實際逐案例10/10。
- 未建 tag/release，版本欄仍沿開發基線；未安裝 HACS、未接原 HA／現場憑證、未部署實機。一般 Switch 無法證明 HA 當機後會自行關泵；commissioning 聲明不等物理保護驗收。
- 酸／獨立攪拌僅在隔離副本開發，四階段可編順序／合法重疊／相對延遲／條件／星期／預覽及 P4/P5 仍未完成。Issue #3 不得關閉；ready_for_irrigation=false。

Backend 保留 `docs/reviews/p3a-spec-q1/REPORT.md` 與 `docs/reviews/p3a-quality-q1/REPORT.md` 及原 REQUEST_CHANGES 證據；歷史 handoff／快照中的未批准狀態是當時紀錄，不覆寫為後來通過。兩庫 README／共同路線圖以此交付狀態為準。
