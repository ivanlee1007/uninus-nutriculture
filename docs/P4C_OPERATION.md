> 現行來源狀態（2026-11-08）：P1–P3、P4a／P4b／P4c與P5a首片已完成軟體來源交付。P5a交付基線：Backend `4a08e615bf1949ecbeea37fdba4696c5bf8d3062`（CI `42458123964`）、Card `3eaa78c55043598fd4bc666c8ef432b8870d6701`（CI `42458104719`）；獨立SPEC／品質、出版等價與遠端產物核驗已完成。 本提交新增P5b同槽pH／EC／液位歷史，功能、真Recorder整合與獨立SPEC／品質兩審已完成，B-01已關閉；出版與hosted CI以本提交的實際核驗結果為準，不冒用P5a基線CI。P5b唯一修補批次1/1已用，不重置舊額度。P5a joint-review修補1/1與具名read-side revocation修補1/1已用；P4c 4/4、P3 5/5結案不重置。完整P5十二組保留，部分已交付不等於全組完成；未實機／HACS／tag／release／部署。

# P4c 操作與驗證邊界

狀態：現行狀態（2026-11-08）：P4b正式交付與exact-HEAD hosted CI／產物核對已完成。P4c R4來源已通過SPEC及獨立品質兩審，本機完整553 cases／82 modules（144／116／137／156）與真Core／shipped Card join已完成；P4c正式來源出版、exact-HEAD hosted CI與產物核驗已完成；P5a首片亦已正式軟體交付。P4c初始2輪＋explicit Options卸載1輪＋explicit quota1輪＝4/4；P3歷史4輪＋explicit mix1輪＝5/5，皆結案、不重置。完整P5、實機commissioning及HACS實裝未完成，未tag／release／部署。內嵌0.2.0保留既有封裝，不代表功能階段。 共同契約與schema維持原凍結版本。

## 使用

1. 外部automation仍呼叫既有 `uninus_nutriculture.start_flow`，或操作本槽原生整輪switch；沿同一後端准入，不另建scheduler、不匯入外部滴灌腳本。`accepted`只是已受理，不是已開始或已完成。
2. 選本槽原生result_status sensor／Card的result_entity，或讀 `uninus_nutriculture.get_result_v1`。目前整輪優先顯示，否則保留最後terminal；active和last皆空才idle。只有所有既有輸出身份、OFF、owner、lease與待完成操作皆證實閉合後才可能completed／stopped／failed；不得以switch OFF猜成功。
3. 結果、品質與灌溉許可是三件事。completed不會授予灌溉；唯一權威仍為既有quality_v1／permit。舊S1–S5 ready=false保留。低pH／高EC idle觀察只報告，沿原安全數值、unit/fresh/finite有效性；高pH沿已有告警，不改安全控制。
4. 至本槽Integration Options的「通知管理」，或Card的通知面板，由人類active admin選persistent_notification／NotifyEntity、事件和cooldown（整數60–86400秒，工程預設300）。default disabled、無provider/target/events；沒有任意service/action、URL、模板或收件者／憑證輸入，不支援legacy service-only notify。
5. Save使用私有WebSocket與同一後端執行器，CAS取私有GET的epoch/revision。每次成功Save即使同內容亦增加revision，原生private atomic Store寫入後獨立驗實體envelope。設定不寫control options，不因通知改變quality／permit。開頁、純GET、取消和准入前拒絕不寫盤、不發通知、不動輸出。
6. 「更新通知狀態」只是快取GET。`handoff_returned`不是收件者送達；timeout表示結果未知。「標為已讀（不復歸）」只改本runtime私有ledger，不能復歸fault、dismiss原生通知、重授permit或重送。
7. 保存已進入I/O後的取消／讀回失敗可能為indeterminate，不保證未提交或已回滾。「重新讀取通知設定」才明確drain已准入I/O、fresh NativeStore load及獨立實體驗證；GET不偷讀盤，reconcile不保存、回滾、重載control entry或補送歷史。
8. 普通flow／master OFF不關通知plane；已選的停止／故障資訊仍可報。只有Core STOP、entry disable／unload關閉通知准入；安全OFF不等待通知provider或policy I/O。舊owner／policy／epoch的排隊與晚回不復活設定或改新ledger。

## 保存、重啟與限制

- 通知policy持久化；active run、last_result、通知queue／ledger／ACK只在本runtime。restart換epoch並清結果，不恢復控制、不補跑、不重送；完整歷史留P5。
- queue16、entry native in-flight1、lifetime global2、dedupe64、ledger32、provider timeout5秒、queue TTL60秒使用後端有界資源及monotonic時間。忽略取消的provider占用quarantined slot至真正settled；不承諾殺執行緒、回收外部副作用或exactly-once。第三方同步阻塞event loop不在非同步timeout可保護範圍。
- 新integration公開結果／事件不帶私有provider/target或raw exception；固定allowlist錯誤不寫Controller.fault。被選provider本來就可接收固定消息，其原生entity/events/host logs及host admin/backup不在此隱私保證範圍。
- SDK Core2026.10.4下已驗nativeStore完成觀察；instance-scoped私有 `_async_write_data`完成接點須隨SDK升級重驗。CoreSTOP證據限持住Stage2讓真I/O結清，不是程序毀損／斷電保證。

## 目前驗證狀態

先前隔離真Core／Chromium shipped Card已證GET/Save/GET→實體Store與freshload一致、NativeOptions submit/reopen/cancel、四stage假設備閉合→原生result/GET/Card同DTO；不是現場或完整HA frontend/network驗收。最後功能候選另閉合nested epoch與fresh-load cache；這些新碼與本次fresh持久化需在此次合流後重驗，不能將舊來源結果冒稱最終同版通過。

使用者已明選「只重做通知持久化，保留其餘成果」。初版unknown_command的無效RED維持歷史失敗，不重標；已在另一隔離sourcepair移除7方法business body，真nativeadmin經正式註冊GET／Save成功後以實體檔缺失形成新RED，再逐行為重實作。精確舊metadata只加notification管理key與新result sensor；原安全assert保留。全部原始證據由parent私有封存，不將runtime/.storage/auth或loopback能力匯出。

尚待：此合流來源完整既有回歸及新增測例、必要stale/clock／同run danger→failed／跨entry/request矩陣、真Card/Core新碼join、獨立SPEC→quality及精確Git／hosted CI出版程序。P5進階視覺、完整歷史／診斷、兩槽完整commissioning／共用輸出與HACS實機仍保留；未建立tag/release、未連原HA認證、未部署或向真收件者發送。
