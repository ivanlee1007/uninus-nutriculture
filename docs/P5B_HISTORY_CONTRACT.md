# P5b 同槽 pH／EC／液位歷史契約

狀態：P5b功能、真Recorder整合與獨立SPEC／品質兩審已完成，B-01已關閉，唯一修補批次1/1已用。來源出版與hosted CI依本提交的實際結果核驗，不以本機成功代替。P5a既有軟體交付不重開；本片不等於完整P5。

## 使用者能力

選槽 → 展開「歷史」 → 選1／6／24小時 → 分別查看pH、EC與液位曲線 → 觸控／滑鼠或鍵盤選取時間點、閱讀數值與可及資料表 → 明確重新整理。預設收合、不自動查詢、不輪詢；普通即時數值更新不搶焦點或重建操作控制。

## 唯一資料路徑

- 只從目前選槽status.attributes.source_entities的ph／ec／level取得來源；不另填ID、不猜名稱、不查全部Entities。
- 只經目前登入者的hass.callWS呼叫Core `history/history_during_period`；不建立integration資料庫或新控制API。
- 本片支持與驗收基準為Core2026.10.4。請求明確設定start_time／end_time為有時區UTC ISO、include_start_time_state=true、significant_changes_only=false、minimal_response=false、no_attributes=false。
- 讀取真Recorder資料，權限由原生READ過濾。回應為來源ID→compressed rows：s字串、a屬性、lu為Unix秒、lc可選；秒只轉顯示毫秒一次。只有真隔離Core與shipping Card對接通過才可宣稱native兼容。

## 顯示真值與有界性

- 三種指標分圖；支持pH無單位／pH、EC mS/cm、液位m。逐筆依真屬性檢查單位，不混接異單位；不改既有控制或Number的單位處理。
- unknown／unavailable／非有限值是缺口，不補零、不借用即時讀值。不把區間起點沿用狀態稱為新採樣；單點、平線、空結果均如實呈現。
- 使用HA設定時區並明示必要fallback與偏移；排序、同時刻重複、窗外資料與單位變動須有確定規則。
- 查詢逾時20秒；最多每來源10000筆、合計30000筆；每指標至多240顯示點。正常有界6／24小時密集資料採確定性代表抽樣，保留首尾、各連續有效段極值、缺口邊界及缺口單位變化；不新增或插值測量值，不宣稱保留所有轉折。分別標示原始／正規化／顯示筆數與是否抽樣。若必要邊界本身超過240點而無法安全表示，只明確拒絕該指標，其他可讀指標照常顯示；輸入安全上限不變。
- 空結果可能來自沒有紀錄、排除、清除或READ過濾，只稱「無可讀歷史資料」。權限拒絕、未知命令、不支援、離線、傳輸與格式錯誤分別降級；不提權或另找私有路徑。
- 320px與桌面、明暗主題可用；圖表支持方向鍵／Home／End與指標點選，提供表格替代，不建立大量Tab停留點。

## 生命週期與私密性

綁定status entity、實際公開的entry／epoch、來源映射／單位、登入者ID與primitive角色／啟用狀態、connection／connected、callWS、掛載／設定及window／request世代。換槽、重綁、移除、降權、登出、離線、換transport或卸載同步清舊圖與快取；晚到success、error與timer不得復活舊資料或污染新notice。等價設定與普通telemetry不觸發新查詢。不持久保存raw history。

## 驗收與邊界

真隔離Recorder ingestion／History／Auth註冊WS → shipping Card；同名槽使用各自三個來源，核對真數值／時間／單位、1／6／24小時與partial／full READ過濾。槽的commissioning／就緒狀態另列，不冒稱兩槽完整流程驗收。補充缺口、錯誤及晚到競態、必要受影響回歸，再整合SPEC→獨立品質／安全。

歷史純展示，不影響品質、灌溉許可或致動。來源改名、重用或重綁後，現在的映射不能證明全部舊紀錄屬同一實體槽；Recorder保留／排除亦限制資料可用性。不增加接線歷史追溯後端。

保留完整P5十二組inventory；本片不關閉stage／output／permit時間軸、進階runtime、選配水溫通訊、多槽完整commissioning／shared-output、備份還原、原生宿主／HACS及另授實機／發行。原HA不連線／不讀憑證／不部署，既有產品後端／schema不改，不加入scheduler、raw IO或瀏覽器關泵timer；不建立tag/release。
