# P3c R4 exact202 獨立整體品質重查

## 結論：APPROVED（品質／安全 gate，非發布授權）

獨立審查對象為 `nutriculture-p3c-review-r4-successor`，MANIFEST SHA256 `23be9cac518af780c5c59434983b6353394afc93959051148c92a0ea2487e818`。本審查未實作或修改候選；以先前完整 whole-slice source review＋本輪完整 delta review／真 native 原反例及新鄰界，批准**目前完整 exact202 品質範圍**。沒有未結產品 blocker。原 exact198 的 REQUEST_CHANGES 保留原結論，不能追稱當時批准。

used4/limit4，未開第五輪、未修產品、未換模型/provider；沒有發布、部署、合併、關閉 Issue3 的授權。P3c/I3 仍未發布。

## 來源與讀碼

先核 exact202 實體集合與各檔 SHA 並寫 CHECKPOINT，再實測。讀契約全文／wire（§7優先）、P3C_QUALITY_FIX_HANDOFF、原 whole 品質 REPORT，逐行讀完整四 production delta 及周邊 admission/run/session/source/MixStage；新增永久測試及 evidence runner 亦已讀。程式比對原 exact198 逐檔仍相同；對新202，舊198中僅 control.py、flow.py、flow_settings.py、mix.py 四 production 改，新增 handoff/progress/test/runner 四檔，其餘所有舊檔不變。既有 tests/assertions、Card、wire／contract 均未變。

Q1：accepted row 產生 frozenset required_sources，非下輪可變 options；active owners 先處理捕獲 event payload，invalid→restored 仍 latch，coordinator 持續健康檢查，MixStage dispatch/validate同機制。只驗健康、不持續執行 admission 數值閾值；null-condition mix仍 level-only。非mix原必需 level/ph/ec未縮減。

Q2：fresh admission 在新run_id之前，先要求無 leases、session start/cutoff空、所有owner及operations結清，已知binding皆off，才清所有stage的兩個per-run欄位。此操作不在新lease／retry ON路徑，未改原最早ON session cutoff、late ACK或獨立OFF。

## 實跑／原反例閉合

真 Core SDK Python3.14.5／pytest9.2.0；原庫只供 interpreter。cwd/config/PYTHONPATH皆 owned build，沒有 import 原庫 custom_components。原兩probe逐byte複製，原assert完全不變。

| 真測試 | 結果與意義 |
|---|---|
| 原Q1 ph loss與null-condition對照 | PASS；explicit失效→source_invalid及physical OFF；無關ph失效不阻level-only mix |
| 原Q2 nutrient | PASS；真native Options C6/F1、正常completed及OFF、真sleep過舊cutoff、新run再ON；無時鐘seam |
| 原refill registry身份撤銷 | PASS；真registry disabled被拒並fault |
| 原held circulation ON／兩circ owners | PASS；獨立OFF、pending真值、lateACK與同session最早cutoff保留 |
| 永久R4八cases | 全PASS；ph loss/ec unit/invalid-restored/nonfinite/stale/健康數值跨閾值、mix closed runs、N真expiry新輪 |
| 新獨立鄰界：abort後完整closure再新mix輪 | PASS；真flow_run OFF使aborted；所有owner/operations/lease/session結清、circ OFF，保留舊stage cutoff；再registered start有新run_id、新session與新cutoff、circ ON且fault null。無時鐘seam |

第一child為 **15 collected、14 passed、1 failed、0 skipped，exit1，30.34s**。最後一個失敗是本審查新probe觀察器過早：前輪 aborted owner 的 circulation_confirmed 尚true，新 accepted task未執行即觸發until。觀察值 fault=null、new_session=null，並非已確證產品反例。完整原raw、probe bytes及觀察值皆保留，未改assert或產品。僅把owned新probe等待條件改為「新的實體session已建立且confirmed，或fault」後，單獨同case **1 passed、exit0、2.40s**，真觀察 session35709.1849917→35709.2524239、cutoff37508.1849917→37508.2524239。不可把初次child1說成全綠；不可把重疊執行加總為16個獨立cases。最終覆蓋15個獨立case，14個在首child通過、新鄰界在修正觀察器後通過。

## Whole-slice compose（不是重跑或抹去舊RC）

原整體品質 `p3c-quality-review-1/REPORT.md` 第56–79行完整覆蓋及所有finding集合已讀。其未變檔逐hash一致；兩個原Important Q1/Q2已由本輪原assert閉合。沿用以下明確結論，並由上述四檔完整delta及相鄰對抗例確認沒有擴成新框架／新持久化／新authority邊界：

- 四唯一列／錨點／skip／blocked／delay／可達refill：原coordinator/validator讀碼結論，affected R4 SPEC保留I1–I4；本次新增source及closure整合覆核。
- HA local weekday／七日Preview／native非JSON表單／Save Cancel：未變實作及affected SPEC真表單與七日draft結果；不聲稱跨午夜窮舉。
- 雙revision／namespace CAS／immutable next-run snapshot／熱收緊：原完整writer與鎖內ACL讀碼結論，加R4 fresh S5真CAS/Auth/Store/flowrun；未變writer字節。
- 全cycle互斥／shared circ／pending union／停止及fault隔離：本次重跑heldACK與兩owners，原其餘stop/error既有範圍沿用；新健康／fresh closure經真owner證明。
- authority／registry identity／closed faults／v1–v4／schema5 30keys四physical值：未變security及projection字節、原讀碼結論與已驗R4 SPEC；本次registry撤銷亦PASS。
- Card async／DOM／injection／demo／IRR／scheduler：Card bundle `4fd326a406531c601e490393d77e4ac1632a2e72cd1df9bc424aaa1909250e0f`完全不變，沿原完整582行讀碼與UI證據限定範圍；沒有browser安全timer／新scheduler／IRR ready。

本次重hash R4 SPEC FINAL `a721b97690dcd7dc95319a26859633cbda5fd9c40b757da9cf5001160bf715de`及其44 artifacts、原whole品質20 artifacts、UI39 handles，全部相符。R4 SPEC原6pass／affected19pass、fresh S5/Core13 requests／7Preview／0pageerrors／四stage四OFF只是**compose，非本次新跑**。UI320px64controls／trusted typing及Node13/browser38只沿用未變Card inputs，不是新畫面審美批准。

R4 full FINAL及raw SHA重核為 `183c1369ac13cf382a0dc63675d05af51a20a0f080e7e18248f9b65cc828894e`／`17546cbb1bccceca4c92fd32b951a467b4de6097c949303e4882d998f8d5bf7d`。339=永久335＋複製原probe4，不是clean published-tree339。本次未重跑full、未自稱重驗其112source/114snapshot/85imports；父端已驗之證據保留原歸屬。Ruff scoped85沿已驗結果，未新跑；歷史tools/evidence.py及全tools格式債不改、不稱CI全綠。

## Provenance／限制

`authentication.json`核source202及build202前後完全一致，真native31／adjacent28 imports均owned且逐bytes綁manifest或獨立probe（初次probe另存原bytes）。原probe SHA保持98ef93...／411f732...，完整值在FINAL。argv/cwd/env/child/raw-close SHA見receipts；沒有對仍開stdout自hash。所有新檔僅本OUT；ephemeral runtime .storage/token不列交付artifacts、不打包。

沒有site HA／真auth憑證／外網／install／硬體／外部physical cutoff認證／窮舉race或跨午夜矩陣。mix永久case的logical/state-age/stale-field seam如實限定；原N真sleep及本輪abort鄰界無該seam。R4 SPEC terminal capture bytes原full receipt未hash的限制保持：producer及本次測量不等同原sealed輸出或物理證明。未重做fresh happyjoin或全339以充數。

## Owned流程記憶

只在唯一可寫OUT記錄，不改profile skills：先exact來源核實即checkpoint→原assert bytecopy→新鄰界觀察器必等待新session而非前輪confirmed→真child/raw閉檔hash→逐import及source/build前後驗證→完整舊finding集合＋未變inputs逐格compose→獨立full-candidate品質判定。觀察器錯誤與原child1必保存，不可偷換為產品失敗或全綠。
