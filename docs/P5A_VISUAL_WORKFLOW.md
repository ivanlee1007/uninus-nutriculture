# P5a 四階段視覺工作台操作說明

> P5a視覺工作台／手機鍵盤首片已完成獨立SPEC／品質、正式來源出版、精確HEAD hosted CI與遠端交付核驗；交付基線見本文README／目標對齊。後續新候選另驗自身CI。未部署、實機、HACS或建立tag/release；以下說明已交付介面，不要求或代替使用者執行設備控制。

## 入口、草稿與真值

在Card選擇後端實際的S5控制狀態Sensor，不使用pH／EC／液位來源Sensor，也不從槽名猜Entity ID。後端能力／權限未就緒時不要強行送出。打開流程計畫區，四張關係卡的「編輯補水／加養／加酸／獨立攪拌」是真按鈕：點擊或以Tab聚焦後Enter／Space，會捲到同stage既有開始規則欄位並聚焦；不是開啟另一份計畫。

**草稿關係示意不是後端可行性、物理啟動／到達時間或灌溉許可。** 已保存流程、尚未保存草稿、七日後端預覽、實際step_runtime是不同資訊。重疊只表達請求，輸出資源、最低液位、必要混合與安全條件仍由後端裁決。

## 改順序、重疊、延遲、條件與星期

1. 在原有四列欄位用上下移動改順序；四stage各一次。第一列必須明確是`flow_start`，調序不會偷偷修正規則。其餘選整輪開始、上一階段開始`after_previous_started`（可請求重疊）或上一階段完成`after_previous_finished`；錨點跟隨目前順序。
2. 改相對delay seconds、wait timeout seconds及整輪`run_timeout_seconds`，遵守欄位界限。條件只選`none`或`level`／`ph`／`ec`配`gte`／`lte`與有限值，不輸入template或service。液位m、EC mS/cm；pH無單位。
3. 每stage勾選星期一至日，空集合就是沒有允許日。星期是每階段真正admission前依HA時區檢查的允許gate，不是排程或手動豁免。Enable仍由既有原生子開關持有，不由草稿另存啟用值。
4. 看到未保存標記表示仍是草稿。一般遙測不應抹除輸入或搶焦點；參數群、流程、配方與通知草稿各自分開。

## 七日後端Preview → 明確套用 → 等待native讀回

- 按Preview，Card將同一份完整草稿與原始雙CAS送到已註冊`preview_flow_plan_v5`，取得七個weekday結果。逐日閱讀eligible、disabled／weekday skip、blocked dependency／safety、未知offset及uncertainty；不能把未知當0、earliest offset當實際arrival。預覽不保存、不啟動工作或操作輸出。
- 確認後才按明確「套用」保存；`apply_flow_plan_v5`原子提交計畫與星期，下一輪生效，不是Start。**服務回應不等於已讀回**：等待同entry、兩revision與完整plan／weekdays的native狀態一致，Card才確認已保存；等待讀回期間不要再次送出。
- 移除並重新開啟Card，核對保存值。到「設定 → 裝置與服務 → UNiNUS Nutriculture → 該槽選項」，勾選`Open flow plan editor (no settings saved)`；原生Options可上下移動、Preview、Cancel或Save。重開Options與Card應呈現同一後端真值。隔離FlowManager／Store與fresh SDK讀回已在整合證據中，並非真HA宿主瀏覽器或物理驗收。

## 取消、拒絕與並行編輯

Cancel捨棄本流程草稿／預覽並採當前後端值，零mutation；不取消已送出的後端呼叫，也不能回滾已提交保存。Preview／Cancel／管理設定零致動，不代表執行整輪零輸出。

錯誤時保留草稿及原始CAS；先閱讀錯誤，不自動重送。另一張Card、原生Options或Number已推進版本時，stale寫入必須拒絕；dirty草稿不自動rebase。重新讀取並由人協調後再明確編輯，不能覆蓋新版本。權限／槽／transport改變時舊回覆不可污染新scope；未結束write仍維持鎖到真正settlement。

## 手機與鍵盤界線

不需拖曳。Tab／Shift+Tab遍歷原生button／select／input，Enter／Space操作階段導航；星期label可點，checkbox可Space切換。上下移動後焦點留同stage可用控制；到邊界時可回規則select。普通輸入／遙測不應換節點或捲回頂部。

隔離Chromium已測Card本身320×360（viewport1280×900）、320×740、360×640及768×900、明暗主題、真鍵盤與連續輸入；短卡需垂直捲動到Preview／套用／取消。這不代表所有手機／輔助科技／HA宿主都已驗收。沒有完整screen-reader認證、實站瀏覽器、HACS安裝或物理arrival保證。

## 完整P5十二組inventory（含首片已交付部分，非十二組全未做）

- **P5-VISUAL — 四階段可操作視覺關係編輯**：關係卡可操作定位原欄位→改計畫→後端Preview→Save→native/Store重開。 **其中本段P5a入口路徑已交付；完整進階runtime視覺與其餘視覺能力仍保留，不重做首片。**
- **P5-RESPONSIVE — 手機短窄/窄高、桌面窄欄與純鍵盤**：Card自身dimensions、trusted連續輸入、stage導航/reorder焦點、Tab/Shift+Tab、Preview/Save/Cancel全程。 **P5a上述首片操作已交付；完整產品及後續新增頁面的響應／可及驗收仍保留。**
- **P5-RUNTIME — 真階段/資源等待/停止確認/物理輸出視覺**：完整運行圖分清disabled/skips/blocked/waiting/running/completed/aborted/fault/stopping；計畫與實際分開，不估算物理arrival。
- **P5-HISTORY — pH/EC/液位歷史曲線**：既有native recorder/history資料→時窗選擇→槽隔離→權限/無資料/無recorder降級，不先建新資料庫。
- **P5-TRACE — stage/output/permit變化與停止原因時間軸**：定義可得事件/週期欄位與來源→歷史查詢→時間軸與停止原因/缺資料展示；非timed估計。
- **P5-DIAGNOSTICS — 可選水溫、感測器及繼電器通訊診斷**：可選binding/單位/失效語意→設定→回讀→清除時不掛空互動DOM；不改控制必要來源。
- **P5-MULTISLOT — 兩槽都commissioned的完整產品矩陣**：同名兩槽各自全部commissioned fakehardware：四stage成功/並行/停止/故障/重啟/來源失效/參數/流程/持久化隔離，不能另一槽uncommissioned代替。
- **P5-SHARED-OUTPUT — 共享實體輸出拒絕與所有權仲裁**：兩commissioned槽測physical identity/aliases重複綁定拒絕、並發競爭/停止不釋別槽lease；若需例外共享先凍結新契約。
- **P5-COMPAT-NATIVE — 跨倉庫相容矩陣與真原生HA宿主UI**：新Card對schema/capability/readonly降級、Options/Number/Switch一致；真正宿主瀏覽器另授，不把FlowManager當實站UI。
- **P5-DOCS-BACKUP — 完整文件與備份/恢復**：P5開始併修banner及current正文，保歷史；新手設定/控制/雙控風險/備份→乾淨隔離還原身份/參數/CAS，不恢復ON致動。
- **P5-HACS-RELEASE — 實際HACS安裝與發行準備**：另授乾淨宿主HACS安裝→integration loaded→真resource→Card/native workflow；相容版本/回退/發行清單，tag/release另授。
- **P5-PHYSICAL — 物理commissioning/斷電耐久/採樣保護**：另授兩槽別名/最大ON保護/液位幾何/脈衝採樣/OFF回饋/斷電復原與外部雙控驗收，不取憑證或連原站。

已交付P5a首片改善可操作關係、手機鍵盤、必要相容與current文件；同槽歷史為下一開發片；完整歷史／診斷、兩槽皆commissioned矩陣、共享output預設拒絕及另授例外契約、備份恢復、原生宿主／HACS與實機／正式發行仍保留。外部scheduler／cron／19排程匯入、8個滴灌腳本管理、Card raw IO／瀏覽器關泵timer始終排除。P4c 4/4、P3 5/5不重置；P5a修正後兩審均批准；joint-review repair 1/1與具名read-side revocation修補1/1已用，不自動新增修補批次。
