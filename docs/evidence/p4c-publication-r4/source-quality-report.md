# R4 whole source-quality／security：APPROVED

本裁定為完整52 path的組合式品質／安全批准，不是只給affected PASS。候選F SHA256 `c8432ecf9d9bdec0d091890af9f90466b4edf68e60f69ca0893e1723daa42ba3`。正式P4b基線：Backend `48b148c05de50dd976952462d50c86871acffc5c`、Card `14dad5f2bed79baab52001bf47a8be80ffc5ff35`。

## 完整覆蓋與承接
- 原 `p4c-whole-quality-r3/COVERAGE.json` 全51 path已REVIEWED／zero unreviewed，原209封存artifact逐hash驗證；其REPORT、FINDINGS與REQUEST_CHANGES原件保持不變。原17SPEC與歷史失敗不改名。
- 本輪程式核算R3→R4：6658 source bytes相同、dispatcher一改、永久test一增、無移除。原51之50檔精確hash承接，dispatcher保留原全文審查背景但以本輪全文／diff與依賴分析取代舊配額結論，再全文審新增test。合計52＝27 changed＋25 added，18 source／16 test／18 docs，zero unreviewed；見COVERAGE.json與INVENTORY_DELTA.json。
- 承接既有results closure／public DTO allowlist、registered API每await authority／CAS、Options隱私與卸載拒絕、NativeStore真I/O drain與reconcile、Card DOM安全／late owner fences、唯一P3 mix prestart guard，以及全部未變測試／文件。無變動的已審內容不是重新執行證明。
- 本輪亦核R4 SPEC封存711 artifact全部hash正確，17格wholeSPEC APPROVED與parent receipt相符；其中13 native unique及98 focused只作已驗證背景，不冒稱本輪重跑。舊546不是R4 byte的完整回歸；未輪詢、未等待另一worker。

## Important P4C-QUALITY-01：對此R4完整候選 CLOSED
原反例逐byte複製，不改永久assert：真opt-in NotifyEntity held → 真pH恢復 → 同entry Core async_reload → 新epoch真pH danger。新結果old closed／old task仍pending，global_pending=1、provider_invocations=1、fresh native未建立、release=false、零actuator calls。原R3失敗及two pending事實不改寫。

源碼責任邊界：
1. `entry_slots`為同一hass.data shared map，stable entry ID→actual native task；每次setup/runtime/epoch換新不遺忘held owner。不是永久空history；map只含未釋放reservation，長度受global2約束。
2. `run` L226–247 check／create eager_start=False／global set add／entry map reserve間沒有await，同loop不會讓兩個worker搶同entry。entry1與global2雙判斷，不把queue16或TTL60改小來掩蓋問題。
3. `handoff` L165–200另持真正provider child，shield迴圈承受外層cancel，直到child.done並取result；cancel請求、timeout、close、reload、新epoch都不是settled。typed NotifyEntity adapter identity/fence與SDK async_send_message之executor await邊界已檢視；選中provider自己違反native contract、提早背景return或堵塞event loop仍是既有信任邊界，不宣稱能取消第三方實際寄送。
4. 只有task真正完成後的callback discard global；entry map必須`is t`才delete，舊owner callback不清新owner。callback取exception，exception/cancel的terminal均釋放；不回寫新owner ledger。舊task可能比child晚一個loop tick清除，是保守延後、不是提早釋放。
5. `close`只清queue並cancel worker；原unload在通知close後走control.shutdown/OFF，不等通知slot。既有policy/epoch/TTL驗證在reservation前，fault episode/cooldown/去重與成功handoff語意完全未變。正常同候選碼entry reload為本範圍，不要求未部署R3與R4熱混版migration。

## 本輪實際小run：5 unique PASS，child exit0
`native/command.json`、raw.log、junit.xml、exit.json：5.68s pytest（另有wrapper wall time）。
- 原quality同entry reload反例1。
- 獨立新probe2：held provider在原生reload後對舊outer task連續3次cancel，直到release仍保有同entry/global reservation；provider正常return及真正exception各一。replacement關閉後release/drain，最終map／global空，closed DTO不變，無actuator calls。此probe只替換測試sink方法以觀察原生能力回傳／失敗，不替換產品dispatcher或shield。
- 永久test精確selector2：settlement後新owner可交付、old callback identity保護／empty-map prune；另一entry可用第二global slot。old callback人工重播兩次是防禦邊界試驗，**不是聲稱Core天然呼叫兩次callback**。
- 五份真Core fixture copytree各36 `.py`／41 total均逐檔hash符合R4；兩個獨立鄰例記錄actual dispatcher import path直接來自凍結R4及精確SHA。未誤要求import一定來自fixture copy。SDK notify/storage hash與原review seam吻合；未改runtime、SDK或安裝套件。
- 精確dispatcher新增行＋新增永久test全文安全pattern scan無命中；另人工語義檢查無新增secret、任意外部IO、注入、權限放寬或public target泄露。pattern silence本身不作安全證明。Ruff `check --no-cache`只對兩個delta檔exit0，不聲稱本輪fullstatic已過。

## 完整性與資格
PRE.json／POST.json：6660 source＋5 root metadata＝6665，完整集合與F逐hash吻合；5份metadata均有獨立prehash及posthash，不沿用前review只有metadata post的缺口。所有本輪overlay、copies、captures、log／report只在owned E。來源碼／永久test／文件／F／Q／SPEC／SDK／正式repo均未寫。

本輪無產品或harness失敗；pytest有5項SDK dependency deprecation warnings。證據verifier使用本次owned pytest產生的XML，非外部不可信XML。歷史timeout／harness／invalidRED／唯讀等資格保持原Q與SPEC報告，未重跑舊finalizer或洗掉失敗。

## 不包含的批准
Critical=0，未閉Important=0；新security問題=0。P4C-QUALITY-M01仍是非阻擋publication-only successor，舊phase/status字句在歷史與pending出版範圍內，未發現新規範矛盾；不授產品修碼許可。P4c4/4與P3closed5/5不重置。

**R4 final553/fullstatic/currentCoreCard join由parent另核，本review未驗該gate，亦不宣稱出版完成。** 未重跑全17SPEC、全suite、bridge、stress或frontend。未變frontend31 input hash的unit14／DOM91只能承接既有證據，不是本輪新run。tag／release／部署／現場HA／auth與兩槽硬體P5資格均無批准。完整報告是source-quality/security裁定，與final gate及publication授權分離。
