# P2 控制切片契約：補水＋原生運行入口＋Card

> 本次獲准繼續開發，交付下一個可操作的P2切片，不將P2冒稱P3–P5完成。原HA不連線、不寫入、不部署、不發tag/release。父端負責整合審查與推送；worker不得commit/push。保留歷史證據。

## 1. 交付範圍

原生Options明確綁定補水輸出並確認風險/啟用前設定 → 總開關/補水子開關 → start_flow服務或整輪Switch啟動 → 後端事件驅動補水 → 高水位/正常停止/急停/失效/期限關閉並確認 → Card讀取真實原生狀態。

僅補水可運行；養/酸/獨立混合能力為false且原生對應Switch不可啟用。不得假裝已有加藥。P1舊監測Sensor/10 Number契約保留，另建schema2控制Sensor；舊Card只看舊監測Sensor，不能暗中有控制權。README清楚區分本槽有控制功能與舊監測卡本身不控制。

## 2. 已選工程預設（不需再阻擋使用者選型）

- 原HA仍唯讀；測試僅隔離HA、記憶體/假設備與本機瀏覽器。禁止讀取/使用HASS_TOKEN或呼叫外部HA。
- 每槽預設總OFF、各階段OFF，無輸出綁定/未確認commissioned不可啟用總開關或啟動。Save/Cancel不調用輸出，不自動ON。
- 原生Options保留P1來源/新鮮度表單及提交語意，擴充補水控制設定；不能讓舊表單或來源更新覆蓋中間Number/開關寫入。所有新設定讀最新options合併，保存需驗證。
- 補水輸出必須為使用者明選的已註冊switch，保存registry穩定身份而非只信entity_id。移除/替換/停用/來源修改/不合法別名要失效封鎖；重命名可跟隨同registry身份。跨槽拒絕相同實體輸出/可識別別名重複擁有。不推測未知實體別名，不宣稱解決全部設備別名。
- 更換綁定/commissioning僅總OFF且本輪已停止/輸出已知OFF時允許；不偷偷關外部/舊綁定輸出。已綁定輸出開啟的重啟狀態不得當閒置安全；明示故障/需核對，絕不重跑。
- P2啟動要求ph/ec/level皆有限/單位正確/新鮮，過期/移除/未來時間戳均阻擋；目標區間以外不是資料invalid，不因此禁止補水稀釋。運行中任何必要來源invalid即停止。輸出未知/不可用禁止開啟。
- 補水僅液位<level_low啟動；已不需補水明確拒絕、不假造新成功本輪。達level_high立即停止，非3分鐘輪詢。timeout使用refill_timeout，單調時鐘、有界回饋等待；新Options的回饋期限可前台調整，保守初始10秒並標示工程預設非原HA值。低/高標/逾時收緊即生效，放寬不擴大已受理本輪界限。
- 每階段星期以HA當地時區在實際輸出開始前檢查（含等待/授權後），不允許則拒絕/略過且不等到另一日；四階段星期保存，預設七日、空集合為無允許日。手動服務/Switch不豁免。
- 控制/停止/錯誤皆後端擁有；總/子OFF撤銷世代、取消等待/後續ON並確認關閉。輸出ON已送出不能宣稱回滾，必須在返回後確保跟進安全OFF。停止未確認保持stopping/fault，Switch不能假報OFF。停止中禁止重啟；所有安全收尾需有界，不能因取消/卸載拋失。
- 正常停止非急停；急停鎖定、復歸分開。復歸需本槽輸出已知OFF、必要來源可用，不開馬達、不開Enable、不自動續跑。卸載/HA停止安全收尾，拒絕卸載也不恢復先前工作。
- 人類控制預設admin-only，user_id為None的原生內部automation可用；拒絕未知/停用/非管理員使用者；傳遞Context。原生Switch/Button與domain服務共用校驗，避免entry存在就當授權。每次await後及實際輸出前重查active/世代/授權/設定/來源。
- start_flow顯式必填config_entry_id，先拒絕missing/null，驗證domain/loaded。SupportsResponse.OPTIONAL，要求回應才傳accepted/run_id，否則None；原生例外不包success-shaped error。
- 一槽一輪：運行中再次Switch ON為無新副作用；不同service請求busy拒絕。可選request_id非空長度<=128；有限去重（建議64筆/24小時、記憶體、重啟不保證），授權後才可重放回執且不得重啟。無request_id也不能雙啟動。
- 服務在async_setup註冊，無loaded entry亦可清楚拒絕；P1既有隔離tests不因服務註冊產生輸出。
- 不內建時刻/cron/日曆、不匯入Scheduler、不管理外部腳本、不提供raw馬達繞過。UI保存不致動，原生使用不依賴Card。沒有stage_link。

## 3. 凍結後端→Card控制Sensor wire v2

新控制Sensor唯一ID `<entry_id>:control_status`。state為flow_state，另保留舊 `<entry_id>:status` 的P1 schema1，不改其keys/數值語意。

```json
{
  "schema_version": 2,
  "mode": "control",
  "ready_for_irrigation": false,
  "source_entities": {"ph":"sensor.actual","ec":"sensor.actual","level":"sensor.actual"},
  "parameter_entities": {"level_low":"number.actual"},
  "parameters": {"level_low":2.25},
  "reasons": [],
  "capabilities": {"refill":true,"nutrient":false,"acid":false,"mix":false},
  "control_entities": {
    "automation_enabled":"switch.actual",
    "refill_enabled":"switch.actual",
    "flow_run":"switch.actual",
    "emergency_stop":"button.actual",
    "reset_fault":"button.actual"
  },
  "allowed_weekdays": {"refill":["mon","tue","wed","thu","fri","sat","sun"],"nutrient":[],"acid":[],"mix":[]},
  "stage_states": {"refill":"idle","nutrient":"unsupported","acid":"unsupported","mix":"unsupported"},
  "flow_state":"uncommissioned",
  "fault":null,
  "run_id":null
}
```

- source_entities/parameter_entities/parameters/reasons型別與原P1一致，10參數keys未變；上述map為縮短示例，不是只留一參數。allowed_weekdays實際新entry四階段皆預設七日，示例空集合展示型別。未支援階段不因有星期就可執行。
- flow_state vocabulary：uncommissioned, disabled, idle, starting, refilling, stopping, completed, aborted, fault。stage_states.refill可同詞彙，另可skipped_weekday；fault為有界code字串或null，run_id為後端生成字串或null。
- control_entities只提供此entry持有、Registry/生命週期有效的實際Entity ID，不由title推算；不可用target可省略。unsupported原生階段Switch可存在但available=false，不在map提供可操作target；Card以capabilities顯示「尚未支援」。
- 原生控制unique key：automation_enabled/refill_enabled/nutrient_enabled/acid_enabled/mix_enabled/flow_run/emergency_stop/reset_fault。各entry隔離。
- Card依P1參數metadata及既有驗證顯示10 Number；v2額外顯示控制模式/flow_state/fault、總/補水/運行Switch與急停/復歸Button。設定不致動，不因收到attributes就callService。
- Card只呼叫已映射switch.turn_on/turn_off及button.press，前台不使用config_entry_id直接繞過Gate；原生Entity handler將entry/context帶入同一控制器。
- Card每次事件依最新schema/mode/map/Entity domain/state/能力再驗證，拒絕缺target、舊map、不可用state及錯誤domain；不以舊已渲染按鈕授權。延續跨槽/卸載/過期Promise/草稿安全，失敗可見，不樂觀改state。
- v1繼續原來影子模式，不能出現控制操作；未知v3/不相容契約安全拒絕。不顯示灌溉許可，P2永遠false。

## 4. 驗收及檔案所有權

Backend worker只改backend庫production/tests/本次P2證據及P2 handoff文件，不寫父端主規範、不改Card。Card worker只改Card庫JS/tests/demo/版本metadata與P2 handoff，不改backend。不commit/push，不連HA。

TDD先真行為RED→GREEN，保存精簡不可覆寫快照/命令/raw結果；不能以import/callable缺失假稱RED。至少測原生Config/Options保存/取消、原生Number/Switch/Button/services、正確/缺/錯/未載入目標、非管理員/內部呼叫、低/高水位、timeout/過期/外部開關異常、急停/復歸、無輸出、Registry替換/停用、跨槽共享、重複/快速OFFON、等待中停用/卸載/授權變化、重啟不致動及回饋失敗。不得為新功能弱化P1測試；必要新增fixture，保留P1無輸出斷言。

Card需原Node/Chromium回歸＋v2真正點擊/操作/失敗/換槽/斷線/錯target/未知契約/窄寬幾何。parent需另作shipped Card事件→真後端原生handler的跨層驗證，不拿兩層mock各自綠當對接成功。

先SPEC再品質/安全審查，最多兩次具體修正；本次交付P2，不為證據無限擴充。父端更新README/共同規範/Issues、stage明確清單與exact-head CI。未完成不得關Issue #2；P3–P5保持open並繼續保留完整承諾。
