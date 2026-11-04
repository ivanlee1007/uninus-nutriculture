# P3c 四階段可編流程契約 — P3C-v1
> **For Hermes:** 依 subagent-driven-development 執行；本版為父端工程凍結，尚未實作/審查/發布。§7補充優先於來源提案。
**Goal：** 四列編輯／預覽／真執行同切交付。
**Architecture：** 小coordinator＋四唯一step＋既有Controller，非generic DAG。
**Tech Stack：** HA Python、原生服務/Switch、shipped JS Card。

## 邊界
依原產品docs/{DEVELOPMENT_SPEC,CONTROL_SWITCHES,FLOW_DESIGN_RESEARCH}.md，以及scratch nutriculture-p3b-review-r1-successor內P3B_ACID_MIX_CONTRACT、control/nutrient/mix、Card strict v4實際source。未改R1；P3a已source/CI交付，P3b未合併。本提案未實作P3c，不成為P3b延期／重開前期理由。以下新增政策均為**工程預設草案**。
保留順序、合法重疊、延遲、條件、各stage星期及預覽；native/服務/Card共backend，外部trigger用start_flow，flow_run同入口。子Enable只控制納入，不單獨啟動或私自接續；整輪的後續stage依已受理計畫執行。無scheduler/stage_link/eval/任意service/迴圈/重複stage/配方/IRR ready；進階圖編輯P5。

## 1 計畫／錨點
flow_plan exact `{rows,run_timeout_seconds}`；四列stage=refill/nutrient/acid/mix各一次，列序亦仲裁優先序。row exact `{stage,start_rule,delay_seconds,condition,wait_timeout_seconds}`。
start_rule=flow_start/after_previous_started/after_previous_finished；首列只能flow_start，previous固定緊鄰前列。up/down保留設定重驗、不暗改規則。delay為0..86400整秒；wait/run_timeout為1..86400整秒，wait預設300。新global run_timeout預設依四stage現有合法執行上限、delay及wait保守加總並上限86400，不照抄單一dose的5400而讓正常多stage預設必然超時；所有原10 Number與各stage既有預設不變。Preview揭露global期限可能先於各stage最壞上限，不保證全輪必成功。condition=null或exact `{source,operator,value}`；source=綁定level/ph/ec，operator=gte/lte，value有限且在既有量程。AND gate讀目前新鮮值，非只等edge、不取代安全。
flow_start錨定受理；started錨定真admission首次輸出/lease dispatch，非排隊/feedback。finished為正常owner結清，亦作純排序：前列skipped_disabled/skipped_weekday以dependency-settled釋放並計delay，**不偽造started/completed**。未started的skip無started錨點，started-dependent子列立即blocked_dependency；blocked不當finished釋放，fault/aborted不接續。排序通過非品質完成。
run deadline自受理固定；admission等待期限=min(run deadline,anchor+delay+wait_timeout)，只限制條件/資源/液位等待。真正admit後改受global期限、該stage原有執行期限與共享circ物理保護期限約束，不把300秒wait誤當600秒mix的運行上限；等待逾時fault全停。前列已終結且無錨點立即blocked。所有等待後、真正admission同鎖重查權限/identity/啟用/來源/安全/預算及HA時區當日星期，才dispatch。不符skipped_weekday，不等明日；已開始跨日不突停。星期綁run snapshot。

## 2 重疊／owner
N/acid**整個化學cycle**互斥（含混合/採樣/穩定/收尾）；refill與chemical亦互斥。可要求並行，實際waiting_resource，不偷改計畫。一次取齊互斥資源才持lease，禁部分持有等待。
standalone mix可與安全refill或N/acid共享circ。低液位mix僅同輪已有active或可獨立啟動refill才waiting_condition至列deadline；實際admission時若無可達refill則拒level_unsafe、不自補水。不可僅因保存當下液位低就拒絕一份未來液位健康時合法的計畫；靜態Save只拒結構非法，Preview將動態安全不可達列明，runtime再按真讀值判斷。stage必需來源及顯式condition選中的來源失效才fault，level-only且condition=null的mix不因缺pH/EC誤停。level-only不能侵蝕dosing完整gate；dose fault撤全部active/pending並停circ，不續混。安全一律明確owner，不借active role。
circ連續ON以最早未結清ON dispatch起算cutoff=min(owner deadlines,session_start+C-F)，保留OFF feedback F。新lease/重送ON/未確認OFF不重置；已有確認ON只加lease不重送。identity/健康/剩餘收尾額度不足拒新工作。最後lease釋放且pending ON收束才物理OFF，late ON追OFF。own result依自身劑泵OFF/pending結清、必要mix完成、lease釋放；其他owner合法ON不阻own completed、不因global running誤報fault。最後owner仍須OFF確認，失敗fault/unknown。

## 3 接縫／停止
現control.execution_stage依單run_stage分派；nutrient.cleanup約510行用control.running推own fault；mix.start要求circ OFF且直接改global flow_state，故不可直接平行spawn。
新增flow.py持run_id/generation、immutable snapshot、四step records、dependency wake、資源表；Controller唯一I/O權威。refill的target/started/on_task/off_task/result隔離至step。callback/dispatch/cleanup必傳owner；phase_changed只改own phase/result，coordinator聚合。
global running=coordinator未終結 ∪ 全部pending/waiting ∪ cleanup/lease/pending I/O；合法等待flow_run保持ON，停止未確認stopping/fault。總OFF、flow_run OFF或運行中子OFF先撤generation/取消全部pending，再收尾全部active，aborted、不啟下一列。fault全輪撤銷鎖定；reset/再ON/HA重啟不續跑。正常完成須做必要mix再release；手動正常stop沿既有劑泵OFF確認後釋lease的順序，不額外新加一輪postmix timer拖延停止；急性fault不等postmix。
plan/weekday/Options草稿下輪生效，active snapshot不可變。受理時固定enabled_stages；原本未納入的stage不可因中途ON被偷偷加入。已納入而尚未started的stage若中途OFF，在其dependency/anchor/delay到達後才skipped_disabled結清，不提早穿透排序鏈；active子OFF仍正常停止全輪。bounds同輪只熱收緊並重驗全部owner；放寬下輪。binding/source/commission仍限master OFF且無任何cleanup/pending。

## 4 schema5／CAS
舊v1/2/3/4 exact不放寬；v5不降版投影，舊Card零控制call、舊writer拒settings_schema_mismatch。成功保存v5才持久升版；未知key拒絕。
snapshot exact=P3b/shipped V4_KEYS的**25 keys**僅加 `flow_plan,flow_plan_revision,flow_plan_target,run_plan,step_runtime`。schema_version=5，settings_target.service=apply_control_settings_v5。其餘v4型別保留；flow_state新增running/waiting_condition/waiting_delay，stage_states新增waiting_condition/waiting_delay。聚合fault→stopping→active running→等待→終態；completed可含skip/blocked，非四項成功/IRR ready。
flow_plan_target exact `{config_entry_id,service,preview_service}`，服務=apply_flow_plan_v5/preview_flow_plan_v5。flow_plan_revision是entry-local非負安全整數；settings_revision是**全設定交易序號**，plan變更亦增加。run_plan=null或exact `{run_id,settings_revision,flow_plan_revision,flow_plan,allowed_weekdays,enabled_stages}`，enabled_stages為四stage exact bool map；受理深複製、下次accepted run才替換；bounds/source副本後端持有。
step_runtime exact四stage map，各值exact `{phase,result,started_at,settled_at,waiting_reason}`。phase沿v4，另refill starting/refilling、waiting_delay/waiting_condition/waiting_resource，非活動null；result=null或completed/aborted/fault/skipped_disabled/skipped_weekday/blocked_dependency。時間UTC ISO string|null，reason非空string|null；未started的skip之started_at必null；settled_at記錄略過結清時刻。舊phase/progress各鏡像own owner，output_states為物理真值。
v5 settings mutation exact `{config_entry_id,expected_revision,parameters,dosing_parameters,acid_parameters,mix_parameters,safety_parameters}`，不夾plan或weekday；舊v4的八鍵payload與服務保持原契約，v4 writer對v5 entry拒絕。plan mutation exact `{config_entry_id,expected_revision,expected_flow_plan_revision,flow_plan,allowed_weekdays}`；response exact `{applied,settings_revision,flow_plan_revision,flow_plan,allowed_weekdays}`。v5四列星期唯一在plan editor/native plan Options namespace編輯並與順序同筆保存，不讓UI改了星期卻不在payload。plan/weekday任一實質變更均增加flow_plan_revision與settings_revision；純數值settings只增加settings_revision。兩writer/Options/Number共Tank.lock：鎖內讀最新entry、重驗ACL/loaded/CAS、merge自身namespace、一次update/publish，禁舊options整包覆寫。plan比兩revision，settings比全域revision，避免lost update；無差異不加版、衝突零寫。原生Options若同次編輯兩namespace亦只一次原子update；Number鎖內用最新revision/同validator。Card成功須同entry/revision/全值讀回；失敗保留草稿，Cancel零寫；測mutation後run_plan不變。

## 5 UI／預覽
四列up/down＋start規則下拉＋offset＋有限條件＋七日複選＋parallel/實際等待說明；Apply/Cancel/Preview分開，非純JSON交付。啟用沿原生子開關，不藏入plan草稿；停止沿backend確定讀回，急停不得增加阻擋關閉的確認modal或瀏覽器安全timer。
preview payload exact `{config_entry_id,expected_revision,expected_flow_plan_revision,flow_plan,allowed_weekdays,weekday}`，weekday=mon..sun，allowed_weekdays取未保存的四列草稿。共真validator/依賴/資源規則，零run/I/O。response exact `{settings_revision,flow_plan_revision,weekday,rows,warnings}`；row exact `{stage,eligibility,earliest_offset_seconds,uncertainties}`，eligibility=eligible/skipped_disabled/skipped_weekday/blocked_dependency，offset非負有限秒|null，warnings/uncertainties字串列表。逐日七日預覽，區分靜態最早下界/未知感測時長/資源等待；未知finished錨點offset=null，不報虛假確定完成時間。星期僅假設admission日，跨午夜runtime為準。

## 6 真RED→GREEN／owned files
首個behavioral RED：真HA Options/服務保存refill(flow_start)、mix(after_previous_started,+1s)、N(after_previous_finished)、acid(after_previous_finished)；低液位mix等待，fake安全液位後與refill重疊。斷言兩owner、mix結清不毀refill、後續真dispatch。現單eligible拒絕/無第二步dispatch才算RED，不算import/fixture失敗；只fake設備/時鐘、不手塞options/runtime。
GREEN同切：原生保存/讀回→shipped editable table/preview/Apply→真start_flow/flow_run→多stage→sensor→shipped consumer own終態，Card離線仍跑。首例refill+mix只有mix持circ lease，不足以證明多circ-owner；必另真跑mix與N或acid重疊，先釋放一owner不關他人的circ，最後owner才要求物理OFF。回歸換序、未存星期草稿Preview/Apply原子讀回、七日/跨午夜資源後admission、skip兩錨點、deadline、全cycle互斥、共享circ先完成/cutoff不重置、dose fault全停、manual OFF不接續、late ON/OFF失敗、雙writer CAS、snapshot不變/bounds只收緊、舊caller零call及v1–v4，helper GREEN不算交付。
解凍後backend單owner獨占custom_components/uninus_nutriculture/{flow,control,nutrient,mix,manager,control_settings,config_flow,services,sensor,switch,p3b_projection}.py、services.yaml、strings/translations、新tests/test_p3c_flow.py及native fixture/bridge；flow.py新增、其餘按需。Card owner僅sibling uninus-nutriculture-card.js、tests/test_contract.cjs、tests/test_browser.py、demo。先凍結wire再同一垂直切片；沿既有TESTING/CI命令跑native全套＋shipped bridge/browser，獨立SPEC→品質安全；發布/部署另gate，不自批准。


## 7 父端凍結補充（P3C-v1，本節優先）

- Baseline改為已joint SPEC PASS＋品質APPROVED的P3b exact175 Q-successor，manifest a22f4988f6b26754a73a8185cd1e76bc1e6dacecb95f5e4a9f9fc458e1ded3c2。P3b原庫尚未合併，出版隔離工作平行；不重開或延後P3b。此P3c是同一完整四stage交付slice，初始實作＋最多兩輪具體修補，改名/timeout不重算，不允許自發布。
- 本版已由父端採納為可實作工程契約，前文「只讀提案／草案」屬來源歷史，不代表還需使用者逐項批准。保留所有原用戶功能，沒有scheduler/stage_link，P3c完成之前不可關Issue3。
- schema5 exact root keys由同目錄P3C_WIRE.json列出；25個V4基礎＋5個新增。例外擴展：v5 output_states改為exact nutrient/acid/circulation/refill四個物理真值(on/off/unknown)，不冒稱enabled=物理ON；舊v4三keys不變。服務target兩entry ID必一致，HA_METADATA沿既有四項，不接受其他extra。
- 首次建立v5須由原生Integration Options「流程計畫」的真正表單（非JSON textarea）或registered apply_flow_plan_v5完成；v1 shadow不可升。v2/v3/v4 control首次明確Save只在master OFF且無任何owner/pending/cleanup時升5。這個schema transition算實質變更，即使採預設plan也同交易增加兩revision；不虛造N/acid/mix commissioning。開表/Cancel零寫、不升版。已v5的plan/weekday可在active時原子寫下輪，不能換Controller、清掉當輪run_plan或改動active規則；已v5 no-op不加版。
- 新Card流程編輯器僅在已驗v5 target啟用。v4無新metadata，不猜API/entry或降級v5；可提示先在原生整合設定建立計畫。settings v5移除weekday欄位；weekday只在plan表格/native plan頁同筆Save，舊v4含weekday payload完全保留。
- 首次預設plan四row順序refill/nutrient/acid/mix，首flow_start，其餘after_previous_finished，delay0/wait300，run timeout由原上界推導；服務可自訂。條件value量程level0..10、ph0..14、ec0..20；不可bool/NaN/inf/任意entity/service。先admission後無輸出即完成的no-op可result completed但started_at=null，started-dependent後列blocked_dependency，finished-dependent照settled釋放。全部子Enable皆False的start拒絕、零run_id/IO，不造成功整輪。
- step_runtime.phase exact允許null及P3C_WIRE.phase；活動中的waiting reason只用wire閉集，非等待時null；不得把provider diagnostics/str(exception)落options、fault、reason或sensor。新故障碼須明確closed allowlist，初始化同sanitize，None才清fault。stage_states若有run record，terminal用其result、等待用waiting_*、starting用starting、清理用stopping、其餘活動用running；沒有record沿原unsupported/idle語意，不因master變False覆掉真結果。
- Preview eligibility加blocked_safety（完整enum見wire），可達已啟動refill正在改善低液位則eligible＋uncertainty，無可達refill或缺必要健康來源則blocked_safety，不以blocked_dependency混充；只靜態Save不能依當下低液位拒合法未來計畫。預覽warnings/uncertainties用bounded owned代碼/固定模板，不傳原exception；實際runtime再次決策，不能保證未來感測時刻。
- 所有v4-only safety/globalS判斷明確支援known5，包含高pHobserver及schema投影；v5不可默回N-only策略重開酸-only漏告警。設備binding/source/commission修改仍masterOFF且無pending；Bounds同run只收緊，所有owner用同樣hot-safety預算，plan/weekday/放寬只下輪。
- 先真native保存/preview/start的行為RED。若v5服務尚未存在，registered API的ServiceNotFound是待接通產品boundary RED（不是import/fixture錯），並保留舊v4拒multi-stage陽性控制，不能改舊v4契約求綠。GREEN必有完整四row plan＋至少refill/mix真重疊＋後續化學dispatch，另N或acid與mix真共享circ/先owner釋放不OFF他人；純helper/獨立UI mock都不算交付。
- Workstreams：backend owner只寫本隔離backend、Card owner只寫本隔離Card（均不得更改本契約/wire）。各自驗證用自己的owned build snapshot，引用peer用sealed P3b或標明fixture，不能讀正在改的peer充作整合；父端join後真S5 shipped payload→native/原生UI可操作路徑再joint SPEC→品質。早期partial checkpoint須清楚已接通/未接通，別到最後才保存。
