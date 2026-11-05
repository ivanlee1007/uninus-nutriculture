> 現行交付狀態（2026-11-05）：P1–P3軟體來源已交付；P3c Backend `a85c120b80bcb1b92d9459637cfa1d36c5a9ac16`／Card `9867602939ea0b04cafdcec9873eca77c8b7e1ed` 的 exact-HEAD hosted CI `41848490751`／`41848470366` 均成功，SPEC、品質、出版等價及已列軟體驗收完成。Issue #3 保持 OPEN，15個軟體項已勾、2個實體保護／別名commissioning未勾。P4a 參數配方（原生Options＋Card保存/原子套用）已實作並通過整合SPEC與全slice品質兩審；出版等價與exact-commit CI待驗；P4b品質/許可、P4c結果通知及P5未完。物理驗收不阻擋隔離P4；未存取原HA／認證、未HACS安裝、未tag/release或部署。後端唯一權威；無stage_link、內建scheduler或外部腳本管理，IRR仍false。

# 開發目標對齊與有限後續順序

檢視日期：2026-11-05。本次對齊候選只修現行宣稱與後續順序，不重寫歷史、不構成P4來源批准或部署授權。

## 結論

**產品範圍沒有刪減，但文件與開發重心需要校正。**

1. 兩庫 README／共同規範／路線圖仍把 P3 寫成全部未實作、R04 等已凍結工程政策寫成等待使用者決策。現已區分「P2 已發布」、「P3a 已交付並通過兩審及功能來源 CI」、「P3c 主功能來源已接通並完成兩審，非全產品／實機完成」。不回寫歷史證據。
2. 加養安全切片已產生真正可操作路徑，不是只有 fixture UI；P3b 已接通酸與獨立攪拌並完成兩審；完整 P3c 可編流程已接通並完成兩審。必要安全不得刪除，也不再以無界排列／新測試框架代替主功能。
3. 下列目標仍全部有效；P3a 只能代表開發順序，不能作為全產品完成或關閉完整 P3 的依據。

## 目標與可核對現況

| 使用者結果 | 可核對現況 | 下一個實際交付 |
|---|---|---|
| 可重用、多槽、重用原生 MQTT Entities | 每槽 config entry、三來源及原十 Number 已實作；完整多槽產品驗收仍待後續 | 保留身份／隔離，不硬綁農場名稱或值 |
| 原生前台及 Card 共用啟停 | P2 補水已發布；P3a 加養與群組設定已走真 native/shipped Card bridge | 已完成 P3a 具體阻擋與兩審；P3b 酸／獨立攪拌已完成兩審，P3c 來源已接通並完成兩審 |
| 補水、加養、加酸、必要及獨立混合 | 補水已發布；加養／必要循環本機已接通；P3b 酸／獨立混合已接通並完成兩審 | P3c 可編流程來源已接通並完成兩審；不以另一個輔助框架代替主要功能 |
| 可編順序、合法重疊、條件、相對延遲、星期與預覽 | 星期／參數群已可保存，actual-admission 檢查有 native 路徑；完整有限圖與編輯／七日預覽已接通並完成兩審 | 已交付；P4a原生/配套Card參數配方已實作並通過兩審，不重做P3 |
| 慢感測不過量、使用者可調 | EC 中點停泵、pulse/mix/new sample、可調界限已本機執行；P3b 指定安全反例已完成兩審，實機能力仍待校驗 | 有限關閉已知缺口，不把預設當物理認證 |
| 配方、結果／通知、品質及灌溉許可 | 尚未交付；高 pH 原生延時原因已接通不等於通知系統 | P4；未完成前 ready_for_irrigation 固定 false |

## 不變邊界

- 不增加獨立 stage_link；不硬編固定補水→加養→加酸→混合拓撲。
- 星期依 HA 當地日期、在各階段實際 admission 前檢查；不是內建排程器。
- 外部決定何時啟動整輪；本整合負責輪內計時、混合、資源、樣本與安全。
- 後端唯一輸出／安全權威；Card 不直接控制泵、不樂觀捏造 state、不持有關泵計時器。
- 原 HA 不連線／不接管；既有來源憑證不讀取；沒有 tag/release 或實機部署授權。

## 有限執行順序

1. **P3a 收尾已完成（下列為歷史工作內容）**：先修初始採樣 token admission、下一輪放寬重新取值、native request cache64；接著針對混合 commissioning 急停／未收束角色、明確必要循環 ownership 及可達取消／trace 界線完成具體反例。每個凍結條款保留主要 native 行為與必要鄰界，不追求無窮笛卡兒積。
2. P3a／P3b 已依凍結來源完成整合 SPEC→獨立品質；P3b功能來源及CI早已交付；P3c兩審/出版等價/精確HEAD CI及軟體named驗收亦完成，不再停留於出版準備。發布／exact-head CI／部署／實機分開。
3. **P3b 酸與獨立攪拌可操作切片（已接通並完成兩審）**：重用安全／採樣／循環所有權與原生控制入口，不能只新增 capability 或空 helper。
4. **完整四階段可編執行＋最小 UI／預覽**：有界圖工程模型與實際執行已接通，凍結來源已完成兩審；publication-equivalence 與 exact-commit CI 均已完成；不重開P3 gate。純保存／預覽不冒稱可執行編排。
5. P4a已實作並通過兩審：原生與Card配方保存/選擇/原子套用至10個Number，不只是新模組。P4b品質/完成/許可、P4c互通/通知與P5進階體驗仍保留；不能再以額外P3證據工作替代主功能。

P3a 來源交付與歷史證據保持不變。P3b 已審來源具備加酸／獨立攪拌／S4 原生與 shipped Card 路徑，以及 295 項 native 假硬體驗證；P3b與P3c的出版等價與對應exactHEAD CI均已完成，證據與實機驗收分開。P3c 四階段可編執行與真正預覽已接通並完成兩審；Issue #3 保持 OPEN。不從頭重做 P1/P2/P3a，不重問已確認政策。

## P3c 現行流程與原生操作

- 四列必須各含一次 `refill`、`nutrient`、`acid`、`mix`。可改順序；第一列為 `flow_start`，其餘可選 `flow_start`、`after_previous_started` 或 `after_previous_finished`，延遲相對於該錨點，不是任意腳本或排程時間。合法 overlap 仍受後端輸出資源、最低液位、採樣及安全 gate 約束，不保證同時致動。
- 必要加藥循環與獨立 mix 不同：停用獨立 mix 不會解除加藥必要循環。共用 circulation 由後端仲裁；不能以 Card 或其他入口繞過 ownership。
- 有限 condition 僅 `level` / `ph` / `ec` 的 `gte` / `lte` 有限數值，或 `none`；不是 template。液位用 m（0–10）、pH 0–14、EC 用 mS/cm（0–20）。每列等待期限與整輪期限有界。
- 到「設定 → 裝置與服務 → UNiNUS Nutriculture → 該槽的設定／選項」，勾選 **Open flow plan editor (no settings saved)**（`flow_plan`），開啟 **Flow plan / 流程計畫**。這是原生 selector 表單，不必貼 JSON；進入編輯器不會保存同頁其他設定。
- 每列有 stage、start rule、delay seconds、wait timeout seconds、condition source/operator/value 及 weekdays；`run_timeout_seconds` 為整輪期限。用 **Save / seven-day Preview / Cancel / move row up or down** 的 `row_0_down` / `row_1_up` 等動作調序；規則隨列保留，調序後第一列仍須 `flow_start`。
- `action=preview` 讀草稿，列出七日有效流程；`save` 才以版本衝突檢查原子保存，作用於下一輪，不啟動設備；`cancel` 不保存。其他頁面已改設定時須重開並協調，不能覆蓋新版本。Card 同樣提供階段列、上下移動、星期、Preview／套用／取消；參數群與流程草稿為分開 namespace。
- 每階段真正 admission 前依 **HA 設定時區** 的當地星期重查；跨午夜不沿用整輪開始日。星期是允許 gate，不會自行排程、補跑或啟動。外部 automation／`uninus_nutriculture.start_flow` 與原生整輪 Switch 共用後端；Enable 開關不是 start。
- Preview 使用相同有限依賴／略過與資源模型，反映停用、星期、條件、等待和依賴，不再只是單一 eligible 清單。未來感測、實際加藥／補水完成時刻及跨日 admission 可能未知；七日預覽不是確切時間表、成功保證或灌溉許可。無致動也不建立運行任務。
- P3c交付時永久 native suite 為 335；本輪P4a suite 為378；R4 full 339 包含四項外加 QA probes，不屬正常 repo，不能要求乾淨 CI 收集 339。源碼兩審不取代 publication-equivalence 審核或 exact-commit hosted CI。內嵌版本未升正式發行版本；不為顯示美觀修改 bundle/hash/version metadata。

## P4a 本輪交付範圍（已實作並兩審；非完整P4/發布宣稱）

- [參數配方契約](P4A_RECIPE_CONTRACT.md)
- 原生Options與Card共用entry-owned UUID配方庫：建立/編輯/選擇/刪除二確認，Save/Cancel不改運行參數，Apply原子更新既有10參數且零致動。不能變更commissioning、Enable、fault、流程、星期或裝置保護。
- 本slice只交參數配方；完整配方擴充、品質/完成/許可與外部結果/通知仍屬後續P4，不標全P4完成；未完成前IRR維持false。
- 不新建通用測試框架，不重做已交付P3，不用物理驗收待辦阻擋隔離軟體開發。每個主要行為真RED→GREEN、一次整合SPEC→品質；P4a最多兩輪具體repair，P3的4/4歷史不重置。
