> 現行來源：P5b同槽pH／EC／液位歷史已完成正式來源交付（Backend `53e4f0b5dceb2cbd8c76bcef0470636d37868e41`、Card `863406040b2537f57001caa0d59c56f16af97a67`；精確CI `42476705488`／`42476693050` 已核驗）。P5c重要UI已完成隔離整合與獨立SPEC／品質安全兩審；來源出版與本提交hosted CI分別按實際核驗結果為準，不冒用舊批准。最新順序：重要UI → 另行確認測試機與致動範圍後實機測試 → 其餘P5。完整P5仍保留，未部署、HACS、tag或release；P3／P4／P5a／P5b結案修補額度不重置。

# 開發目標對齊與目前推進順序

> 2026-11-07 目標審查：產品主線仍對齊原始需求；需修正的是過度偏重驗證管理、文件混用歷史狀態，以及不能被綠色回歸掩蓋的功能缺陷。本文件為目前目標盤點，不變更已凍結契約或既有修復輪次。

## 1. 產品仍要完成什麼

| 原始目標 | 現行能力／狀態 | 邊界與剩餘工作 |
|---|---|---|
| 可重用、多槽、後端唯一權威 | integration 每槽穩定身分；原生前台與 Card 共用後端 | 不硬綁農場、設備或收件者；完整兩槽全流程與共用輸出產品驗收仍屬 P5，不冒稱完成 |
| 補水、加養、加酸、必要／獨立攪拌 | P2／P3a／P3b／P3c 軟體來源已交付 | 必要混合不因獨立攪拌關閉而取消；現場校正未做 |
| 使用者可編流程 | 四唯一階段、順序、合法重疊、相對延遲、有限條件、星期與七日預覽已接通 | 各階段真正開始前依 HA 時區查星期；不是固定串行，也不是任意腳本或無界 DAG；進階視覺編輯仍保留 P5 |
| 原生操作與外部觸發同權威 | `uninus_nutriculture.start_flow` 與原生 `flow_run` Switch 共用受理及安全 gate | Enable 不是 Start；單階段不隱含接續；停止、急停、復歸分離；不增加獨立 stage_link |
| 平均目標與可調安全上限 | pH／EC 中點停止續藥；脈衝→必要混合→有效新讀值 | 完成不等於瞬間達標；最低液位、所有權、累積劑量／期限與硬體保護不能繞過 |
| 配方、品質與灌溉許可 | P4a／P4b 軟體來源已交付，原生 Options 與 Card 接通 | 新 `quality_v1`／唯讀 permit 與舊 S1–S5 `ready_for_irrigation=false` 分開；許可不是直接啟動滴灌 |
| 外部結果與可選通知 | P4c正式來源、兩審、553／82與真Core／Card join、exact-HEAD hosted CI及產物核驗已交付 | 不等於實機或HACS實裝 |
| 完整產品體驗 | P5a視覺關係入口／手機鍵盤首片已交付，完整P5未完成 | 十二組完整inventory保留；同槽感測歷史已交付，先完成重要runtime／時間軸UI，再另授實機，最後選配診斷、完整多槽、文件備份、原生宿主／HACS與發行驗收 |

規範優先序與具體操作見 [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md)、[CONTROL_DECISIONS.md](CONTROL_DECISIONS.md)、[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)。[FUNCTIONAL_PARITY_REVIEW.md](FUNCTIONAL_PARITY_REVIEW.md) 保留原始 F01–F36／D01–D11 的歷史依據，不將舊研究待定項重新打開。

## 2. 這次修正的偏差

1. **推進方式回到可用能力。** 不再建立通用測試框架、純封存階段或重複包裝舊能力當產品進展；不因案例數變多就宣稱完成。已驗證且未改的部分沿用原證據，新候選保留必要受影響回歸、整合 SPEC 與獨立品質／安全關卡。
2. **修正狀態而不改寫歷史。** P4b與P4c軟體來源、兩審、出版等價、exact-HEAD hosted CI及產物核驗均已正式交付。原M1 REQUEST_CHANGES、timeout、來源寫入違規與無效RED皆為保留的歷史，不回寫成成功。
3. **既有缺陷已閉合。** 故障cause／episode、private Options卸載及quota定點修復已納入R4兩審與完整gate；不再列為正在修復，不改P3控制loop。
4. **P3急停例外已閉合。** 歷史MixStage.deadline反例保留；explicit mix授權窄修及回歸已完成並由R4兩審／553 gate覆蓋。P3歷史4＋1＝5/5結案，不從零重新計算。

## 3. 本輪P5b歷史與後續保留範圍，不重開P5a交付

- P4c正式來源、兩審、出版等價、push、exact-HEAD hosted CI與遠端／下載核驗均完成，不再列pending；P4c 4/4、P3 5/5結案。
- P5a四階段可操作關係／手機鍵盤已完成整合、獨立SPEC→品質、正式來源出版、exact-HEAD hosted CI及遠端核驗；不再列為待凍結／待兩審候選。本提交P5b完成選槽→展開歷史→1h／6h／24h→三來源曲線／資料點／可及資料表；僅經既有source_entities讀Core History／Recorder，不新增DB或後端控制契約。
- P5a joint-review修補1/1與另具名read-side revocation修補1/1均已用並交付；P4c 4/4、P3 5/5結案不重置。新歷史候選仍須必要受影響回歸與整合SPEC→獨立品質／安全，不把舊CI當新候選批准；不增加純封存或重複驗證里程碑。
- 完整P5十二項保留於[P5a操作說明](P5A_VISUAL_WORKFLOW.md)，先完成重要runtime／時間軸UI，再另授實機；其後選配診斷、雙槽commissioned隔離／共享輸出矩陣、完整文件／備份及HACS／發行；不重做已交付P4c。

## 4. 明確排除與授權邊界

- 外部擁有何時觸發整輪；不內建 scheduler／cron／日曆、不匯入19排程、不接管8個滴灌腳本、不自動補跑。
- Card 不直接控底層馬達、不樂觀改安全 Entity、不持有關泵 timer。通知 ACK 不解除故障，通知失敗不影響安全停機。
- 不讀取／使用現場 HA 憑證，不連線、寫入、接管或部署原 HA；僅隔離 Core、假硬體與本機瀏覽器。推送功能來源不等同部署或實機 commissioning。
- 不建立 tag/release；HACS 實際安裝、物理雙控／採樣／保護驗收仍待各自授權與實測，不以 Public repository 或隔離綠測試替代。

## P5a 視覺工作台與操作入口

四階段關係按鈕可進入既有規則欄位，保留調序／重疊／延遲／有限條件／星期→七日後端Preview→明確套用→native讀回／重開路徑；見[P5a視覺工作台操作說明](P5A_VISUAL_WORKFLOW.md)。真隔離Core19 requests整合與修正後獨立SPEC→品質兩審已完成；既有P5a基線精確HEAD hosted CI與遠端交付核驗亦已完成；後續新候選另驗自身CI，不宣稱完整P5或實機完成。草稿示意／Preview不保證物理可行性或arrival；不增加schema、scheduler、raw IO或現場控制。

## P5b：同槽歷史（來源已正式交付）

完整使用路徑、真值／權限／生命週期與保留範圍以[P5b歷史契約](P5B_HISTORY_CONTRACT.md)為準；本片功能、整合驗收、兩審、正式來源出版與exact-HEAD hosted CI及產物核驗已完成。不重開P5a既有交付或已結案修補額度。


## P5c重要UI與後續順序（隔離整合與兩審完成）

1. **重要UI已實作並完成隔離驗證／兩審**：四階段即時運行視覺、真資源等待／略過／停止確認、HA觀察輸出、Recorder的stage／output／permit與停止原因時間軸；補齊新增畫面的手機／鍵盤與切槽一致性。沿用後端唯一權威，不把草稿當運行計畫、不把輸出狀態當物理到達、不把歷史許可當現行授權。
2. **再進行實機測試**：完成必要整合與獨立SPEC→品質後，先確認指定測試機、硬體、可連線／可致動範圍與停止條件。此排序不解除原站不連線、不讀取現場憑證、不部署的現行界線。
3. **最後補其餘P5**：選配水溫／通訊診斷、完整兩槽commissioned與共享輸出矩陣、完整HA宿主／HACS、文件／備份還原及另授發行準備；不是取消這些需求。

P5a編輯入口與P5b感測歷史已交付，不重做。P5c契約見[P5C_RUNTIME_TRACE_CONTRACT.md](P5C_RUNTIME_TRACE_CONTRACT.md)。
