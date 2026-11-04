# P3c R4 exact202 — affected joint SPEC PASS

## 結論／權限
**JOINT SPEC PASS（source-bound、affected recheck＋fresh S5/Core 雙向整合）**。本次未發現需升級的新產品 blocker。這不是獨立品質批准、發布批准或 Issue3 關閉；P3c/I3 仍 OPEN，used4/limit4，沒有第五輪，也沒有改產品或契約。

對象 `nutriculture-p3c-review-r4-successor`，MANIFEST SHA256 `23be9cac518af780c5c59434983b6353394afc93959051148c92a0ea2487e818`，exact202。完整讀契約（§7優先）、wire、R4品質修補交接與原品質 REQUEST_CHANGES；逐差異讀四個production修改及其session/source整合，未把兩helper正確當整體SPEC證明。

## 本次實測
| 邊界 | 真結果 | 判定 |
|---|---|---|
| 原Q1，逐字原probe | 健康ph≥6的mix受理且真circulation ON後，ph unavailable → `source_invalid`、running false、circ OFF、mix fault。condition=null同路徑仍繼續mix，fault null。 | 原反例閉合；非要求所有mix依賴ph/ec |
| 原Q2，逐字原probe、無時鐘seam | 真Options C6/F1，第一輪N正常completed、pump/circ OFF、leases/session空後真sleep超舊cutoff，再registered start_flow接受新run且pump ON、fault null。觀察舊cutoff34215.0739012、新session34215.186007。 | 原反例閉合；不是重置未結清session |
| held circ ON | 原 `test_v5_pending_circ_on_does_not_block_independent_safety_off` 真pass：pending ON不阻其他owner獨立OFF；late ACK仍必收束。 | 原pending/running真值保留 |
| two circ owners | 原 `test_two_circ_owners_first_completion_never_turns_off_other` 真pass：共用ON、先完成owner不關他人circ、同session cutoff不重置、最後owner才OFF。 | shared-session保護保留；原邏輯mix clock seam非實體cutoff認證 |
| 新獨立相鄰：refill明確ec條件 | registered plan Save `refill.condition=ec≥.6`，真refilling且physical ON；核accepted required_sources為frozenset、含ec（refill原必需level/ph/ec未縮減），StateMachine ec unavailable → 全flow source_invalid、refill physical OFF且own fault。 | PASS；不只重測mixhelper |
| R4永久8cases | selected ph失效／ec錯unit／invalid→restored latch／nonfinite／stale／健康ec跨出gte仍繼續；mix兩closed runs；N真expiry後新run/session。 | 全pass；stale測試state-age seam、mix新輪有明示logical/stale-field seam，不能取代原N真sleep |
| I1–I4永久10cases | 真native plan表單／open-abort／首次Save transition／Preview Cancel／busy／兩revision／no-op stale CAS／legacy星期拒絕／不可達refill／後列獨立refill改善等待／blocked不傳遞finished／skip兩anchor。 | 全pass；維持I1–I4 CLOSED |

`run.py original`：**6 collected、6 passed、0 skipped、child0、14.75s**。
`run.py remaining` affected：**19 collected、19 passed、0 skipped、child0、13.57s**（新增獨立1＋既有SPEC10＋永久R4 8）。這些與full及歷史cases重疊，**不加總成新永久suite數量**。

首條實測後已寫 `CHECKPOINT.md`。原Q1/Q2 probe SHA分別維持 `98ef93eab2ab8ff3473adff549e3416428db1502aa42cfc2b4a04e054dd11640`／`411f73296567514affe626b177ae5a17d6a0d1eca96ba1c905187dee6a36d830`；無改assert、xfail、skip或跑舊覆寫runner。

## Fresh shipped S5 ↔ Core
本OUT fresh1是真新exact202 owned build：native父0、Playwright子0，**13真WS requests、7日draft Preview、page_errors=[]**。原browser probe逐字不變，native只將既有terminal capture handle改指R4 full的真輸出，不改assert或Controller/Auth/Store。

真shipped Card controls → JSON-lines原payload（僅transport id）→ Core ActiveConnection／非owner admin的真AuthManager／registered call_service → 原Core response回同DOM。已實跑：Cancel零寫、未存七日Preview零options/I/O、plan原子CAS與兩revision／全值讀回、fresh reopen、settings7/plan5草稿namespace獨立、雙Card原payload conflict零寫、deactivated admin拒寫、fresh Store durable讀回。

並從實際Card flow_run再開新輪，真refill/mix重疊，mix先結清而refill仍ON，再N→acid；同Card讀到四completed與四physical OFF。`join/fresh1/multistage.json`、wire、Store、events/result為本輪新證據，不借舊R3 freshjoin充作新bytes覆蓋。join邏輯mix完成clock加速沿原合法fixture；不加速physical session cutoff。

另consume R4 full既有service/switch terminal captures展示兩入口。已核producer test bytes對final-full receipt前後相同、兩parameterized真case在authenticated raw為PASSED、檔案存在且exact30 keys／四OFF，本次pre/post SHA一致。**capture輸出本身未列入原full snapshot receipt的hash inventory**，所以本次只記新測量hash及producer來源，不冒稱其bytes原已sealed、不冒稱本輪重跑這兩capture入口；上述fresh實際flow_run四stage整合是獨立新跑。

## Source／imports／compose
`authentication.json`全部checks true：source202 pre/post、exact set、native與join兩build各202前後均相符；原198仍全相符。R3→R4僅control/flow/flow_settings/mix四production變更及四新增handoff/progress/test/runner，Card/wire/contract等其餘相同。Card SHA `4fd326a406531c601e490393d77e4ac1632a2e72cd1df9bc424aaa1909250e0f`。

真actual imports：原native29、affected31、join28，各個實際path均在本OUT且逐bytes核對frozen source/test（額外原probe及新adjacency另保留原始SHA）。不是用原庫custom_components；原庫只提供SDK interpreter。argv/cwd/env/child與closed raw SHA逐run記在 `*-receipt.json`，FINAL列出全部交付hash。未在自家仍開啟的stdout上自hash。

已重新hash R3 SPEC FINAL的51 artifacts、UI continuity39 handles、原品質FINAL20 artifacts全部相符。原品質結論仍是歷史REQUEST_CHANGES，沒有追稱它批准；新結論針對R4 affected SPEC。

Whole joint SPEC採逐cell compose：
- 本次重跑改動會經過的source健康／session closure／I1–I4／Preview／native表單／雙writer CAS／fresh S5 Core整合。
- 未變namespace/native-plan/UI／legacy-schema/Card-input cells只在既有實測與實際未變inputs範圍沿用；舊R3 join不冒稱覆蓋新runtime bytes。
- Node13/browser38與320px64controls／trusted5typing5telemetry／18samples無focusout/replace：沿同bundle既有證據限定範圍compose，**本次未重跑**，不是全UI或視覺審美批准。
- R4 full339的child0與raw SHA本次再核，父端已核112source/114snapshot/85imports；本SPEC沒有為更大總數重跑full，也不冒稱另核其全部85imports。339=永久335＋fresh full-build複製的原獨立probe4，不是published clean tree都339。
- Ruff scoped既有85files check/format0由父端驗證沿用，未重跑；歷史全tools非綠，絕不聲稱CIall綠。

## 問題／限制
- 首次provenance verifier把UI handles誤認dict，實為list，驗證程式在讀取處AssertionError；只修owned verifier支援實際schema後全部真核通過。非產品失敗，原錯誤記 `harness-notes.json`。同時如實記terminal capture不在原receipt hash清單的資格限制。
- SDK有既有5項deprecation warnings；join的settings_conflict與Unauthorized是預期拒絕，不是漏報測試失敗。
- 沒有窮舉架構／race矩陣、實體跨午夜、site HA、硬體或外部physical cutoff保證；未將同session保護替換成fresh-run reset。
- 所有新增檔與runtime只在本OUT。source／原庫／舊evidence／契約只讀；無install、外網、siteHA/auth實機、stage/commit/push/tag/deploy。ephemeral `.storage`／token不列artifacts、不打包。無品質／發布授權；後續獨立品質另gate。

## Owned workflow lesson（唯一可寫範圍內，不改profile技能）
依exactmanifest複製fresh builds→逐字原反例與真sleep→首實測checkpoint→獨立鄰界＋受影響永久SPEC cases→同shipped probes雙向Core join→close raw後hash→source/build/import逐bytes→舊evidence handles按真schema驗證→只compose未變inputs；producer已驗不等於capture輸出原已sealed，須明列限制。
