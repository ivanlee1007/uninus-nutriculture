> 現行來源：P5b同槽pH／EC／液位歷史已完成正式來源交付（Backend `53e4f0b5dceb2cbd8c76bcef0470636d37868e41`、Card `863406040b2537f57001caa0d59c56f16af97a67`；精確CI `42476705488`／`42476693050` 已核驗）。P5c重要UI已完成隔離整合與獨立SPEC／品質安全兩審；來源出版與本提交hosted CI分別按實際核驗結果為準，不冒用舊批准。最新順序：重要UI → 另行確認測試機與致動範圍後實機測試 → 其餘P5。完整P5仍保留，未部署、HACS、tag或release；P3／P4／P5a／P5b結案修補額度不重置。


> 導航優先序：FUNCTIONAL_PARITY_REVIEW.md是舊commit的歷史F/D盤點，不代表目前沒有控制能力或所有D/R仍未決；不改寫其原文。P3C_FLOW_CONTRACT.md頂部提案語句屬來源歷史，現行以其§7已採納補充及本輪交付狀態為準，不再次凍結或重審。
# UNiNUS Nutriculture — 分階段開發與驗收契約

> 最新定案：取消獨立stage_link；各階段實際開始前檢查星期；增加原生整輪運行Switch並保留start_flow。以[已確認控制決策](CONTROL_DECISIONS.md)為準；P2 已發布且保留 P1 wire；P3a/P3b/P3c軟體來源與精確HEAD CI已交付；P3實機commissioning未驗，P4a已實作並兩審，完整P4–P5尚未完成。

## 核准產品方向與授權界線

產品由 `ivanlee1007/uninus-nutriculture`（HA integration）與 `ivanlee1007/uninus-nutriculture-card`（Lovelace Card）組成。兩個 repository 已依使用者要求改為 Public；初次 P1 交付時為私人，歷史證據不回寫。P5a首片已完成正式軟體來源交付。P5b同槽pH／EC／液位歷史完整使用路徑已正式交付；目前P5c依最新順序開發重要runtime／事件時間軸UI，沿既有原生Entity與Core History／Recorder，不改backend產品／schema；不操作外部HA、不部署、不建立tag/release。原站維持唯讀。本專案不得包含原站 URL、Token、使用者識別、完整設定匯出或未授權複製的 SVG/CSS。

完整產品目標不因先交付最小功能而縮減：既有 MQTT Entity 重用、多槽、integration-owned 可調參數、總開關＋四階段子開關、使用者可配置順序／重疊／相對時序與每階段星期的流程組合、補水/加養/加酸/混合流程、補水與加養跟隨重疊、安全互鎖/急停/復歸、資料有效性、重啟復原、外部整輪啟動入口、下游灌溉許可、通知與響應式 Card。不得將配置成功或綠色測試當作實機驗收。

## 目前狀態與規格優先序

- P1 程式已交付與通過原生隔離、瀏覽器、跨層對接及對應 commit 的 CI；仍未部署原站、未做實體設備接管。P2 補水已發布並有隔離／跨層驗證；P3a 加養及群組設定本機已接通、已通過兩審並交付功能來源／CI，P3b 酸／獨立混合已接通並完成兩審；P3c 可編流程已接通並完成兩審，P4a／P4b／P4c及P5a首片軟體來源亦已交付；完整P5未完成，不將候選誇稱全產品或實機完成。
- [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md)為跨倉庫共同產品規範；本計畫為分期/驗收契約；[CONTROL_SWITCHES.md](CONTROL_SWITCHES.md) 定義啟用與組合語意；[FUNCTIONAL_PARITY_REVIEW.md](FUNCTIONAL_PARITY_REVIEW.md) 保留原始行為、既有規格缺口與待決策，不能將待定項當成已核准演算法。[FLOW_DESIGN_RESEARCH.md](FLOW_DESIGN_RESEARCH.md) 為本次流程/UI研究依據；R01已確認取消獨立stage_link，R03已確認階段實際開始前檢查星期；新增整輪運行Switch入口。R04 及 P3a 策略已由具體契約凍結；P3c 有限圖語意已依 P3C_FLOW_CONTRACT.md 凍結，不是等待使用者重複回答已定政策。
- 歷史P2新增版本化控制，保留P1 schema v1、Number參數上下限與舊監測安全語意。歷史 P1 驗收證據與凍結來源不改寫。

## 有限後續順序（不以安全切片取代主要功能）

1. （P3a 已完成）收斂既有程式的具體安全阻擋；不另建測試框架或追求無界笛卡兒積。凍結完整候選後，獨立 SPEC→品質，最多兩輪具體修正。
2. （P3b 已接通並完成兩審）酸與獨立攪拌的可操作原生／Card 路徑，重用同一授權、採樣、關閉與必要循環所有權，不複製互相矛盾的計時器。
3. （P3c 來源已接通並完成兩審）完整四階段可編順序／合法重疊／條件／相對延遲／星期及最小編輯與預覽 UI；不以固定補水→加養流程代替。
4. P4a已實作並通過兩審：原生Options與Card參數配方保存/原子套用；P4b品質/完成/許可已實作並兩審，本機隔離驗證完成；P4c外部結果/通知軟體來源與exact-HEAD hosted CI／產物核驗已正式交付；P5進階視覺化與完整發行體驗保留。P3未授權實機項不作隔離P4前置。

[目標對齊](GOAL_ALIGNMENT.md)記錄本次現況修正；[P3A_NUTRIENT_CONTRACT.md](P3A_NUTRIENT_CONTRACT.md)僅限定加養切片，不縮減完整 P3。

## 分階段路線圖

| 階段 | 可用功能 | 必要驗收 | 禁止誇大 |
|---|---|---|---|
| P1 最小可用影子監測 | 原生設定感測器、10 個 Number 參數、持久參數驗證、品質診斷、唯讀來源、基本 Card 顯示及單項調參 | 原生 HA 隔離設定/Number/重載、無設備呼叫、實際 shipped Card 操作及窄寬版測試 | 不會控制任何馬達、不會授予灌溉許可、不宣稱已上線 |
| P2 補水與安全控制 | 總開關、四子階段模型與未支援 gate、整輪/單階段/停止/急停分離、外部整輪啟動服務與原生flow_run Switch共用入口、版本化計畫/結果模型；補水低高標、事件停止、逾時/回饋、輸出所有權 | CONTROL_SWITCHES 的 P2 案例；目標/權限/停用/急停/忙碌/重複請求及版本測試，假時鐘/故障注入/取消/卸載/重啟；驗證R01取消鏈結及整輪Switch，先凍結R04相關契約 | 未支援階段不得假啟用；服務受理不等於已運行/完成；不靠瀏覽器計時 |
| P3 四階段可配置流程 | 補水/加養/加酸/獨立攪拌的可配置順序、合法重疊、相對延遲/條件依賴、各階段七日複選；有界 typed 依賴圖、加藥上限/混合/穩定/共用馬達仲裁、成組原子參數；最小階段列編輯與預覽 | C05–C10、C12 完整組合/星期/略過依賴/非法圖/版本衝突驗收；依已確認 R03 於實際階段開始前查星期；沿 P3A-v1 已凍結策略，P3c 有限圖語意已凍結；儲存不致動，Card 離線後後端仍運行 | 不固定原順序或加養一二五六；核心可配置能力不能全延至 P5；停用不是完成 |
| P4 作業整合 | 配方、外部 action/結果互通、通知、完成/品質/灌溉許可介面與可選相容資料；外部自行接線 | 外部服務與原生入口共用 gate，受理/運行/完成/品質/許可分離，通知失敗不阻擋停機；原19排程/8腳本只作歷史與雙控風險 | 不含內建排程器、排程匯入或外部腳本/旁支管理；通知確認不解除故障 |
| P5 完整產品與發行候選 | 進階流程圖、手機/桌面/鍵盤、視覺化編輯器（可選節點畫布）、可選水溫/通訊診斷、歷史、可運作多槽隔離、文件/備份、HACS 發行準備 | 全流程/安全矩陣/原生 UI/跨倉庫版本、實際 HACS 安裝驗收；實機與發行另行核准 | Public 不等於 HACS 已驗收或已入預設清單，未授權 release/部署均須明示 |

## P1 Frozen Contract v1

Domain: `uninus_nutriculture`; card type: `custom:uninus-nutriculture-card`.

每個 entry 代表一座槽，設定名稱與 ph/ec/level 三個既有 sensor Entity。只讀取來源、不建立 MQTT 客戶端、不綁定任何馬達。來源移除、unavailable/unknown、非有限數值、資料過期均為不合格。原生 Entry ID 提供穩定身份，名稱不是 identity。感測新鮮度必須定期重算，且 source entity 的移除會更新品質。

10 個 Number keys 與預設：`level_low=2.25`, `level_high=2.4` (m), `ph_low=5.4`, `ph_high=5.8`, `ec_low=0.8`, `ec_high=0.9` (mS/cm), `refill_timeout=190`, `ec_timeout=90`, `ph_timeout=190`, `mix_duration=10` (min)。上下限嚴格 low < high；數值必須有限且符合公開 min/max/step。時間參數 P1 僅儲存供後續使用，不暗示控制已實作。使用 Config Entry options 作為持久設定，保存成功後原生 Number 與品質同步更新；拒絕更新不得改變其他參數。來源綁定可透過原生 Options flow 調整。P1 不需要自訂寫入 service，Card 使用標準 `number.set_value` 單項保存；跨欄位原子套用列入 P3，不可把單項保存冒充原子批次。

Status Sensor state：`within_range` / `out_of_range` / `invalid`。
Status attributes（JSON scalars/maps only）:
- `schema_version: 1`
- `mode: "shadow"`
- `ready_for_irrigation: false`（P1 永不變 true；品質合格不是灌溉許可）
- `source_entities: {ph: "sensor...", ec: "sensor...", level: "sensor..."}`
- `parameter_entities: {<10 keys>: "number..."}`，以 registry 實際 ID 建立，不能從名稱猜測；停用/刪除/缺失/unavailable/unknown/非數字/非有限 state 不提供可寫 target；健康恢復後重現同一實際 ID，字典可少於十項。
- `parameters: {<10 keys>: <finite number>}`
- `reasons: [<bounded stable reason strings>]`
Card 可讀取來源即時值；以 status sensor 作為單一配置入口。缺少/不相容 status/schema、非 shadow、錯誤 target、缺 Number/不可用、尚無 hass 時都必須清楚顯示且不得誤寫其他 Entity。

Card config：`{type: "custom:uninus-nutriculture-card", entity: "sensor.<status>", title?: "...", show_parameters?: true}`。卡片顯示繁體中文、影子模式/不控制設備提示、三個來源值/單位、品質原因、10 個可編輯參數及每項明確保存。不得在重繪/遙測更新時抹掉正在輸入的草稿；保存錯誤保留草稿；換槽/移除/重新設定不可把舊草稿送往新 Entity；loading/重複點擊有保護。使用 textContent 等安全顯示，無 token/localStorage。卡片 picker、基本 editor、無依賴單一 JS 發布檔、320px/寬版可用，不提供未實作的操作按鈕。Demo 必須明示模擬，不使用原站資訊。

## 總/子開關要求（P3c 四階段已接通）

- 持久總開關＋四子開關；取消獨立鏈結，新增整輪運行Switch（ON啟動、OFF正常停止、完成自動OFF），與start_flow共用後端，不等同總開關。Enable、單階段啟動、整輪、停止本輪、急停、復歸分離。
- 總 OFF 阻擋所有本整合控制入口，撤銷舊任務並確認擁有的輸出安全停止；監測與調參保留。子設定、流程/星期與配方不清除；外部排程不由本整合管理；再 ON 不續跑或補跑。
- 關閉子階段可組合流程；執行中停用要即時中止並正確處理共用輸出及安全相依。略過/中止不得冒充完成或可灌溉。
- 未支援階段拒絕啟用；無合法階段不運行；關閉獨立攪拌不能繞過加藥最低混合前提。
- 關閉自動化、停止本輪、故障鎖定具有不同狀態。原生 Entity、Card、外部 automation/服務共用後端 gate，不能只隱藏前端按鈕。
- 具體語意與 C01–C14 驗收以 [CONTROL_SWITCHES.md](CONTROL_SWITCHES.md) 為準。

## 原始功能相容性與決策門檻

功能對照以 [FUNCTIONAL_PARITY_REVIEW.md](FUNCTIONAL_PARITY_REVIEW.md) 為準。每個階段實作前，將其中列出的待定選項轉為明確核准決策及測試；不以一般「安全控制」文字代替作業規則。原始秒數/星期/門檻是盤點基準，不是本文件自行認定的新設備安全預設；最低液位、劑量及時間上限須在接管前校驗。

尤其不可漏掉已確認取消鏈結、整輪Switch與服務共用入口、單階段啟動、可配置跟隨/順序/重疊與每階段星期、脈衝/混合等待、穩定次數、跟隨逾時繼承、直接/定時輸出別名、備妥與供外部滴灌使用的許可介面、超標告警、水溫/通訊/歷史、Helpers/Timer 的相容策略。既有錯誤分支、誤名停止腳本及停用程式不得當作必要行為照搬。

## 執行與審查

- TDD：每個新業務行為先有真正行為失敗再實作；保留精簡 RED/GREEN 手記與原始命令結果，匯入/語法錯誤不算行為 RED。
- integration 與 Card 可在檔案互不重疊的兩倉庫並行實作；共享介面修改必須先同步契約。
- 整合後先獨立 SPEC 審查，再獨立品質/安全審查；最多兩次具體修正循環，仍有阻擋則保留成果並明示。
- 至少執行原生 HA 隔離測試與 shipped Card 瀏覽器測試。mock、原生隔離、跨層 bridge、GitHub CI、正式站驗收分別記錄，不互相替代。
- 本階段不發布 tag/release，不部署 HA。後續階段保留 GitHub issue 與明確驗收標準，不能因 P1 完成就標示全產品完成。

## 未決策與待開發的區分

已確認結論、已凍結工程策略與剩餘設計以[共同開發規範](DEVELOPMENT_SPEC.md)第7節及具體 P2/P3a 契約為準；Issue #6 保留歷史登錄，不將未完成實作等同等待使用者重新核准。R01取消鏈結、D03/R03星期時點與原生整輪Switch入口已定案，不重新列為未決。P2–P5開放Issue代表未完成的開發/驗收，不代表所有需求仍待選擇。

控制目標與前台可調安全參數已補入[CONTROL_PARAMETERS.md](CONTROL_PARAMETERS.md)：平均目標停止投藥、危險門檻預設採原HA且可調；D01已定，不阻擋繼續開發。

## P2候選驗證

P2補水候選已通過隔離測試及獨立SPEC／品質安全審查；舊P1監測介面保留。P3a 加養已交付並通過兩審及功能來源 CI；加P3b 酸／獨立混合已接通並完成兩審，P3c 可編流程已接通並完成兩審；未部署原HA、未做物理設備或HACS安裝驗收。詳見[P2_ACCEPTANCE.md](P2_ACCEPTANCE.md)。

## P3c 現行流程與原生操作

- 四列必須各含一次 `refill`、`nutrient`、`acid`、`mix`。可改順序；第一列為 `flow_start`，其餘可選 `flow_start`、`after_previous_started` 或 `after_previous_finished`，延遲相對於該錨點，不是任意腳本或排程時間。合法 overlap 仍受後端輸出資源、最低液位、採樣及安全 gate 約束，不保證同時致動。
- 必要加藥循環與獨立 mix 不同：停用獨立 mix 不會解除加藥必要循環。共用 circulation 由後端仲裁；不能以 Card 或其他入口繞過 ownership。
- 有限 condition 僅 `level` / `ph` / `ec` 的 `gte` / `lte` 有限數值，或 `none`；不是 template。液位用 m（0–10）、pH 0–14、EC 用 mS/cm（0–20）。每列等待期限與整輪期限有界。
- 到「設定 → 裝置與服務 → UNiNUS Nutriculture → 該槽的設定／選項」，勾選 **Open flow plan editor (no settings saved)**（`flow_plan`），開啟 **Flow plan / 流程計畫**。這是原生 selector 表單，不必貼 JSON；進入編輯器不會保存同頁其他設定。
- 每列有 stage、start rule、delay seconds、wait timeout seconds、condition source/operator/value 及 weekdays；`run_timeout_seconds` 為整輪期限。用 **Save / seven-day Preview / Cancel / move row up or down** 的 `row_0_down` / `row_1_up` 等動作調序；規則隨列保留，調序後第一列仍須 `flow_start`。
- `action=preview` 讀草稿，列出七日有效流程；`save` 才以版本衝突檢查原子保存，作用於下一輪，不啟動設備；`cancel` 不保存。其他頁面已改設定時須重開並協調，不能覆蓋新版本。Card 同樣提供階段列、上下移動、星期、Preview／套用／取消；參數群與流程草稿為分開 namespace。
- 每階段真正 admission 前依 **HA 設定時區** 的當地星期重查；跨午夜不沿用整輪開始日。星期是允許 gate，不會自行排程、補跑或啟動。外部 automation／`uninus_nutriculture.start_flow` 與原生整輪 Switch 共用後端；Enable 開關不是 start。
- Preview 使用相同有限依賴／略過與資源模型，反映停用、星期、條件、等待和依賴，不再只是單一 eligible 清單。未來感測、實際加藥／補水完成時刻及跨日 admission 可能未知；七日預覽不是確切時間表、成功保證或灌溉許可。無致動也不建立運行任務。
- P3c交付時永久 native suite 為 335；P4a交付時 suite 為378；R4 full 339 包含四項外加 QA probes，不屬正常 repo，不能要求乾淨 CI 收集 339。源碼兩審不取代 publication-equivalence 審核或 exact-commit hosted CI。內嵌版本未升正式發行版本；不為顯示美觀修改 bundle/hash/version metadata。

## P4a 已交付範圍（兩審、出版與精確HEAD CI已完成；非完整P4／實機）

- [參數配方契約](P4A_RECIPE_CONTRACT.md)
- 原生Options與Card共用entry-owned UUID配方庫：建立/編輯/選擇/刪除二確認，Save/Cancel不改運行參數，Apply原子更新既有10參數且零致動。不能變更commissioning、Enable、fault、流程、星期或裝置保護。
- P4a切片來源歷史（非現行整案範圍）：只交參數配方；P4b品質/完成/許可已實作並兩審；完整配方擴充及P4c外部結果/通知仍待後續，不標全P4完成；舊S1–S5 ready_for_irrigation固定false；新quality_v1／唯讀permit有效時可True。
- 不新建通用測試框架，不重做已交付P3，不用物理驗收待辦阻擋隔離軟體開發。每個主要行為真RED→GREEN、一次整合SPEC→品質；P4a最多兩輪具體repair，P3的4/4歷史不重置。

## P4b 來源完成（兩審與本機隔離驗證；出版與實機分開）

以[P4B_QUALITY_CONTRACT.md](P4B_QUALITY_CONTRACT.md)與[P4B_QUALITY_API_SCHEMA.json](P4B_QUALITY_API_SCHEMA.json)為唯一新介面契約。原生Options／Card可調品質策略；品質、整輪必要完成及唯讀灌溉許可分離，新樣本穩定、真整輪與輸出閉合、期限／失效撤銷與不復活必須端到端驗證。舊S1–S5與recipe_v1保持，不以舊ready欄位當新授權。P4b修復預算已用4/4，不重置或另開第五輪；P4a2/2與P3歷史4/4不重置；P4c、P5及另行授權的實機／HACS／發行仍保留。

## P4b 現行操作與交付界線

見[P4b原生／Card操作與唯一權威](P4B_OPERATION.md)。P4b source、兩審、出版等價、push與exact-HEAD hosted CI及下載產物核對均已完成；仍不等同HACS或實機驗收。P4c正式來源交付、出版等價、push、新exact-HEAD hosted CI及遠端／下載產物核驗均已完成；P5進階體驗、兩槽皆commissioned與shared-output實機驗收仍pending；本文件不寫入遠端Issue，完整P5仍保留。修復預算4/4不重置。

## P4c 軟體來源已正式交付；實機／HACS分開

- 以 [P4C_RESULT_NOTIFICATION_CONTRACT.md](P4C_RESULT_NOTIFICATION_CONTRACT.md) §8及 [P4C_API_SCHEMA.json](P4C_API_SCHEMA.json)優先：既有整輪trigger→穩定result_v1投影／事件；nativeOptions與Card共用私有通知權威、選native provider／事件／cooldown；default disabled。無scheduler、任意service runner或直接灌溉。
- P4c R4來源兩審、本機完整gate、出版等價、正式Card commit pin、新exact-HEAD hosted CI及遠端／下載產物核驗均已完成。P4c 4/4、P3 5/5結案，不重開產品修復。通知失敗／ACK不改安全OFF、fault、quality或permit；Core STOP與普通flow Stop分辨；明確private reconcile，不自動entry reload。
- P5a四階段視覺入口／手機鍵盤首片已交付；P5後續進階視覺與完整手機鍵盤、完整歷史／診斷、兩槽各自全流程／跨槽共output commissioning、HACS與實機仍保留；P4c必要idle低pH／高EC唯讀告警G1不延後。原F/D及歷史失敗不回寫。

## P5a 視覺工作台與操作入口

四階段關係按鈕可進入既有規則欄位，保留調序／重疊／延遲／有限條件／星期→七日後端Preview→明確套用→native讀回／重開路徑；見[P5a視覺工作台操作說明](P5A_VISUAL_WORKFLOW.md)。真隔離Core19 requests整合與修正後獨立SPEC→品質兩審已完成；既有P5a基線精確HEAD hosted CI與遠端交付核驗亦已完成；後續新候選另驗自身CI，不宣稱完整P5或實機完成。草稿示意／Preview不保證物理可行性或arrival；不增加schema、scheduler、raw IO或現場控制。

## P5b：同槽歷史（來源已正式交付）

完整使用路徑、真值／權限／生命週期與保留範圍以[P5b歷史契約](P5B_HISTORY_CONTRACT.md)為準；本片功能、整合驗收、兩審、正式來源出版與exact-HEAD hosted CI及產物核驗已完成。不重開P5a既有交付或已結案修補額度。


## P5c重要UI與後續順序（隔離整合與兩審完成）

1. **重要UI已實作並完成隔離驗證／兩審**：四階段即時運行視覺、真資源等待／略過／停止確認、HA觀察輸出、Recorder的stage／output／permit與停止原因時間軸；補齊新增畫面的手機／鍵盤與切槽一致性。沿用後端唯一權威，不把草稿當運行計畫、不把輸出狀態當物理到達、不把歷史許可當現行授權。
2. **再進行實機測試**：完成必要整合與獨立SPEC→品質後，先確認指定測試機、硬體、可連線／可致動範圍與停止條件。此排序不解除原站不連線、不讀取現場憑證、不部署的現行界線。
3. **最後補其餘P5**：選配水溫／通訊診斷、完整兩槽commissioned與共享輸出矩陣、完整HA宿主／HACS、文件／備份還原及另授發行準備；不是取消這些需求。

P5a編輯入口與P5b感測歷史已交付，不重做。P5c契約見[P5C_RUNTIME_TRACE_CONTRACT.md](P5C_RUNTIME_TRACE_CONTRACT.md)。
