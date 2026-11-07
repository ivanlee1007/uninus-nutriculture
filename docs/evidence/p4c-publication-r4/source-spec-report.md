# R4 wholeSPEC：APPROVED（非 wholequality／出版批准）

- 17格明列於 WHOLE_SPEC_17_MAP.json：16格承接，N06以本輪原生反例及相鄰檢查重新裁定 PASS。舊Q REQUEST_CHANGES與舊17PASS原件均未改寫。
- 原Q probe2同一測試逐byte複製重跑：真sensor pH3.7 → held NotifyEntity → pH恢復 → Core async_reload同entry → 新epoch再pH3.7。舊closed但provider仍pending；R4 global_pending=1/provider_invocations=1、新native未建立，無actuator calls。不是owner手換、假DTO或外部送達證明。
- native主run 13 unique PASS／exit0：原獨立反例1、R4永久7、獨立相鄰2、既有queued policy fence3。相鄰額外採native sink真exception及CancelledError settlement；held期間真privateWS reconcile不清reservation、不寫盤；settlement後fresh queued notice交付，重複old callback不能刪new owner，最終entry map空。另一entry可用第二global slot、連續reload、disable/epoch/TTL取消均PASS。
- 額外provenance小run僅重複2個已計case（exit0），不加總unique。實際import路徑及hash見 provenance/imports.json；15份Core fixture copy各41檔含JSON/YAML逐byte符合R4。SDK實取Core2026.10.4／Python3.14.5；非換runtime證明。
- R4完整6660declared＋5含sha root metadata＝6665檔pre/post與F吻合；F SHA c8432ecf9d9bdec0d091890af9f90466b4edf68e60f69ca0893e1723daa42ba3。R3→R4只dispatcher產品一改、新永久test一增；pre/post亦封閉Q/Qspec及父端receipt，未寫舊證據。
- 源碼檢查§6/§8.4：shared hass.data entry_id→actual native task；check/reserve同loop無await，global2保留；只有actual settlement callback清global，entry identity一致才刪map；close/cancel/timeout/reload不先清責任，無空歷史entry key。queue/policy/epoch/TTL判斷仍在reservation之前；沒有改Store、public事件、TTL/cooldown或控制語意。
- 明確承接Qspec其餘16格及其限制：R01–R06、N01–N05、N07–N09、A01、C01；含已關閉Q2/Q3不同fault通知、mix prestart/emergency、Options privacy／卸載控制拒絕、C01真native held role-only Card fence。理由為完整delta與未變bytes，不冒稱重跑真Card bridge或17格矩陣。歷史資格引用Q REPORT及PARENT_FINAL546_AND_QUALITY_QUOTA_BLOCKER_VERIFIED.json；舊546/81與trueCoreCard join436非R4完整回歸。
- 新Important發現：無。本輪無產品修碼、安裝、SDK修改、git／部署／現場HA／auth動作。P4c4/4與P3closed5/5不重置。R4 full553及獨立wholequality仍待父端另過。

## 資格／問題
- 一次唯讀conftest discovery查到根目錄不存在；其後讀tests/conftest.py並用真native selector載入。owned finalizer首次錯假設import必來自runtime copy而exit1；實際sys.modules直接載入凍結R4 source，hash吻合，fixture copies亦逐byte吻合。只修owned來源斷言，原child logs未重跑／覆寫。所有pytest child實跑均exit0；5項SDK dependency deprecation warnings非FAIL。見HARNESS_QUALIFICATIONS.json。
- parent曾封存quality209 artifacts，本輪自身完整讀取Q時為210檔、Qspec1058檔（含既有metadata）；只宣稱本輪精確pre/post集合不變，不把不同封存口徑混成同一總數。
- JUnit解析僅消費本輪owned pytest生成XML，無外部不可信輸入。所有probe/runtime/log/snapshot只寫本E。
