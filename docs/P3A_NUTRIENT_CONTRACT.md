# P3 首個可操作加養切片：開發凍結契約

> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task.
> 2026-11-03：父端採納的 P3a 工程契約；不是已實作功能，也不等於設備已驗證。使用者繼續開發授權有效，實機部署/操作仍不授權。

**Goal:** 原生Options完成每槽加養/必要循環與安全設定，原生Switch及shipped Card可設定、啟停一次加養，後端完成有界脈衝、必要混合、新樣本再評估與可驗證安全停止。

**Architecture:** 延伸既有Tank／Controller／原生Entities，不先建立通用工作流框架。後端唯一設定與輸出權威；跨repo先凍結schema3及原子設定操作，再並行backend/Card，最後用隔離原生HA與真正shipped JS對接。

**Tech Stack:** 現有HA Python integration、原生Options/Number/Switch/Button/Sensor、根目錄JS、Node與Chromium測試。

## 0. 證據與交付界線

- 已以authenticated `gh issue view 3 --json title,body,state,url`讀兩庫Issue #3：均OPEN，完整四階段可編依賴/順序/並行/相對延遲/星期/預覽、原子參數及故障矩陣仍是P3驗收。未做GitHub write。
- 已讀backend `docs/{DEVELOPMENT_SPEC,CONTROL_PARAMETERS,CONTROL_DECISIONS,CONTROL_SWITCHES,P2_CONTROL_CONTRACT,FUNCTIONAL_PARITY_REVIEW}.md`及現行控制、設定、manager、原生Entity與Card consumers。P2 exact HEAD及測試通過數採父端已驗證上下文，不重跑P2。
- 現有實作：`Controller`只補水；`control_settings.py`只一個refill `binding`；Options只補水綁定/commissioned/feedback/四星期。`Tank.set_parameter`驗十參數後逐項更新，沒有group CAS；snapshot以`last_reported`驗新鮮。`ControlStatus`固定schema2、養酸混合unsupported；Switch的養酸混合available=false。Card `isControl`嚴格等於2、FLOW_STATES只有P2九詞，flow_run還以refill capability當gate；save只做單項`number.set_value`。
- 因此不可只擴schema2 capabilities/狀態，不可用refilling表示dosing；純domain helper或未接UI的Numbers不是本切片交付。
- **以下工程方案由父端採納作為本切片的開發契約；後附「跨庫精確補充」優先。它們不是已實作API/已通過驗收，也不誇稱所有數值均為使用者指定。來源/硬體待查證項繼續由commissioning封鎖。** 不連原HA、不讀HASS認證、不改repo/commit/push/tag/release/deploy。

## 1. 已定政策（不得重新發明）

- 無stage_link或額外多階段許可；start_flow與flow_run共用同一授權、安全與單槽受理gate。總ON/子ON/保存均不致動；flow_run ON才請求一次，OFF正常停止，不改Enable。
- 每階段真正開始前依HA時區查星期，包含等依賴/延遲/資源之後；開始後跨午夜不取消，手動不豁免；星期不合不等到下一天。
- EC >= (ec_low+ec_high)/2即停止加養；pH <=中點停止酸。停止繼續投藥與完成穩定/合格不同；本切片ready_for_irrigation始終false。
- 必要循環/混合不受獨立mix_enabled OFF取消；補水OFF不能豁免最低液位。最低安全液位由每槽commissioning明填，不採原跟隨1.2m作通用safe min。
- 危險預設可調：pH<3.8、EC>1.3mS/cm；pH>6.8持續600s僅高值告警，不無聲升級成全域急停；不採通知錯字1.5。
- 不新增scheduler、外部腳本/旁支管理、任意raw motor API。故障/取消/重啟不續藥，復歸不致動。

## 2. 首切片可操作範圍與後續硬承諾

本次先完成「只加養」的完整垂直路徑：營養設定commissioned、master及nutrient_enabled ON、refill/acid/獨立mix OFF → flow_run/start_flow → 必要循環 → pulse → OFF確認 → 必要mix/等待 → 新有效EC → 再評估 → 穩定完成。原P2只補水路徑繼續可用。

本切片尚未具備的多階段組合一律以`flow_configuration_unsupported`明確拒絕，不能悄悄串接固定refill→nutrient，也不能默默忽略使用者啟用的階段。acid/mix capability仍false，獨立mix不可啟用；nutrient內部必要mix不冒稱獨立mix已支援。

**這是開發順序，不是縮減Issue #3。下一個必交切片是酸/獨立混合，接著完整四階段有界可編依賴/順序/合法並行/相對延遲/條件/星期/七日預覽/成組UI及C05–C10矩陣。不得本切片完成就關兩庫Issue #3，也不得全推到P5。** R02完整圖語意另行凍結，當前不先造抽象框架。

## 3. 原生設定、參數與CAS（兩端共同凍結）

### 3.1 綁定／啟用前設定

延伸`control_settings.py`保留P2 `binding`不改語意，新增`nutrient_binding`、`circulation_binding`，沿現有registry identity四元組，不保存只有entity_id的權威身份。兩者不得相同、不得與本槽refill/已知其他槽輸出衝突；跨槽循環共享本切片仍拒絕。能辨識的直接/定時別名歸一資源；未知別名不宣稱已解決。

原生Options增加明選switch、`nutrient_commissioned`、安全參數群；所有欄位一次驗證/一次保存，取消零寫入零I/O。綁定/感測來源/commissioning/設備能力改動僅master OFF、無run/cleanup/待完成I/O、舊新輸出已知OFF時允許；不能為保存偷偷關外部輸出。舊P1只改來源的表單仍保持既有路徑，不強迫建立加藥設定。

commissioning必填：safe_min_level_m、pulse_seconds、max_total_on_seconds、max_pulses，以及可驗證設備最大ON保護的說明/已確認秒數、直接/定時實體對應。沒有物理驗證不得設定nutrient_commissioned=true；定時名稱不等於設備保護。此刻不用向使用者索取現場數字，未commissioned保持安全不可啟動。

### 3.2 參數精確key／單位／來源

P1十參數`parameters`及Number IDs不增刪：level_low/high、ph_low/high、ec_low/high、refill_timeout、ec_timeout、ph_timeout、mix_duration。其schema1 map仍恰十項。新增獨立`dosing_parameters`物件：

| key | 單位/用途 | 初始值性質 |
|---|---|---|
| safe_min_level_m | m；運行中level<=此值即停，開始須嚴格大於 | 必填每槽，無通用預設 |
| pulse_seconds | s；從送ON起算的單次最大窗口 | commissioning必填；原45s僅歷史基準非安全預設 |
| max_total_on_seconds | s；本run所有已送出ON的保守累計預算 | commissioning必填有限正數，非mL |
| max_pulses | 整數；本run最大脈衝數 | commissioning必填有限正數 |
| post_mix_seconds | s；每脈衝OFF確認後必要循環 | 300；原等待基準，套用為最低混合是工程選擇 |
| sample_wait_timeout_seconds | s；mix結束後等有效新樣本的上限 | 600；工程預設，非原站證據 |
| stable_samples | 整數；新有效樣本連續合格數 | 8；原酸穩定基準，套到加養屬工程預設 |
| stable_interval_seconds | s；成功樣本最小間隔 | 300；原酸基準，套到養屬工程預設 |
| flow_timeout_seconds | s；含等待/循環/加藥/穩定的整輪deadline | 5400；工程預設，與P1 ec_timeout初始90min對齊但不同欄位 |
| ph_danger_low / ec_danger_high | pH / mS/cm | 3.8 / 1.3，使用者已定且可調 |
| ph_high_alarm / ph_high_alarm_seconds | pH / s；告警而非全停 | 6.8 / 600，使用者已定且可調 |

`feedback_timeout`沿P2秒數，分清ON/OFF確認與脈衝時長；`ec_timeout*60`為加養階段deadline，不繼承refill_timeout；本run總deadline與階段deadline取先到者，安全收尾仍有獨立有界OFF確認，不因到期跳過。

後端有限值/非bool/單位/step/上限驗證；建議秒數正整數<=86400、max_pulses 1..1000、stable_samples 1..100；pulse<=已確認設備最大ON，pulse<=total_on，pulse+feedback<=階段/整輪deadline；必要mix/採樣/穩定可在deadline內完成至少一次。液位仍在0..10m資料範圍但需每槽幾何確認；危險門檻需與目標方向一致，不能0/極端值等同關閉保護。沒有commissioning範圍證據不得把這些UI範圍說成物理安全認證。

### 3.3 唯一交易與Card保存操作

新增提案服務`uninus_nutriculture.apply_control_settings`：

```
{config_entry_id: <明確loaded本domain entry>, expected_revision: <非負int>,
 parameters: <完整十項>, dosing_parameters: <上述完整物件>,
 allowed_weekdays: {refill:[...],nutrient:[...],acid:[...],mix:[...]}}
```

不接受bindings、commissioned、Enable或raw outputs；這些僅原生Options／既有Switch處理。採與start_flow相同admin/internal-context政策、明確拒missing/null/wrong/unloaded目標。SupportsResponse.OPTIONAL：回應要求時傳`{applied:true,settings_revision:N}`，失敗拋原生例外，不傳成功形狀error。Card使用callService並以Sensor revision/值讀回確認，不因Promise resolve宣稱持久安全。

`settings_revision`每entry持久整數；設定相關寫入均在既有Tank.lock下重讀最新options、CAS、整組validate、一次async_update_entry、一次publish。成功修改才+1；相同內容保存不增。原生Options把開表單的revision留flow私有狀態，不要求使用者填；其只提交被編輯欄位，不能把舊suggested values蓋掉中間Number/Enable寫入。原有逐項Number仍可用，走同一writer/全組驗證且+revision；因此Card草稿會收到衝突而非覆寫。Enable/fault寫入只合併最新control，不重寫設定群；不以run變化無謂增加設定revision。

CAS衝突`settings_conflict`：零部分寫入、Card保留草稿/顯示最新值與重新載入，不自動重試覆蓋。Card Cancel只丟草稿/讀回，不呼叫服務。儲存是HA ConfigEntry排程持久化，不能宣稱fsync crash-durable。

## 4. schema3 wire／原生map凍結

保留schema1 `<entry>:status`與十Number原貌。P2-only entry繼續schema2；**明確完成加養設定並commissioned後**，同一`<entry>:control_status`升schema3，不能在任何dosing期間發布schema2假象。既有schema2 Card對3 fail closed；舊monitor仍可綁schema1。新版Card同時支援1/2/3，不讓schema2宣告養capability被誤採。

schema3繼承v2可相容的source_entities、parameter_entities、parameters、reasons、allowed_weekdays、fault(string|null)、run_id(string|null)，增加：

```
schema_version: 3; mode: 'control'; ready_for_irrigation: false
capabilities: {refill:true,nutrient:true,acid:false,mix:false}
settings_target: {config_entry_id:<entry>,service:'apply_control_settings'}
settings_revision: <非負int>; dosing_parameters: <完整設定>
control_entities: {automation_enabled,refill_enabled,nutrient_enabled,flow_run,
                  emergency_stop,reset_fault} // 值皆實際registry ID
flow_state: <下列枚舉>; stage_states: {refill:...,nutrient:...,acid:'unsupported',mix:'unsupported'}
nutrient_phase: null|'starting_circulation'|'pulsing'|'confirming_off'|'mixing'|'waiting_sample'|'stabilizing'
dose_progress: {pulse_count:<int>,reserved_on_seconds:<number>,stable_count:<int>}
output_states: {nutrient:'on'|'off'|'unknown',circulation:'on'|'off'|'unknown'}
```

flow_state枚舉：P2原九詞 + `waiting_resource`,`dosing`,`mixing`,`waiting_sample`,`stabilizing`。nutrient stage_states用`idle`,`starting`,`waiting_resource`,`running`,`stopping`,`completed`,`aborted`,`fault`,`skipped_disabled`,`skipped_weekday`,`blocked_dependency`；phase表達pulse細節，不拿refill詞彙充數。對schema3不支援/畸形/未知詞/state≠flow_state，Card禁止寫入並顯示不相容。

原生Switch unique keys沿P2，nutrient_enabled新增available；acid/mix仍unavailable且不映射。flow_run gate是「有已支援且合法的計畫」，不再硬寫capabilities.refill。map只提供本entry、registry身份有效且已載入的實際ID；每次click依最新schema/能力/map/domain/狀態重驗，不由title拼ID。settings_target只供group設定，控制啟停仍走映射switch/button，Card不直接碰泵。

flow_run在starting/合法等待/執行為ON；未確認停止保持stopping，停止失敗用unknown/unavailable+fault；只有本輪工作及pending ON/OFF確定收束才OFF。正常completed不等於灌溉許可。

## 5. 執行與安全狀態機（工程凍結）

1. 受理共用P2授權、entry life、世代、單槽lock與request_id策略；每await後與每次物理ON前重驗。nutrient必要ph/ec/level皆有效、單位/未來/時效正確；低pH/高EC危險拒絕。不因一般目標區間外就當資料invalid。
2. 先確認nutrient與circulation均已知OFF，再取得本槽循環lease；等資源有deadline。每階段實際開始前含資源等待後查星期。開循環並確認ON才可開加養；必要循環運行中失去/未知立刻撤銷後續脈衝並停加養。
3. 若EC>=中點，零加藥；如無前序pulse可進必要循環/穩定檢查，但不得直接completed。否則先預留一整pulse的累積ON及次數預算，再送ON；無預算則故障/受限中止，不偽完成。累計含送出到OFF確認的保守ON時間；確認超時不能用「只有設定pulse秒」低估。
4. 從送ON起單調計時；到pulse截止送OFF，不從ON確認回來才開始計時。任何EC>=中點事件也立即OFF（不等脈衝自然完），危險/低液位/invalid/timeout/取消同樣優先OFF。已送I/O不能回滾；晚到ON必追安全OFF，未收束禁止重啟。
5. OFF回饋確認後才開始post_mix最低必要循環；mix期間不追加。mix完成才建立EC新樣本屏障；有效新樣本後重新檢查安全及中點，未達才可下一pulse。
6. 達標樣本必須同時EC在目標區間內，穩定計數只計不同、足夠間隔且本run有效新樣本；invalid立即故障/不累積，超區間重置，不以感測滯後宣稱穩定。滿stable_samples才completed。全程pH/液位/危險與deadline仍檢查。
7. 所有停止先撤銷世代/後續ON，再確認加養OFF，最後釋放循環lease；循環仍有其他合法owner時不能OFF。此首切片無跨槽共享，單槽lease已要能表達nutrient必要混合owner；後續獨立mix以同一資源計數，不另造可互相關泵的timer。
8. master/nutrient OFF立即中止本輪、不改其他子設定；mix_enabled OFF不能關nutrient lease。正常取消亦中止而非completed；取消/卸載不能丟安全收尾。急停鎖定；reset需所有本槽輸出已知OFF、必要來源有效，解除不重跑。
9. 重啟不恢復運行；檢查全部已commissioned輸出，ON/unknown→restart fault及核對，不擅自接管外部輸出、不讀回舊ON來續藥。停泵失敗fault持久可見。循環OFF失敗也不得聲稱全部安全。

### 有效新樣本不等於HA state_changed

現有last_reported只證HA回報新鮮，不能證物理採樣。加養commissioning須明選來源模式：具可驗證sample sequence/timestamp（僅允許指定attribute、型別、有限值、單調、無未來），或明確認可「每次report即新採樣」的設備契約。未確認則不commission。

收集來源report事件（不能只靠state_changed，同值也可能是新採樣）；EC樣本token必須大於mix完成屏障及上次已消費token。讀取同一State/attribute變更/重繪/回報舊token不消費、不續加、不累穩定；相同EC值但可證明新採樣可計。source identity/單位/err映射異常即停。等不到新值到sample_wait_timeout就fault，不拿最後已知值追加。

此模式與允許sample attribute列表是尚待設備來源查證項；不能在本次只讀下聲稱實機已證明。Native fixture須有真報告事件與sample token兩種模式測試。

### 熱修改

綁定/來源/設備能力只允許停機；已受理run持有設定revision快照。收緊立即生效：safe_min上升、pulse/累積/次數/deadline下降、ec目標中點下降、危險EC下降/pH低標上升、mix/等待/穩定要求提高。pulse已超新界限立即OFF，累積已超新上限立即中止；放寬不得擴大本run預算，下一輪生效。目標變更若跨參數不合法整組拒絕。星期/一般流程改動下一輪；總子OFF及安全收緊不等下一輪。草稿永不影響run。

## 6. 檔案所有權與TDD開發次序

所有backend路徑相對`D:/UNiNUS Projects/AI project/uninus-nutriculture`；Card相對sibling `uninus-nutriculture-card`。workers不得改對方repo、不commit/push。父端先採納本契約並在正式共同規範落一版，再同時派工；避免各自發明wire。

### A：Backend worker（既有檔延伸，不先新框架）

- `custom_components/uninus_nutriculture/{control_settings,config_flow,manager,control,services,sensor,switch,number}.py`；`services.yaml`、`strings.json`、`translations/{en,zh-Hant}.json`。必要新增小型dosing helper可接受，但必須同輪接原生Controller，不能單獨當交付。
- 新增`tests/test_p3_{options,settings,wire,dosing,samples,safety,races,restart}.py`；沿`tests/p2_fixtures.py`模式建立隔離加養/循環設備，不弱化P1/P2斷言。
- Task A1：先寫原生Options Save/Cancel/reopen與非法整組零寫入測試；確認行為RED→接共同writer/CAS→GREEN。
- A2：先寫實際Sensor schema3、registry rename/disable及原生nutrient Switch→Controller啟停測試；行為RED→接wire/入口→GREEN。
- A3：先寫pulse ON→OFF確認→mix→舊值不追加→新值續評、中點事件中途停泵測試；RED→有界狀態機→GREEN。
- A4：先寫停用/取消/late ON/OFF/timeout/低液位/危險/累積/重啟/hot-tighten矩陣；逐個業務斷言RED→最小修正→GREEN。輸出回饋與設備物理保護分開證據。
- 命令：沿repo現有隔離測試環境執行`python -m pytest tests/test_p3_options.py tests/test_p3_settings.py tests/test_p3_wire.py -q`，接著其餘p3測試；若當前shell Python不是已安裝HA的環境先讀README/TESTING，不任意全域install。預期通過是待驗證，不報虛構數量。

### B：Card worker（可與A並行）

- `uninus-nutriculture-card.js`、`tests/test_contract.cjs`、`tests/test_browser.py`、`demo/index.html`；本次handoff文件。不要改backend或父端權威規範。
- B1：先寫schema3 payload/未知v3詞彙/惡意schema2宣告nutrient拒絕之Node行為RED；實作1/2/3獨立解析、完整狀態與capability gate→GREEN。
- B2：先Chromium點擊養子開關/flow_run/停止、非樂觀狀態/錯map/切槽in-flight測試RED；接原生map→GREEN。
- B3：先群組草稿編輯EC上下限＋安全參數、顯示唯讀中點、取消零call、一次Apply payload/CAS衝突保留/讀回確認測試RED；接apply_control_settings→GREEN。新版schema3群組UI取代本模式逐項Save，v1/v2十Number單項路徑保留。
- 延續epoch/flight/換槽/斷線/卸載與舊Promise防護；服務呼叫前重驗settings_target和revision，不能從cached草稿決定另一槽target。320/768/1200寬度及light/dark操作可見，非只demo截圖。
- 命令沿`package.json`/`docs/TESTING.md`既有Node/Chromium入口，不虛構新script；本次調查未執行測試。

### C：Parent整合gate（不能被兩邊mock替代）

- 建議隔離驗收檔backend `tests/test_p3_bridge.py`配Card browser probe；parent擁有共同契約文件與bridge，worker不互改。
- 從原生Options flow真Save綁定及commissioning → 擷取實際HA Sensor attributes/entities → 瀏覽器載入repo根目錄shipped JS → 真click群組Apply/原生養Enable/flow_run，bridge把原始callService payload/context送實際隔離HA service registry/native handler，回傳實際states，再驅動同張Card更新。
- 驗證EC原子修改持久讀回、Cancel無寫入/I/O、nutrient output ON/OFF→mix循環持續→舊樣本不追加→有效新樣本中點停止→穩定完成→Card/原生flow_run OFF；另測busy/OFF快切/來源失效/CAS衝突/錯槽/停止未確認及schema2舊Card對schema3零寫入。
- 使用真HA state/report events與fixture設備，僅設備層fake；不是手造回應假稱backend bridge。核對所有map均來自當前registry、沒有任何真HA連線。
- Slice驗收後SPEC審查→獨立品質/安全審查→限定修正→exact candidate測試；後續publication須另依父端授權。P2既有全套不在本調查重跑；整合時保留正常回歸門檻不削弱。

## 7. 分類與剩餘查證

**已確定：** 本文§1、兩庫Issue #3完整範圍、現行schema1/2嚴格consumer/P2只補水/缺CAS，均有只讀來源支持。

**本切片採納的工程契約（非既有功能）：** schema3升級策略、apply_control_settings精確payload、revision writer、必要混合lease、只加養首切片與拒絕尚未支援組合、參數key與工程預設、deadline/熱修改/穩定的保守語意。不得寫成已實作或使用者已核准所有數值。

**來源/硬體尚待查證：** 每槽safe min/幾何、泵直接/定時別名及獨立最大ON保護、允許pulse/累積上限、EC真採樣token/同值report語意、裝置err可用性。以commissioning明填與驗證封鎖危險啟用；不要求現在再向使用者索取一串固定值、不連原HA補資料。完整R02四階段圖/重複節點界限仍在後續P3契約凍結，不由本切片默認解決。

來源調查為只讀，沒有設備操作；實作狀態另見當次handoff，不用本契約冒稱已完成。


## 8. 跨庫精確補充（本節優先，P3A-v1）

### 8.1 持久位置與既有行為

- 保留 `entry.options.parameters` 原十key；新增頂層 `dosing_parameters`、`settings_revision`（缺省0）。不把Enable/run/fault塞進revision。
- `entry.options.control` 延伸 `nutrient_binding`、`circulation_binding`、`nutrient_commissioned`、`device_max_on_seconds`、`nutrient_protection_confirmed`、`alias_notes`（最長512字）、`sample_mode`、`sample_attribute`、`report_contract_confirmed`。既有binding/commissioned/feedback_timeout/allowed_weekdays/Enable保持原語意。
- `sample_mode` 精確為 `reported`、`sequence`、`timestamp`。reported需明確操作人員確認每次HA report代表新量測；sequence需單一選定attribute為非bool單調非負整數；timestamp需選定attribute為具時區ISO8601，非未來且符合來源新鮮度。sequence/timestamp的attribute名稱必須明選、1..64字元、僅ASCII英數底線；不接受模板、路徑或任意巢狀資料。這是選定attribute白名單，不宣稱現場裝置具備它。timestamp不猜epoch單位。
- commissioning記錄是操作人員對設備保護/採樣語意的明確聲明，**軟體不會驗證這項物理事實**；沒有確認及必填數字便不可啟動。假硬體測試可明確模擬已確認設備，不可稱實機驗收。
- 原生Number保留既有HA Entity ACL，不偷偷改成一律admin；群組服務與綁定/commissioning依原生admin/internal管理政策。所有寫入共用最新值/整組驗證與revision。Number只改既有正常參數，不能修改新安全群的權限。
- 新危險/劑量跨參數驗證於加養commissioned的entry強制；未配置加養的P1/P2 entry保持已允許的監測/補水數值語意。整組資料錯誤零部分更新。危險EC須大於ec_high、危險低pH須小於ph_low；高pH告警與正常目標分離。
- settings revision只對成功且有設定內容差異的交易+1。群組保存要求完整parameters/dosing_parameters/四stage星期；Options只提交本表單明確欄位，過期表單CAS拒絕，不覆蓋別人的Number更新。
- 管理服務初始授權在目標讀取之前；排隊等Tank.lock後重驗授權/active/registry/CAS，任何await後在首次設定效果前再檢查，不能以排隊前的admin快照授權。拒絕不讀受保護投影、不改設定、不啟動設備。
- 設定writer可選擇保持既有來源變更reload路徑；不可讓pure group/Number保存reload正在運行的controller。綁定/來源/保護能力改動嚴格停機，Numeric安全收緊走同一運行controller的既有通知路徑。

### 8.2 型別與範圍（工程限制，不是設備認證）

所有boolean嚴格bool、整數不可接受bool；數值有限且不猜單位。拒絕額外key。

- `safe_min_level_m`：0..10，0.01 step，commissioning必填；level必須嚴格大於它才允許加養。
- `pulse_seconds`、`max_total_on_seconds`、`post_mix_seconds`、`sample_wait_timeout_seconds`、`stable_interval_seconds`、`flow_timeout_seconds`：正整數1..86400；前三個critical中的pulse/total及max_pulses無通用可啟動預設。post_mix=300、sample_wait_timeout=600、stable_interval=300、flow_timeout=5400為可調工程初值。
- `max_pulses`：1..1000；`stable_samples`：1..100，初值8。
- `ph_danger_low`、`ph_high_alarm`：0..14，0.1 step，初值3.8/6.8；`ec_danger_high`：0..100，0.01 step，初值1.3；`ph_high_alarm_seconds`：1..86400整數，初值600。
- `device_max_on_seconds`：1..86400，須操作人員確認獨立設備保護；pulse<=device_max_on_seconds、pulse<=max_total_on_seconds。開啟/關閉回饋期限仍使用P2 feedback_timeout。
- 累積額度為保守時間預算，不是mL。物理OFF延遲可能造成觀測預算超出，必須故障/禁止追加，不能假稱回滾或絕對物理硬上限。發送OFF的截止時間取pulse/剩餘額度/階段/整輪的最先者；不能等ON ACK返回才起算。
- 一輪deadline須容納必要混合/至少所需穩定樣本間隔；沒有足夠時間便在保存拒絕或清楚受理拒絕，不讓配置必然無法完成。一般目標ec_timeout原單位分鐘，換成秒只在運行邊界，不能改原Number語意。

### 8.3 Wire完整性與UI精確邊界

- schema3保留P2所有既有attribute，新增第4節欄位；Entity `state` 必須等於 `flow_state`。`output_states`為nutrient/circulation三態，不是實體硬保護證明。
- `settings_target`正好 `{config_entry_id: nonempty string, service: 'apply_control_settings'}`，domain永遠本整合常數；不得由資料指定任意HA domain/service。
- `parameters`正好原10keys；`dosing_parameters`正好表內13keys。`allowed_weekdays`正好refill/nutrient/acid/mix，每組為mon..sun的無重複列表，空集合=不允許任何日。
- control_entities是已註冊/載入/active/有效registry的實際ID子集；可缺失、不能猜。schema3的nutrient_enabled僅能力已接通時映射。flow_run要求至少一個已支援且已選階段，不再硬依賴refill；同時開啟refill+nutrient的本切片計畫需顯示「組合尚未支援」並拒絕，不悄悄改為固定順序。
- v3 group編輯模式使用單一Apply/Cancel（含原10key與新增安全參數/四星期），v1/v2保留原十個單項保存。顯示唯讀EC中點；不提供bindings/commissioning UI替代原生Options。群組服務僅callService，Promise成功後等待最新revision及值讀回一致才顯示已套用；不聲稱fsync。
- Settings服務會拒絕missing/null/wrong/unloaded entry、stale revision與額外key。回應如有要求為 `{applied:true, settings_revision:N}`；錯誤用原生exception。啟停永遠使用native map，禁止底層泵呼叫。
- schema2/未知schema不能藉偽造nutrient capability開啟養；嚴格版本/狀態/身份/map驗證，並保持epoch/換槽/舊Promise隔離。schema3可用合法P2九態與新增5態，沒有refilling冒名dosing。
- 狀態`settings_revision`來自後端權威。Card自己不得+revision；CAS衝突保留整組草稿、不自動重試、不把新槽的目標放進舊請求。

### 8.4 分工與中間狀態

1. Backend A1先交付「原生Options/共同CAS writer/管理服務/schema3投影」的可呼叫設定路徑，保留P1/P2；暫無加養engine時，Controller `supports_nutrient`預設缺失即false、native養Switch unavailable/capability false，不得假啟用或交付P3完成。
2. Card B可與A1並行，依凍結schema3做fixture RED/GREEN與真Chromium編輯/操作；fixtures只能證明前端，不能稱真backend bridge。
3. A1完成後Backend A2在相同契約接加養/必要循環狀態機，才設supports_nutrient=true並完成真端到端。A1/A2 sequential，不同時修改backend檔案。
4. Parent最後接真native/shippedJS橋接、獨立SPEC→品質與最多兩輪具體修補；A1/B單獨的綠測試不是可交付P3a。版本及README/roadmap由parent整合後更新，worker不自行commit/push。
5. 不發行tag/release、不連原HA、不授權設備操作。Issue#3整體仍OPEN直到完整四階段/可編流程驗收；本切片只是一段開發順序。
