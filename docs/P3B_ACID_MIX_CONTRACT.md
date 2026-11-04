# P3b 最後契約候選
2026-11-03；只寫 scratch、未測試／自批准。參照P3a F1的SPEC PASS；品質發現Q1生命週期投影缺口，第二輪限定修補進行中。不得改其凍結source。本候選已由父端核對並修正循環期限／既有N遷移邊界，新增介面仍待實作，尚未採納到兩庫。

## 1 版本與 exact snapshot
已核對 control_settings.py/dosing_settings.py/config_flow.py、Card parser/groupwriter；限讀 manager writer/targets、sensor、services 必要部分。星期四 `thu`。原 N-only v3／13-key dosing／10 Number ID、單位與 ACL 不變。
Options 成功保存酸／獨立mix專屬設定（含未commission草稿）才同交易 persist `options.control_contract_version=4`；開表/Cancel/拒絕/只改既有circulation_output不升版。升版後停用/fault/清綁定/重啟不降版；未知版本拒控制。舊consumer讀v4永遠fail-closed、零call，不投影有控制的v3。
Snapshot integration-owned exact keys（不含HA自加metadata）：
```
schema_version,mode,ready_for_irrigation,source_entities,parameter_entities,
parameters,reasons,capabilities,control_entities,allowed_weekdays,stage_states,
flow_state,fault,run_id,settings_target,settings_revision,dosing_parameters,
acid_parameters,mix_parameters,safety_parameters,nutrient_phase,acid_phase,
dose_progress,acid_progress,output_states
```
固定4/'control'/false；sensor state=flow_state。parameters exact10：
```
level_low,level_high,ph_low,ph_high,ec_low,ec_high,
refill_timeout,ec_timeout,ph_timeout,mix_duration
```
沿原範圍/step/全組驗證；m、pH無單位、mS/cm、四時間min。source_entities exact `{ph,ec,level}`，保存sensor ID；原三來源表單保留，執行健康要求另定。
parameter_entities為10 key的Registry真子集、ID唯一，可空、不補假ID。manager.targets省略disabled/缺失/非有限state；現validV3卻要求exact10，不假稱已容忍缺項、不放寬v3。validV4接受子集；沿target/groupValid：缺映射/不可用/min,max,step無效→禁該欄且整組Apply禁用；不撤其他native控制、不擴全局權限。
capabilities/stage_states/allowed_weekdays exact `{refill,nutrient,acid,mix}`；capability嚴格bool、完整commission/identity/保護且engine接通才true。星期列表mon,tue,wed,thu,fri,sat,sun、不重複，空=不准啟動。
flow_state=`uncommissioned,disabled,idle,starting,refilling,stopping,completed,aborted,fault,waiting_resource,dosing,mixing,waiting_sample,stabilizing`。
stage值=`unsupported,idle,starting,waiting_resource,running,stopping,completed,aborted,fault,skipped_disabled,skipped_weekday,blocked_dependency`。各stage須由其accepted owner之phase/result投影；不得將全域disabled/uncommissioned直接放進stage。refill的refilling在stage欄映為running；master OFF、reset或設定更新不可把已accepted終態冒充成功或抹除成非法stage值。永久跨層回歸沿P3a Q1的真native→shipped consumer路徑。
phase=null或starting_circulation/pulsing/confirming_off/mixing/waiting_sample/stabilizing，非作用stage=null；progress exact `{pulse_count,reserved_on_seconds,stable_count}`，計數非負安全整數、秒數非負有限number，未用全0。output_states exact `{nutrient,acid,circulation}`，on/off/unknown，未綁unknown。reasons字串列表；fault/run_id非空string|null。
control_entities同entry Registry子集且ID唯一：switch=automation_enabled/refill_enabled/nutrient_enabled/acid_enabled/mix_enabled/flow_run；button=emergency_stop/reset_fault；未支援stage不映射Enable。revision非負安全整數；settings_target exact `{config_entry_id,service}`，本entry非空ID、service=apply_control_settings_v4，domain=uninus_nutriculture。

## 2 安全權威、null與mutation
Q=exact9：
```
safe_min_level_m,pulse_seconds,max_total_on_seconds,max_pulses,
post_mix_seconds,sample_wait_timeout_seconds,stable_samples,
stable_interval_seconds,flow_timeout_seconds
```
S=exact4：ph_danger_low/ec_danger_high/ph_high_alarm/ph_high_alarm_seconds。
acid_parameters=Q；mix_parameters exact `{safe_min_level_m,flow_timeout_seconds}`；dosing_parameters=原13 Q∪S。未commissioned stage snapshot map=null，已commissioned必完整非null且無null值。safety_parameters永遠exact S非null、唯一可編安全權威；N的S唯讀鏡像。
新服務payload exact：
```
{config_entry_id,expected_revision,parameters,dosing_parameters,
 acid_parameters,mix_parameters,safety_parameters,allowed_weekdays}
```
null同snapshot，不准藉服務commission/清空已commissioned map。N非null仍傳13，S須等於全局S，否則全拒；server只取Q、按全局S同交易重建13。Card僅一份S輸入。
升版S逐key取舊dosing合法值，缺項用原DEFAULTS 3.8/1.3/6.8/600，非法拒絕。已commissioned N缺13拒升版。未commissioned N內部options.dosing_parameters保留合法Q子集+server S；不補未知物理值、snapshot=null、不進engine/v3投影。mutation N=null保留草稿Q、更新S；酸-only不用造N配置。酸/mix部分Options草稿同理內部保留、snapshot=null，服務null不刪草稿。
Tank.write_settings保留keyword parameters/dosing_parameters/control/sources/expected_revision，新增acid_parameters/mix_parameters/safety_parameters；sentinel分未傳/null。v4 Options均帶開表revision；同Tank.lock重驗admin/loaded/active/registry/CAS、全組validate、一次update_entry/publish；有差異才+1，Enable/fault不計。舊apply_control_settings遇v4拒settings_schema_mismatch；Number單項在lock帶當前revision走同一v4 validator，不繞S/CAS、不改ACL。可選回應exact `{applied:true,settings_revision:N}`；Card等revision/全組讀回，conflict保留草稿，Cancel零寫入/I/O。

升版本身不撤銷既有N的P3a commissioning：新增循環保護欄位尚未完整時，acid/mix不得有capability，但既有N仍依P3a保護契約，不能因只存新stage草稿就無聲失去原可用流程。一旦使用者完整宣告共用循環cutoff，所有後續使用該輸出的run均遵守該保守上限；變更仍受master OFF／無pending IO gate。不得把舊N保護聲明冒充新acid/mix的循環保護證明。

## 3 Options精確新增名
acid_output→control.acid_binding；共用circulation_output→control.circulation_binding，無mix_output。binding exact `{registry_id,platform,unique_id,config_entry_id}`。N的device_max_on_seconds/alias_notes/sample_mode/sample_attribute/report_contract_confirmed/nutrient_commissioned/nutrient_protection_confirmed不改。
新增control：
```
acid_commissioned,acid_device_max_on_seconds,acid_protection_confirmed,
acid_alias_notes,acid_sample_mode,acid_sample_attribute,
acid_report_contract_confirmed,mix_commissioned,
circulation_device_max_on_seconds,circulation_protection_confirmed,
circulation_alias_notes
```
酸Q表單acid_前綴、mix兩項mix_；S沿無前綴四名只映射全局，無前綴Q仍N。source沿ph/ec/level/max_age_seconds。
binding/source/保護修改須master OFF、無run/cleanup/pending I/O、舊新輸出已知OFF；拒角色/跨槽/已知alias衝突。safe_min、pulse/total/pulses、cutoff、保護確認/說明commission明填，未知不假值。酸其他Q可用300/600/8/300/5400工程建議，非物理證明。獨立pH sample_mode=reported需acid_report_contract_confirmed=true；sequence/timestamp需acid_sample_attribute符合[A-Za-z0-9_]{1,64}，沿N token型別/新鮮度，不借EC token。

## 4 安全循環、期限、lease
Options保存/native Enable/start_flow/flow_run同設定與commission gate；Enable零I/O。啟動/資源等待後/每次ON前重驗授權、identity、master/fault、weekday、來源、預算。最多一選中eligible stage；零/多選拒flow_configuration_unsupported，不偷取一項。必要mix不受mix_enabled OFF撤銷。
酸須有效新鮮level>=酸safe_min、pH/EC有限/正確單位/未過期、酸/循環identity及OFF/feedback/保護、獨立pH token。pH<ph_danger_low或EC>ec_danger_high必停藥；source loss/低液位/循環失效不續藥。高pH超ph_high_alarm持續ph_high_alarm_seconds只通知、不全局停機。S沿RANGES，danger_low<ph_low、danger_high>ec_high。
standalone僅bounded circulation：必需有效新鮮level>=mix safe_min、循環Registry identity/feedback/cutoff/保護；不需N/酸commission、採樣或pH/EC dosing admission。pH/EC缺失/out-of-range僅品質/告警，不阻standalone；僅本次沒有劑泵ON/pending ON、沒有尚未結清的dosing owner適用，不能轉成故障加藥後的自動續混。酸運行的危險pH/EC、來源失效、低液位或循環失效沿P3a acute fault規則及時關兩路並鎖故障；必要postmix是正常停止順序，不能凌駕急性安全關閉。
酸：circ ON確認→pulse；pH<=`(Decimal(str(ph_low))+Decimal(str(ph_high)))/2`立即OFF→確認→必要post_mix→有效新pH再評估/stable；[ph_low,中點]且相隔stable_interval才累計。初始達標仍需新樣本、舊token不累計。收緊即時/放寬下輪；酸中點tighten=max，N沿min。
F=feedback_timeout，D=min(ph_timeout*60,acid.flow_timeout_seconds)，C=circulation_device_max_on_seconds。pulse+F<=acid_device_max_on_seconds，pulse<=total。循環的有效絕對截止為min(stage開始+D,首次未結清circ ON dispatch+C-F)，保留F要求OFF確認；超過F仍未確認則fault/unknown，不能聲稱軟體保證物理OFF。每次pulse admission依真elapsed/reservation保留劑泵OFF、必要post_mix及循環OFF額度，不足就不得再dose；不能要求把sample_wait_timeout這個最大等待值與所有stable最壞等待預先相加才能保存。standalone M=mix_duration*60，M+2F須同時容納於mix.flow_timeout_seconds及C；較大的flow_timeout不代表一定持續運行到該上限，禁止額外要求整個flow_timeout都小於C。cutoff限1..86400整秒；Q/mix沿同名RANGES。runtime從dispatch計連續ON/deadline；邏輯/保護期限到期前停藥與收尾，沒有取得足夠新穩定樣本就fault/timeout，不假completed。重取lease/未確認OFF不重設時鐘；declared cutoff非實機證明。Options/preview應揭露最少穩定間隔已超出有效時間等不可完成配置，不把最大sample等待當必等時間或自動放寬任何安全期限。
Controller唯一acquire(identity,run_id,generation,owner)/release(token)，owner=nutrient_required/acid_required/standalone_mix。P3b一eligible stage、API留多owner token，不造DAG。最後owner釋放且pending ON收束才OFF；release冪等、禁獨立timer關別人的必要mix。stop=aborted、先劑泵OFF確認再release；急停=fault，撤lease/後續ON、追late ON；reset零致動、重啟不續跑。

## 5 真native首切與ownership
待跑RED沿test_p3_options/test_p3_dosing真HA fixture：hass.config_entries.options.async_init(entry.entry_id,context={"user_id":admin_user.id})→同options.async_configure(flow_id,user_input=完整酸設定)→Save/reopen驗acid_output/Q/revision→native acid Enable可用且零硬體calls。只綁酸/循環、不綁N/refill；現schema缺acid_output，真入口應未接受/保存而失敗，不手塞options/只驗helper。本次未跑。
最短GREEN：Options→writer/v4→Enable→真start_flow與flow_run兩入口→circ ON→Decimal等號OFF→必要mix→新pH stable→completed/run OFF；再同native路徑只mix到期OFF。僅設備fake。須含危險/液位/cutoff/late ON/OFF失敗/CAS舊writer/thu/多選，真sensor→shipped Card→Apply/Cancel/readback→native controls、舊Card/v4零call及P1/P2/v3回歸；helper GREEN不算交付。
解凍後一worker獨占backend custom_components/uninus_nutriculture/{config_flow,control_settings,dosing_settings,manager,services,control,nutrient,sensor,switch}.py、必要酸policy/lease、services.yaml、strings/translations、tests/test_p3b_*.py；同worker同步sibling根uninus-nutriculture-card.js、tests/test_contract.cjs、tests/test_browser.py、demo。父端協調契約/native-shipped bridge，不雙人改共有writer/controller；SPEC/品質/發布/部署另gate、不自批准。
P3c保留完整P3四stage可編順序、重疊、relative、weekday、preview；單stage不偷換完整目標。不新增排程、stage_link、配方P4、IRR ready。
