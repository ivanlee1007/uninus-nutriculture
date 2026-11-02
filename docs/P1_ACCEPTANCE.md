# P1 驗收與交付狀態

## 已交付範圍

P1 為可安裝的影子監測 integration 與配套 Card：原生感測器綁定、十個 integration-owned Number 參數、參數驗證與原生正常關閉後的設定保存、來源單位/新鮮度/品質診斷、Card 單項保存與寬窄版操作。P1 不包含設備控制，且不授予灌溉許可。

## 實際驗證

| 驗證層 | 結果 | 限制 |
|---|---|---|
| 原生 HA 隔離測試 | Core 2026.10.4 / Python 3.14.5，59 passed、0 skipped | Windows 隔離環境，不是正式站 |
| Card 單元測試 | Node 18.6.0，5 passed | 與 CI runtime 分開記錄 |
| Card 真實瀏覽器 | Chromium，16 passed；320/768/1200 viewport 無橫向溢出 | 模擬宿主，不是實際 HA Dashboard 宿主驗收 |
| 跨層 bridge | shipped Card → 真實 HA ServiceRegistry，九項檢查全通過 | 隔離 transport，不是正式站驗收 |
| 獨立 SPEC | 初次發現不可用 Number 映射缺口；修正後 PASS | 原失敗報告保留，不覆寫歷史 |
| 獨立品質/安全 | APPROVED，無 critical/important 阻擋 | 不代表部署或發行核准 |
| Git 精確交付內容 | 從 index blob 建立隔離副本後重跑 59 / 5 / 16；來源 LF 正規化已驗證 | 最後另加入本文件與審查證據，未改變已驗證程式/測試/CI |

三組測試數不得與重跑或 bridge 操作數相加當作不同案例總數。原始本機測試紀錄位於 `docs/evidence/`；Card 紀錄位於伴隨專案的 `docs/evidence/`。遠端 Linux CI 狀態以兩個 repository Actions 的對應完整 commit 為準，本文件不以本機綠燈代替遠端結果。

## 獨立審查留存

後端 repository 的 `docs/reviews/` 留存 SPEC 初次報告、SPEC 複核、品質審查與核准時的完整候選 hash 清單；`docs/evidence/integrated-review/` 留存隔離 bridge 與品質探測的原始程式/結果/紀錄。審查文件中的本機 scratch 路徑是當時執行位置，不是線上安裝需求。

## 尚未執行

- 未部署至原農場 HA、未修改既有自動化、未操作硬體。
- 未驗證實際 HA Dashboard 宿主的新增卡片流程及 HACS 安裝。
- 未驗證突然斷電的 crash durability；參數採 HA 原生排程儲存。
- 未執行正式 tag/release；兩個 repository 保持私人。
- P2–P5 依 [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) 與 GitHub milestones/issues 繼續開發，不因 P1 完成而取消。
