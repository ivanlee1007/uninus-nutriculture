# UNiNUS Nutriculture — 分階段開發與驗收契約

> 最新定案：取消獨立stage_link；各階段實際開始前檢查星期；增加原生整輪運行Switch並保留start_flow。以[已確認控制決策](CONTROL_DECISIONS.md)為準；P2補水候選已實作，P1監測wire保留，P3–P5仍待開發。

## 核准產品方向與授權界線

產品由 `ivanlee1007/uninus-nutriculture`（HA integration）與 `ivanlee1007/uninus-nutriculture-card`（Lovelace Card）組成。兩個 repository 已依使用者要求改為 Public；初次 P1 交付時為私人，歷史證據不回寫。本輪依使用者授權繼續開發P2，包含控制程式、Card與測試；不操作外部HA、不部署、不建立tag/release。原站維持唯讀。本專案不得包含原站 URL、Token、使用者識別、完整設定匯出或未授權複製的 SVG/CSS。

完整產品目標不因先交付最小功能而縮減：既有 MQTT Entity 重用、多槽、integration-owned 可調參數、總開關＋四階段子開關、使用者可配置順序／重疊／相對時序與每階段星期的流程組合、補水/加養/加酸/混合流程、補水與加養跟隨重疊、安全互鎖/急停/復歸、資料有效性、重啟復原、外部整輪啟動入口、下游灌溉許可、通知與響應式 Card。不得將配置成功或綠色測試當作實機驗收。

## 目前狀態與規格優先序

- P1 程式已交付與通過原生隔離、瀏覽器、跨層對接及對應 commit 的 CI；仍未部署原站、未做實體設備接管。P2補水候選已接通並有隔離/跨層驗證；P3–P5尚未實作，不將候選誇稱全產品或實機完成。
- [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md)為跨倉庫共同產品規範；本計畫為分期/驗收契約；[CONTROL_SWITCHES.md](CONTROL_SWITCHES.md) 定義啟用與組合語意；[FUNCTIONAL_PARITY_REVIEW.md](FUNCTIONAL_PARITY_REVIEW.md) 保留原始行為、既有規格缺口與待決策，不能將待定項當成已核准演算法。[FLOW_DESIGN_RESEARCH.md](FLOW_DESIGN_RESEARCH.md) 為本次流程/UI研究依據；R01已確認取消獨立stage_link，R03已確認階段實際開始前檢查星期；新增整輪運行Switch入口。R02/R04及未核准細節仍待確認。
- 本輪新增版本化P2控制，保留P1 schema v1、Number參數上下限與舊監測安全語意。歷史 P1 驗收證據與凍結來源不改寫。

## 分階段路線圖

| 階段 | 可用功能 | 必要驗收 | 禁止誇大 |
|---|---|---|---|
| P1 最小可用影子監測 | 原生設定感測器、10 個 Number 參數、持久參數驗證、品質診斷、唯讀來源、基本 Card 顯示及單項調參 | 原生 HA 隔離設定/Number/重載、無設備呼叫、實際 shipped Card 操作及窄寬版測試 | 不會控制任何馬達、不會授予灌溉許可、不宣稱已上線 |
| P2 補水與安全控制 | 總開關、四子階段模型與未支援 gate、整輪/單階段/停止/急停分離、外部整輪啟動服務與原生flow_run Switch共用入口、版本化計畫/結果模型；補水低高標、事件停止、逾時/回饋、輸出所有權 | CONTROL_SWITCHES 的 P2 案例；目標/權限/停用/急停/忙碌/重複請求及版本測試，假時鐘/故障注入/取消/卸載/重啟；驗證R01取消鏈結及整輪Switch，先凍結R04相關契約 | 未支援階段不得假啟用；服務受理不等於已運行/完成；不靠瀏覽器計時 |
| P3 四階段可配置流程 | 補水/加養/加酸/獨立攪拌的可配置順序、合法重疊、相對延遲/條件依賴、各階段七日複選；有界 typed 依賴圖、加藥上限/混合/穩定/共用馬達仲裁、成組原子參數；最小階段列編輯與預覽 | C05–C10、C12 完整組合/星期/略過依賴/非法圖/版本衝突驗收；依已確認R03於實際階段開始前查星期，先凍結其他D01–D05與R02細節；儲存不致動，Card 離線後後端仍運行 | 不固定原順序或加養一二五六；核心可配置能力不能全延至 P5；停用不是完成 |
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

## 總/子開關要求（P2骨架已實作，P3階段待接入）

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

已確認結論與尚未定案的11項決策以[共同開發規範](DEVELOPMENT_SPEC.md)第7節及兩庫Issue #6為準。R01取消鏈結、D03/R03星期時點與原生整輪Switch入口已定案，不重新列為未決。P2–P5開放Issue代表未完成的開發/驗收，不代表所有需求仍待選擇。

控制目標與前台可調安全參數已補入[CONTROL_PARAMETERS.md](CONTROL_PARAMETERS.md)：平均目標停止投藥、危險門檻預設採原HA且可調；D01已定，不阻擋繼續開發。

## P2候選驗證

P2補水候選已通過隔離測試及獨立SPEC／品質安全審查；舊P1監測介面保留。P3加養/加酸/混合及進階流程編輯仍待實作；未部署原HA、未做物理設備或HACS安裝驗收。詳見[P2_ACCEPTANCE.md](P2_ACCEPTANCE.md)。
