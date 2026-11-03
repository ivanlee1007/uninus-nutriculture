# P2 候選驗證與交付界線

> P2補水控制與Card已接通，僅供隔離測試。**已完成獨立SPEC與品質／安全審查（包含Q1修補），僅為P2工程切片，不是完整產品或物理安全驗收。**程式發布與CI以對應遠端commit及Actions為準；未tag/release、未部署或操作原HA。

## 已實作的可操作路徑

1. 原生Options明選已註冊補水輸出，保存穩定Registry身份、commissioning確認、回饋期限與各階段星期；保存/取消不致動。
2. 總開關＋補水子開關允許後，原生整輪Switch或start_flow呼叫同一後端。初次安裝/無綁定/未確認預設不運行。
3. 液位低於低標才補水，達高標事件停止；來源失效/逾時/正常停止/急停進行取消與輸出回饋確認，未確認不假報OFF。
4. 急停鎖定/復歸、權限/明確槽目標、Registry身份/可識別共享綁定、重啟不續跑與晚到I/O有隔離測試。
5. 獨立schema2控制Sensor供新版Card操作；原schema1監測Sensor與10 Numbers保留。P2永不授予灌溉許可。

## 真實執行結果

| Gate | 實際結果 | 證據 |
|---|---|---|
| Native HA後端完整回歸 | 151 passed，0 skipped，5項上游dependency deprecation warnings | backend docs/evidence/p2-q1-exact-index/native/（精確Git consumed inputs） |
| 停止Context修補 | 5 fail RED → 5 pass GREEN；總/子/運行OFF、急停與user刪除後安全OFF | backend p2-43-context-red/、p2-44-context-green/ |
| Card canonical | Node 9/9、真Chromium 23/23，無fail/skip；320/768/1200與明暗主題幾何 | Card docs/evidence/p2-07-parent-canonical/ |
| 跨層操作 | shipped Card 10次UI操作→隔離HA真Switch/Button handlers→真SwitchEntity假硬體4組ON/OFF；高水位、正常停止、急停/復歸、外部服務狀態同步均通過 | backend docs/evidence/p2-q1-exact-index/bridge/receipt.json |
| compile / ruff | backend production/tests與橋接工具compile及ruff check/format通過；橋接工具import排序曾失敗並已修，不冒稱最初全部通過 | 最終命令及後續handoff記錄 |
| 原始SPEC審查 | 發現1項must-fix：停止操作Context來源遺失；已修補且獨立source-bound重查PASS，原BLOCKED報告保留 | scratch原SPEC報告及其context probe |
| SPEC修補重查 | **PASS**：真native5項及獨立跨user/刪user/新run Context反例通過，來源與index綁定 | backend docs/reviews/p2-spec-recheck-final.md與docs/evidence/p2-spec-recheck-independent/ |
| 首次品質/安全審查（歷史） | **REQUEST_CHANGES / Q1，現已關閉**：starting來源短暫失效被遺忘；兩次重現與7行修補保留 | backend docs/reviews/p2-quality-initial.md與docs/evidence/p2-quality-initial/ |
| Q1回歸 | 8項永久native；RED 6 fail/2 pass → GREEN；其中3個恢復案例真重現Q1，3個held-invalid原已安全OFF但fault歸因需修正，不混稱OFF失效 | backend p2-47-start-source-red/、p2-48-start-source-green/、p2-49-start-source-full-native/ |
| Q1獨立SPEC／品質重查 | **PASS／APPROVED**：精確2038ec1b來源，SPEC真執行15項，品質原反例及鄰近控制3項；與先前未變範圍明確組合 | backend docs/reviews/p2-q1-spec-recheck.md、p2-q1-quality-recheck.md及各獨立receipt |
| exact-head hosted CI | 以本commit的GitHub Actions與Issue #2發布回讀記錄為準；未成功前不可稱CI驗收通過 | 不使用舊P1或文件commit的CI替代 |

停止下傳使用內部安全Context並保留原操作的parent_id，避免被移除的使用者阻擋安全關閉；啟動仍執行原管理員授權。完整原生測試不與focused/重跑/跨層動作相加，避免重複統計。

## P1舊測試窄適配

本輪不削弱數值、持久化、來源有效性或原native無輸出fixture：舊ids helper只列10 Numbers與原status；Sensor數量改為兩個並分別檢查schema1/schema2；版本metadata改0.2.0與新增Options欄位；原「整包不能有Switch/Button」改為只有Controller可呼叫輸出、仍禁止另建MQTT client。保留原P1基線與初始RED證據，沒有回寫歷史快照。

## 仍未提供／未驗證

- P3加養/加酸/獨立混合控制、任意可編依賴圖與其完整UI尚未實作；對應native Switch unavailable，Card明示未支援。平均目標加藥及危險可調預設仍是P3規範，不冒充P2已交付。
- 目前只有補水可運行，不含獨立通用start_stage、內建排程器或外部旁支管理。
- 本機橋接不是HA前台宿主、HACS安裝或物理設備驗證。尚未證明設備斷線/HA當機時能自停。
- Commissioning勾選是操作人員確認，不是軟體探測或實測證明。只能核對可識別綁定，不宣稱自動辨識所有不同Entity背後的實體繼電器別名。
- 已通過測試不代表可立即接管原農場；審查完成後仍需另行取得部署/實機驗收授權。

## 接續工作的確切斷點

1. SPEC-1修補獨立重查已取得source-bound PASS，原失敗歷史保留；不重新開啟已關閉的blocker。
2. Q1修補後的獨立SPEC與品質審查均已完成，無剩餘must-fix；兩輪具體修正歷史與原始失敗保留。
3. 最終source/index/evidence對齊，明確清單提交兩庫，讀回遠端與exact-head CI；未完成前不關Issue #2。
4. P3–P5繼續保留，不因P2切片而縮減完整產品範圍。
