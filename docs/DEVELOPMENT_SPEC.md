> 現行狀態（2026-11-05）：P1–P3與P4a參數配方軟體來源已交付。P4a Backend `5c22e68be935121a853a9351e14cd6d49e38b03d`／Card `108071a744ccc373c300d919b5741b1400a8a047` 的 exact-HEAD CI `41989334445`／`41989315312` 均全job成功，SPEC、完整品質、出版等價及hosted產物驗證已過；P3c實機待辦仍保留。P4b品質／完成／灌溉許可來源已實作並完成獨立SPEC與完整品質兩審及本機隔離驗證，正在出版準備，以[P4B_QUALITY_CONTRACT.md](P4B_QUALITY_CONTRACT.md)為準；出版等價、exact-index與新commit hosted CI仍待驗。採獨立quality_v1與唯讀permit binary_sensor，不改S1–S5既有ready=false。P4c通知結果與P5均未完；未連原HA／認證、未實機接管、未HACS實際安裝、未tag/release或部署。


> 導航優先序：FUNCTIONAL_PARITY_REVIEW.md是舊commit的歷史F/D盤點，不代表目前沒有控制能力或所有D/R仍未決；不改寫其原文。P3C_FLOW_CONTRACT.md頂部提案語句屬來源歷史，現行以其§7已採納補充及本輪交付狀態為準，不再次凍結或重審。
# UNiNUS Nutriculture 開發規範

> 本次對齊：2026-11-05。P1–P3軟體交付與實機驗收分開；新增P4a範圍以[P4A_RECIPE_CONTRACT.md](P4A_RECIPE_CONTRACT.md)為準，P3c有限圖以[P3C_FLOW_CONTRACT.md](P3C_FLOW_CONTRACT.md)§7優先。歷史審查與失敗證據不回寫。

## 1. 規格優先序與範圍

- 本文件定義目前共同產品規範及未決策登錄；若與舊研究的待確認描述衝突，以本文件與使用者最新明確決策為準。
- [CONTROL_DECISIONS.md](CONTROL_DECISIONS.md)補充開關生命週期；[CONTROL_SWITCHES.md](CONTROL_SWITCHES.md)保留詳細安全及C01–C14案例；[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)定義分期，不得以分期默默刪掉完整產品要求。
- [FUNCTIONAL_PARITY_REVIEW.md](FUNCTIONAL_PARITY_REVIEW.md)保留原系統F01–F36及D01–D11依據；[FLOW_DESIGN_RESEARCH.md](FLOW_DESIGN_RESEARCH.md)為決策前研究快照，不得把其中已被取代的R01/R03重新當未決。
- 產品為可重用、多槽的HA integration＋配套Card；重用現有MQTT Entities，不硬綁原農場的名稱、順序、星期、設備或數值。
- 原站保持唯讀；開發/文件推送不是實機接管或部署授權。不得公開原站URL、憑證、收件者、完整設定或未授權SVG/CSS。

## 2. 原生參數與前後端責任

- 每槽具有穩定身份；名稱可重複/可改，不能作身份或Entity ID推算依據。
- integration產生原生Number/Switch/Sensor等Entity，使用者可從HA原生前台操作，不強迫安裝Card，也不要求手動建立一批Helpers。
- 後端為參數、流程、星期、權限、運行狀態與安全判斷的唯一權威；Card只編輯/顯示/呼叫語意操作，不直接控制底層馬達或在瀏覽器持有關泵計時器。
- Card外觀設定與後端作業設定分開。流程/群組參數保存需驗證、原子提交與版本衝突處理；取消/預覽不致動，未保存草稿不改運行。
- 保留P1已發布契約與影子模式邊界，控制能力另以明確版本/能力宣告擴充，舊Card不支援時安全拒絕。

## 3. 開關與啟動入口：已定案

| 控制 | 必要行為 |
|---|---|
| 自動化總開關automation_enabled | 持久允許/停用本槽控制；ON不自行啟動，OFF阻擋新工作並安全停止擁有的工作 |
| 補水/加養/加酸/獨立攪拌四子開關 | 決定哪些階段納入有效流程；不是一次性啟動旗標 |
| 獨立stage_link | **取消**；不保留另一個相同用途的多階段許可或簡易鏈結模式 |
| uninus_nutriculture.start_flow | 保留此整輪啟動服務名稱；執行已保存流程，P2 已註冊，共用 gate／payload 依 P2 及 P3A-v1 契約 |
| 原生整輪運行Switch（flow_run語意key） | ON請求一次整輪；OFF正常停止本輪，不修改總/子設定；正常完成自動OFF |
| 單階段啟動 | 只執行明確指定階段，不隱含接續，仍遵守同一星期與安全gate |
| 正常停止/急停/復歸 | 分開；停止或再ON都不解除故障或自動續藥 |

整輪服務與Switch共用後端受理/執行與狀態來源。外部服務啟動也同步Switch為ON；運行/合法等待保持ON，同槽重複ON不重啟、不再排一輪、不追加劑量。停止未確認不得立即假報OFF，需顯示stopping及真實故障/未知狀態。快速OFF→ON不能繞過停止確認；HA重啟不因恢復舊ON而致動。

總OFF保留子開關、流程、星期、參數及配方；再ON不續跑/補跑。手動Switch不是總開關，也不是星期或安全豁免。所有入口包含原生HA、Card、單階段及外部服務均須經同一授權/安全gate。

## 4. 流程與UI：已確認的能力要求

- 補水、加養、加酸、獨立攪拌的執行順序、合法重疊、相對時序/延遲及開始條件必須可由使用者調整，不固定原站拓撲。
- 最小可用UI必須足以表達順序、並行與條件，不只拖曳串行列表；提供階段列、開始規則、相對延遲、每階段星期及有效流程預覽，支援按鈕/鍵盤或下拉操作而非只靠拖曳。
- 後端以有界、具型別的流程模型驗證/執行；循環、自依賴、缺參照、無期限等待與無法滿足的資源依賴必須拒絕或明確阻擋。禁止任意程式碼/底層service注入。
- P3c 首個有界模型已由 P3C_FLOW_CONTRACT.md §7 凍結為四個唯一階段列，含三種開始規則、有限條件與略過/失敗傳播，不再列為R02未決。這不是任意DAG或重複階段的宣稱；進階編輯能力保留P5，不以此刪掉完整產品方向。
- 流程/星期保存預設下一輪生效，運行綁定明確revision；總/子OFF、急停、來源失效及收緊安全限制必須即時生效，不能被舊計畫覆蓋。
- 可要求並行不代表物理設備一定可同時執行；UI需區分計畫重疊與實際等待資源，不繞過酸/養泵限制、必要循環/混合及劑量/期限。
- disabled、skipped_weekday、blocked_dependency、waiting_resource、running、completed、aborted與fault需明確區分。略過不能偽造實際開始/成功完成事件或品質合格。

## 5. 每階段星期：已定案

- 四階段各自可複選星期一至日，全選代表每天，空集合代表無允許日，不硬編碼原加養星期。
- **每階段實際開始前**依HA設定時區檢查當地星期，包含依賴、相對延遲及資源等待之後；不採整輪開始日固定資格。
- 已開始的階段跨午夜不突然停泵；下一階段按其真正開始日檢查，安全限制持續生效。
- 整輪服務、手動Switch與單階段同樣遵守；本次不新增手動忽略星期選項。
- 不允許時略過/依賴阻擋，不等待至下個允許日、不自行建立週期排程。具體略過傳播已由P3c有限圖契約凍結，R02不再當作使用者待決策。

## 6. 排程、安全與品質界線

- **外部擁有何時啟動整輪的排程**；本整合只提供啟動及可觀察的結果，不內建時刻/cron/日曆排程器、不匯入/管理Scheduler工作、不管理外部腳本或旁支，也不自動補跑。
- 單輪內脈衝、混合、採樣、資源等待、重試及安全期限仍由後端管理，不因排除排程器而移除。
- 最低液位、必要循環/混合、來源新鮮度/品質、物理輸出所有權、單次/累積劑量與最大期限不可被UI或操作入口繞過。
- 關閉獨立攪拌不等於取消加藥必需混合；關閉補水也不允許低液位加藥。
- 整輪受理、實際啟動、完成、品質合格、灌溉許可是不同結果。過期、故障、略過、中止不能自行轉成備妥；通知確認不解除急停，通知失敗不阻擋安全停止。
- 不盲目續藥、不從定時Entity名稱推定韌體斷線保護；物理能力與安全值需明確校驗。

## 6.1 控制目標與可調安全參數：本次已確認

- pH/EC採上下限平均目標停止繼續投藥：EC達到/高於中點停止加養，pH達到/低於中點停止加酸；優先避免過量/超出界限，慢感測需脈衝、混合等待及有效新讀值再評估。停止投藥不等於穩定完成。
- 安全門檻與時間/劑量限制盡可能用integration-owned Number/原生設定讓使用者前台調整，不要求現在逐項決定固定值。現有目標上下限/階段時間不代表已有脈衝、最低安全液位、累積劑量與整輪期限。
- 農藝危險門檻可調，初始預設採原HA實際條件：pH<3.8、EC>1.3mS/cm、pH>6.8持續10分鐘告警；不是EC通知誤寫的1.5，也不照搬缺陷。
- 完整已有/缺少參數與語意見[CONTROL_PARAMETERS.md](CONTROL_PARAMETERS.md)。D01已定案；可調方向/危險預設不再列為需使用者決定的阻擋項目，具體工程介面與設備能力仍需驗證。

## 7. 決策狀態與剩餘工程設計

以下保留原始 ID，但區分已凍結工程策略、後續設計與設備 commissioning；不是全部等待使用者決策，也不是完成清單。D01、R01及D03/R03核心政策已確認，不列入未決；已確認的Switch與星期規則不可因其他細節尚待定而重新打開。

| ID | 現況／剩餘設計與校驗 | 適用邊界 |
|---|---|---|
| D02 | P3a 脈衝／必要混合／採樣／穩定／限制欄位已由 P3A-v1 凍結；P3b 酸欄位及原生執行已接通並完成兩審，實際設備校正仍需 commissioning | P3a 契約已定；完整 P3 |
| D04 | P3c 已凍結並驗證執行／等待／整輪／共用循環期限與accepted快照，詳P3C_FLOW_CONTRACT；物理C−F仍需commissioning | P3軟體已交付／設備接管前 |
| D05 | 每槽最低安全液位明填 commissioning，已定而非等待通用數值；來源幾何／物理量程需現場核對 | 設備接管前 |
| D06 | 受理／忙碌／去重及P3c跨階段資源ownership已凍結並驗證；跨槽共享輸出不可默認允許，完整多槽產品矩陣留P5 | P3已交付／P5隔離驗收 |
| D07 | P3a 必要 ph/ec/level 與來源有效性已凍結；後續階段／選配 err 映射另行工程設計 | 完整 P3 |
| D08 | 危險預設、可調與高 pH 僅告警已定；加養原生告警原因已本機接通，對外通知／冷卻仍屬 P4 | P3 安全、P4 通知 |
| D09 | 可選水溫/通訊來源、歷史/週期欄位與資料取得；是否提供的能力保留，具體介面待定 | P5前 |
| D10 | Registry 身份與設備保護聲明已凍結；未知物理別名及實際硬體最大 ON 需 commissioning 核對 | 設備接管前 |
| D11 | 原十個 Number、十三 dosing 參數與 CAS 已凍結；P3b 酸／獨立混合／安全欄位與 S4 CAS 已接通並完成兩審；P3c 流程擴充已接通並完成兩審，不含外部排程管理 | 完整 P3／P4 |
| R02 | P3c四唯一row、previous-started/finished依賴、skip/blocked傳播與七日Preview已依有限圖契約凍結、交付；不是等待使用者再定API | P3軟體已交付，進階圖保留P5 |
| R04 | start_flow／原生flow_run同受理、S5參數/計畫雙namespace CAS、accepted run revision及取消/停止真值已凍結並驗證 | P3軟體已交付 |

使用者已明確確認平均目標控制、危險預設採原HA並可調；其他原站秒數/門檻仍須標示用途及設備校驗，不擴大解讀為通用安全背書。已凍結工程策略以具體 P2/P3a 契約為準；未覆蓋部分列工程待辦，不反覆要求使用者選 API／鎖／CAS。硬體聲明不得用隔離測試取代。跨庫文件保持同步，Issue 的遠端狀態須另行讀回，不以本機文件假稱已更新。

## 8. 開發與交付規則

- P2：總/子開關、start_flow與原生運行Switch共用入口、補水及安全骨架；未支援階段不可假啟用。
- P3：可配置四階段/星期/依賴、加藥/混合/仲裁及最小UI，不將核心可配置能力全延至P5。
- P4：配方、通知、品質/完成/許可與外部互通；P5：進階視覺化編輯、手機/鍵盤、歷史/診斷、多槽與實際HACS/原生UI驗收。
- 保留完整產品範圍，先交付最小功能不等於刪除後續能力。P2–P5開放Issue是待開發，不全是待使用者選擇。
- 行為變更先測試後實作；整合後依序SPEC與品質/安全審查，驗證Card→真實後端契約。區分隔離測試、CI、發布、部署與實機驗收，不能互相替代。
- 本輪依使用者授權繼續 P4a 配方功能，保留P1–P3 Number/監測/控制wire；不重開P3四輪修補。文件/程式推送不等於部署或實機驗收。

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

## P4a 已交付範圍（兩審、出版與精確HEAD CI已完成；非完整P4／實機）

- [參數配方契約](P4A_RECIPE_CONTRACT.md)
- 原生Options與Card共用entry-owned UUID配方庫：建立/編輯/選擇/刪除二確認，Save/Cancel不改運行參數，Apply原子更新既有10參數且零致動。不能變更commissioning、Enable、fault、流程、星期或裝置保護。
- 本slice只交參數配方；P4b品質/完成/許可已實作並兩審；完整配方擴充及P4c外部結果/通知仍待後續，不標全P4完成；舊S1–S5 ready_for_irrigation固定false；新quality_v1／唯讀permit有效時可True。
- 不新建通用測試框架，不重做已交付P3，不用物理驗收待辦阻擋隔離軟體開發。每個主要行為真RED→GREEN、一次整合SPEC→品質；P4a最多兩輪具體repair，P3的4/4歷史不重置。

## P4b 來源完成（兩審與本機隔離驗證；出版與實機分開）

以[P4B_QUALITY_CONTRACT.md](P4B_QUALITY_CONTRACT.md)與[P4B_QUALITY_API_SCHEMA.json](P4B_QUALITY_API_SCHEMA.json)為唯一新介面契約。原生Options／Card可調品質策略；品質、整輪必要完成及唯讀灌溉許可分離，新樣本穩定、真整輪與輸出閉合、期限／失效撤銷與不復活必須端到端驗證。舊S1–S5與recipe_v1保持，不以舊ready欄位當新授權。P4b修復預算已用4/4，不重置或另開第五輪；P4a2/2與P3歷史4/4不重置；P4c、P5及另行授權的實機／HACS／發行仍保留。

## P4b 現行操作與交付界線

見[P4b原生／Card操作與唯一權威](P4B_OPERATION.md)。P4b source實作、兩審與本機隔離驗證完成，不等同已push、hosted CI、HACS或實機驗收。P4c通知/結果、P5進階體驗、兩槽皆commissioned與shared-output實機驗收仍pending；Issue #4維持OPEN。修復預算4/4不重置。
