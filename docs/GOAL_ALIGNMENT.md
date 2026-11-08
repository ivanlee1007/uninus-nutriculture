> 現行來源狀態（2026-11-08）：P1–P3、P4a／P4b／P4c軟體來源及對應精確HEAD hosted CI已交付。本版P5a四階段視覺工作台／手機鍵盤已實作，修正後完整SPEC與品質兩審均批准，Q-01已關閉；Preview／Apply／Options／Store與fresh SDK隔離驗收已通過。P5a joint-review repair 1/1已用，P4c 4/4及P3 5/5結案不重置。本提交仍須以其精確HEAD hosted CI與遠端產物完成來源交付核驗；不得將本機或來源審查當成hosted CI／完整P5／實機／HACS驗收。完整P5十二項後續範圍保留，未tag／release／部署。

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
| 完整產品體驗 | 仍是待開發範圍，不因切片交付刪除 | P5：進階視覺、手機／鍵盤、歷史、可選水溫／通訊診斷、完整多槽、文件與備份、HACS 實際安裝與發行準備 |

規範優先序與具體操作見 [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md)、[CONTROL_DECISIONS.md](CONTROL_DECISIONS.md)、[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)。[FUNCTIONAL_PARITY_REVIEW.md](FUNCTIONAL_PARITY_REVIEW.md) 保留原始 F01–F36／D01–D11 的歷史依據，不將舊研究待定項重新打開。

## 2. 這次修正的偏差

1. **推進方式回到可用能力。** 不再建立通用測試框架、純封存階段或重複包裝舊能力當產品進展；不因案例數變多就宣稱完成。已驗證且未改的部分沿用原證據，新候選保留必要受影響回歸、整合 SPEC 與獨立品質／安全關卡。
2. **修正狀態而不改寫歷史。** P4b與P4c軟體來源、兩審、出版等價、exact-HEAD hosted CI及產物核驗均已正式交付。原M1 REQUEST_CHANGES、timeout、來源寫入違規與無效RED皆為保留的歷史，不回寫成成功。
3. **既有缺陷已閉合。** 故障cause／episode、private Options卸載及quota定點修復已納入R4兩審與完整gate；不再列為正在修復，不改P3控制loop。
4. **P3急停例外已閉合。** 歷史MixStage.deadline反例保留；explicit mix授權窄修及回歸已完成並由R4兩審／553 gate覆蓋。P3歷史4＋1＝5/5結案，不從零重新計算。

## 3. 下一步：P5a可用切片，非重新出版P4c

- P4c正式來源、兩審、出版等價、push、exact-HEAD hosted CI與遠端／下載核驗均完成，不再列pending；P4c 4/4、P3 5/5結案。
- P5a已合併四階段可操作關係、手機鍵盤及薄native helpers；真隔離Core19 requests整合GREEN已取得，不是smoke。最終docs凍結後只跑必要完整native、affected S5/P4a/P4b/P4c joins及static；不重跑已hash-bound相同Card全套，不改產品／測試洗綠。
- 本機候選完成gate後由父代理安排獨立SPEC→品質兩審；joint-review repair仍0/1。未經兩審、未發布、沒有現場操作，不自授APPROVED。
- 完整P5十二項保留於[P5a操作說明](P5A_VISUAL_WORKFLOW.md)，接續歷史／選配診斷、雙槽commissioned隔離／共享輸出矩陣、完整文件／備份及另授HACS／實機／發行；不重做已交付P4c。

## 4. 明確排除與授權邊界

- 外部擁有何時觸發整輪；不內建 scheduler／cron／日曆、不匯入19排程、不接管8個滴灌腳本、不自動補跑。
- Card 不直接控底層馬達、不樂觀改安全 Entity、不持有關泵 timer。通知 ACK 不解除故障，通知失敗不影響安全停機。
- 不讀取／使用現場 HA 憑證，不連線、寫入、接管或部署原 HA；僅隔離 Core、假硬體與本機瀏覽器。推送功能來源不等同部署或實機 commissioning。
- 不建立 tag/release；HACS 實際安裝、物理雙控／採樣／保護驗收仍待各自授權與實測，不以 Public repository 或隔離綠測試替代。

## P5a 視覺工作台與操作入口

四階段關係按鈕可進入既有規則欄位，保留調序／重疊／延遲／有限條件／星期→七日後端Preview→明確套用→native讀回／重開路徑；見[P5a視覺工作台操作說明](P5A_VISUAL_WORKFLOW.md)。真隔離Core19 requests整合與修正後獨立SPEC→品質兩審已完成；精確HEAD hosted CI與遠端交付核驗另列，不宣稱完整P5或實機完成。草稿示意／Preview不保證物理可行性或arrival；不增加schema、scheduler、raw IO或現場控制。
