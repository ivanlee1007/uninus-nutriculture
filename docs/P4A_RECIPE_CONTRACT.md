# P4A-v1 配方參數管理契約（2026-11-05 凍結）

## 0. 目標、優先序與邊界
這是使用者「review專案開發目標有無偏離，繼續後續開發」授權下的下一個可用交付，不是重開 P3。P3c 軟體來源、兩審、出版等價與 exact-HEAD CI 已完成；Issue3只餘實機commissioning項，不能阻止隔離P4開發。P3修補額度4/4不重置；本P4a新功能的整合SPEC→品質最多兩次具體修正，超額升級。
首個有用路徑：原生Options與shipped Card建立/編輯/刪除/選擇配方→明確套用→後端一次更新既有10個Number參數→原生與Card讀回；保存、選擇、取消、套用均不啟動輸出。不是只有服務或資料模型。
完整P4仍包含後續配方擴充、完成/品質/灌溉許可、外部結果/通知；P5進階圖/歷史/診斷/HACS/多槽產品驗收均保留。v1僅參數配方，不假稱化學配比/流量校正或整個P4已完成。
無新stage_link/內建scheduler/外部腳本管理；不存取原HA/現場認證、不部署/接管/tag/release。不自動確認物理保護。原兩庫、歷史evidence及P3凍結樹只讀，開發僅本隔離兩庫。

## 1. 配方內容與身份
每槽獨立entry.options.recipe_catalog；缺省為{schema_version:1,revision:0,recipes:[],last_applied:null}，讀取/開表不寫入、不升版、不偷偷migration。只支援已顯式保存schema5流程的entry；其他版本服務拒settings_schema_mismatch，Card不提供假能力，不改舊S1–S5 wire。
recipe record精確{id,name,parameters}：id由後端建立UUID32 lowercasehex，不由名稱/索引生成；同名可存在、改名id不變、跨槽同名隔離。name去首尾空白後1–80字、不許C0控制字元。每槽上限100筆（v1明示界限），不新增分頁框架。
parameters必須精確既有10 keys及SPECS合法數值/step/low<high：level_low,level_high,ph_low,ph_high,ec_low,ec_high,refill_timeout,ec_timeout,ph_timeout,mix_duration。bool/NaN/inf/非法巢狀/多餘key拒絕。儲存只驗配方數值，套用另用既有完整設定/commissioning與安全關聯驗證；不可存任意service/template/code、硬體binding、憑證、Enable、fault、星期、流程或裝置保護聲明。
last_applied=null或精確{recipe_id,name,parameters}，為歷史快照而非灌溉/品質許可。刪除/改名配方不篡改這個歷史快照；API parameters_match依目前10參數對歷史快照比較，手動Number改值後顯示「已偏離上次套用」，不捏造active recipe。IRR仍false。

## 2. 版本、鎖與唯一原子提交
catalog revision與settings_revision各自獨立。CRUD僅改catalog，不改既有settings_revision/flow_plan_revision，不影響執行；無意義相同保存不升版。Apply要求兩revision，數值確有delta才升既有settings_revision；last_applied確變才升catalog revision。相同record/參數再次Apply無意義delta不升版。
所有讀寫先authorize(active human admin)再target lookup，Tank.lock等待後再authorize並檢entry仍LOADED/active/同runtime。只受理本domain/本槽，錯ID/刪除/停用/卸載/權限撤銷/CAS拒絕時零寫入、零I/O，不輸出任意exception文字。
Apply僅閒置且無受理中任務、owners、pending I/O、leases/session時受理；忙碌拒busy，不能以套用配方造成hot止泵副作用。fault已鎖但I/O全結清時允許純設定Apply，不能清fault或Enable。
重用Tank.write_settings既有完整驗證。可加private recipe_catalog參數或拆純candidate helper，在同一同步提交段將數值+catalog/last_applied合併成一次async_update_entry；不可先改參數再第二次寫配方metadata。不要用原子catalogCRUD讓settings revision徒增。catalog metadata不改參數時也必須保留現有options全部未知/既有欄位。沒有await夾在最後授權/版本驗證與唯一commit之間；更新後publish原生Number/status。
Apply不改allowed_weekdays/flow_plan_revision/run_plan/Enable/硬體binding/protection/sources/dosing/acid/mix/safety參數；不新增輸出owner或timer。儲存、套用、刪除不改正在執行的accepted snapshot。
HA options為原生排程儲存，非fsync/crashdurable；驗證正常shutdown/finalwrite及新程序讀回，不過度宣稱斷電保證。

## 3. 閉合服務與回傳 wire
四個版本化服務，payload禁止額外keys：
- get_recipes_v1: {config_entry_id}，SupportsResponse.ONLY。
- save_recipe_v1: {config_entry_id,expected_catalog_revision,recipe_id,name,parameters}；recipe_id=null為建立、現有UUID為更新；不存在不能upsert/自造id。
- delete_recipe_v1: {config_entry_id,expected_catalog_revision,recipe_id,confirm_delete:true}；bool必須真True。
- apply_recipe_v1: {config_entry_id,expected_catalog_revision,expected_settings_revision,recipe_id}。
mutations SupportsResponse.OPTIONAL，return_response=True時皆回同一DTO；nativeCore非response呼叫也可執行，但UI使用response正式讀回。
DTO精確{schema_version:1,config_entry_id,catalog_revision,settings_revision,recipes,last_applied,parameters_match,parameters}，parameters為目前authoritative10參數，recipes依保存順序，last_applied遵§1。list空catalog只回default不寫。每次有效CRUD/Apply回傳最新完整DTO，不將draft視為成功。
閉合錯誤至少settings_schema_mismatch,entry_not_loaded,recipe_conflict,settings_conflict,recipe_not_found,invalid_recipe,recipe_limit,busy,confirmation_required，既有安全驗證錯碼保留；Unauthorized維持Core原生映射，不把文字送Sensor。
Card使用hass.callWS({type:'call_service',domain:'uninus_nutriculture',service,service_data:payload,return_response:true})；Core callWS結果為{context,response}，讀取result.response，不將外層包裝當DTO。依官方WebSocket API及已pin SDK實測，不加自訂WebSocket/auth旁路。
S1–S5 Sensor attrs/能力/ready/嚴格消費契約完全不改；不加recipe欄位進S5，不升schema、不改舊Card版本header以冒充發行。Card從已驗證S5 settings_target.config_entry_id取得槽id，不猜Entity名字、不另建sensor必填設定。

## 4. 原生與Card使用路徑
Options入口新增非破壞的「配方管理」獨立頁：選擇/新增/改名與10個NumberSelector；Save僅配方、Apply分開、Cancel零寫；Delete另獨立第二確認頁。不能刪除按普通boolean switch、不能要求貼JSON，不能OptionsFlow結束又以舊options覆寫交易。
Card新增緊湊配方區：明確載入/重新整理、選擇、名稱+10參數編輯、Save/Apply/Cancel、Delete二次確認；支持鍵盤與320px無溢出，同名以不顯眼辨識避免選錯。選擇與輸入不保存；草稿不因hass遙測重繪消失。庫功能僅當S5有效且四服務存在/callWS可用時提供，舊host/舊mock無能力時維持原控制可用、不呼叫不存在服務。
DTO必須strict驗證目標槽/version/revision/fields及數值；RPC拍下entry/revisions/id/generation，換槽/disconnect後late成功/失敗不得碰新槽DOM/draft/busy/錯誤。衝突/錯誤保留draft；Refresh/Cancel才明確重置。等待讀回與實際成功分開，不樂觀改Hass Entity。
get onopen或明確refresh，避免每次telemetry輪詢；同槽兩Card競爭由CAS拒絕，不能隱藏失敗後自動重送覆寫。所有文字textContent，無localStorage/token。

## 5. 精簡必驗矩陣與交付
先真行為RED→GREEN（可先註冊無business的transport shim後以實際保存後的options缺資料/未更新作RED，不拿缺module/import/fixture錯當RED）；第一條路徑先端到端，之後補CAS/拒絕/安全。每個child原始exit/commands/source bytes/RED/GREEN保留，早checkpoint，最多兩輪具體repair。
A native Options CRUD/重開/Cancel/刪除確認/同名穩定ID/兩槽隔離。
B registered native服務Save/Apply後唯一commit、10Numbers/status讀回、拒絕整包零變/CAS雙版本/無意義不升版；非admin/撤權afterlock/停用卸載/不存在服務型別。
C Apply忙碌/owner/pending拒絕且accepted plan/硬體IO不變；idle合法Apply保留非recipe域且零I/O/IRRfalse。普通Number和Options寫入保留catalog並令matches正確。
D shipped Card編輯/保存/套用/取消/二次刪除/衝突draft保留/遙測焦點/latepromise換槽；320px鍵盤；真Card發出payload送入registeredCore/Store正常關閉重開讀回，不以mock假整合。
E 既有native335/Node13/browser38與必要S5 realbridge無回歸（新cases分開報且實際collect）；production/tests/newtools lint/format、compile。每worker在owned build snapshot測，不消費peer半寫入來源。
整合後freeze候選，獨立SPEC再品質；既有P3安全批准不重開，不加第三whole-feature審查。原兩庫未安裝/commit/push前先宣告明確清單；發布另走實際raw-index等價與literalcompanionCI，不以本機pass代替。完整P4/Issue4不得因本slice就關單。
