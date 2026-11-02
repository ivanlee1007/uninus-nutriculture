# UNiNUS Nutriculture — 分階段開發與驗收契約

## 核准產品方向與授權界線

產品由 `ivanlee1007/uninus-nutriculture`（HA integration）與 `ivanlee1007/uninus-nutriculture-card`（Lovelace Card）組成。兩個 repository 初始維持私人。允許本機開發、測試與推送 GitHub；不代表允許對原農場 HA 寫入、部署、停止舊自動化、操作馬達或建立正式 release。原站維持唯讀。本專案不得包含原站 URL、Token、使用者識別、完整設定匯出或未授權複製的 SVG/CSS。

完整產品目標不因先交付最小功能而縮減：既有 MQTT Entity 重用、多槽、integration-owned 可調參數、補水/加養/加酸/混合流程、補水與加養跟隨重疊、安全互鎖/急停/復歸、資料有效性、重啟復原、排程、下游灌溉許可、通知與響應式 Card。不得將配置成功或綠色測試當作實機驗收。

## 分階段路線圖

| 階段 | 可用功能 | 必要驗收 | 禁止誇大 |
|---|---|---|---|
| P1 最小可用影子監測 | 原生設定感測器、10 個 Number 參數、持久參數驗證、品質診斷、唯讀來源、基本 Card 顯示及單項調參 | 原生 HA 隔離設定/Number/重載、無設備呼叫、實際 shipped Card 操作及窄寬版測試 | 不會控制任何馬達、不會授予灌溉許可、不宣稱已上線 |
| P2 補水與安全控制 | 明確啟用控制、補水低高標、事件驅動即時停止、逾時、確認回饋、急停鎖定/明確復歸、輸出單一所有權 | 假時鐘/故障注入/取消/卸載/重啟；實機僅另行授權後 | 不得靠瀏覽器計時或自動啟用控制 |
| P3 加養/加酸/混合 | 單次及累積加藥上限、等待混合、連續穩定判定、跟隨模式與共用循環馬達仲裁、成組原子參數儲存 | 明確安全狀態機；故障/並行/目標改動/拒絕參數不留半套變更 | 不沿用僅 pH > 最低安全值即備妥 |
| P4 作業整合 | 配方/週間規則/排程、流程完成與品質合格與灌溉許可分離、通知、既有 helper/滴灌相容遷移 | 舊新控制器不雙重控制；相容與拒絕路徑；完整連動 | 通知確認不等於故障解除 |
| P5 完整產品與發行候選 | 完整流程圖、手機/桌面、視覺化編輯器、診斷/歷史、可運作多槽隔離、文件/備份與遷移、HACS 發行準備 | 全流程/安全矩陣/原生 UI/跨倉庫版本相容；另行核准實機試運轉與發行 | 私人庫 HACS 檢查限制、未授權 release/部署均須明示 |

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
- `parameter_entities: {<10 keys>: "number..."}`，以 registry 實際 ID 建立，不能從名稱猜測；停用/刪除者不提供可寫 target。
- `parameters: {<10 keys>: <finite number>}`
- `reasons: [<bounded stable reason strings>]`
Card 可讀取來源即時值；以 status sensor 作為單一配置入口。缺少/不相容 status/schema、非 shadow、錯誤 target、缺 Number/不可用、尚無 hass 時都必須清楚顯示且不得誤寫其他 Entity。

Card config：`{type: "custom:uninus-nutriculture-card", entity: "sensor.<status>", title?: "...", show_parameters?: true}`。卡片顯示繁體中文、影子模式/不控制設備提示、三個來源值/單位、品質原因、10 個可編輯參數及每項明確保存。不得在重繪/遙測更新時抹掉正在輸入的草稿；保存錯誤保留草稿；換槽/移除/重新設定不可把舊草稿送往新 Entity；loading/重複點擊有保護。使用 textContent 等安全顯示，無 token/localStorage。卡片 picker、基本 editor、無依賴單一 JS 發布檔、320px/寬版可用，不提供未實作的操作按鈕。Demo 必須明示模擬，不使用原站資訊。

## 執行與審查

- TDD：每個新業務行為先有真正行為失敗再實作；保留精簡 RED/GREEN 手記與原始命令結果，匯入/語法錯誤不算行為 RED。
- integration 與 Card 可在檔案互不重疊的兩倉庫並行實作；共享介面修改必須先同步契約。
- 整合後先獨立 SPEC 審查，再獨立品質/安全審查；最多兩次具體修正循環，仍有阻擋則保留成果並明示。
- 至少執行原生 HA 隔離測試與 shipped Card 瀏覽器測試。mock、原生隔離、跨層 bridge、GitHub CI、正式站驗收分別記錄，不互相替代。
- 本階段不發布 tag/release，不部署 HA。後續階段保留 GitHub issue 與明確驗收標準，不能因 P1 完成就標示全產品完成。
