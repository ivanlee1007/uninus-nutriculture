# P3b 實作交接（隔離；未批准）

## 結果與gate
完整主線縱切已可呼叫：酸-only原生 Options 持久保存/reopen/Enable零I/O，start_flow與flow_run皆循環ON確認→酸pulse→Decimal中點5.6立即OFF→必要postmix→獨立新pH stable→completed。Standalone mix-only由同native Options/Enable/start接通；未知pH/EC不阻合法混合，僅循環輸出有界ON→OFF。

這不是完整P3b驗收或安全批准。P3a Q1/SPEC/品質原阻擋仍有效，已耗2/2預算未重置；無stage/commit/push/tag/release、無token/現場HA/實機。

## 實作接口
- Options新增acid_output、acid_* Q/sample/commission保護、mix_*、共用circulation protection；有意義delta才升v4。含N-only自動注入False/工程預設不升級的native回歸。
- Tank.write_settings擴acid/mix/safety；新apply_control_settings_v4 exact payload/CAS/native auth lock；舊writer對v4拒絕；未commission map snapshot=null保留draft，S全局權威、N鏡像。
- NutrientStage加小型role/source/direction policy（酸=-pH正規化），不複製engine；原Controller唯一physical dispatcher，Controller acquire/release lease record；MixStage復用owned-I/O/cleanup/stop。
- 原生ControlStatus schema4與Registry Number子集；酸/mix Enable映射；stage.result accepted reset、cleanup終態和舊N生命週期回歸保留。
- Card新增v4 validator/native controls/酸Q、mix設定與單一S、CAS草稿Apply/Cancel/後端讀回；原v1/v2/v3驗證未放寬。native snapshot→shipped Chromium→emit requests→native service replay已跑通。

## 真執行證據
- backend docs/evidence/p3b-01-options-red：首永久native Options RED（exit1，酸Q未保存）。
- p3b-05-acid-native：3 passed；p3b-10-mix-green：26 passed（重疊focused，不能相加）。
- p3b-06-safety-wire-red / p3b-07-safety-wire：保留新安全/遷移行為RED與GREEN。
- p3b-11-native-wire-red：idle emergency酸輸出未關RED；p3b-12-native-bridge保留browser成功但idle emergency未修好結果。
- p3b-14-final-native：**266 passed / 1 failed / exit1**。唯一失敗是tests/test_boundaries.py::test_metadata_and_translations的舊P3a exact Options翻譯key集合，不能接受新增契約欄位。未改/弱化此舊測試；交父端決定允許擴充期望後重驗，不假稱全綠。
- Card p3b-07-card：11 Node case全過；p3b-10-final-browser：31 browser case全過，Chromium156.0.8078.4。先前失敗全部raw log保留；p3b-09-full-browser缺BROWSER_EVIDENCE_DIR並有舊v2 rows回歸，已修row移除且新目錄重跑。
- 假硬體SDK測試使用原backend venv（唯讀借用），測試cwd/fixture均隔離；browser使用原Card venv及指定Chromium。early backend evidence有pre-run source bytes/hash/child exit/raw log；後期另有source_after。Card evidence均有前後hash。

## 尚未完成／不得過度宣稱
1. 全P3b安全矩陣仍不完整：酸late ON apply/OFF失敗+身份替換、授權撤銷、跨stage pending ownership、hot-tightening/cutoff細邊界及真HA STOP/unload尚須針對新role永久覆蓋；不能用舊N綠推定已覆蓋酸/mix全部。
2. mix restart identity/externally-ON admission/reset source策略需joint SPEC再核；多commission emergency目前逐新stage cleanup，並非所有role concurrently OFF的新完整保證。
3. Tank新增參數仍採None=preserve，尚未完成契約要求的獨立sentinel區分未傳/null；service邊界已拒commission map不合法null，但Python writer內部完整sentinel契約仍待接。
4. schema4 Card驗證涵蓋各map exact、types、Number subset/identity和state enums，但outer integration-owned exact-key拒絕/所有參數同SPECS範圍檢驗尚未全補；需獨立SPEC檢查。
5. Card新v4靜態demo尚未加入；現有v1/v2/v3 demo回歸通過。新酸/mix中文labels目前由literal欄名轉空白，需正式繁中措辭；services YAML新增尚需native selector文件校驗。
6. 尚未替新v4做完整終態aborted/fault/completed→masterOFF/reset/settings→shipped UI全矩陣；已完成native酸settings/master零I/O snapshot橋與舊N全部終態回歸。
7. P3c四stage可編順序、重疊、relative、星期preview完整需求保留；沒有scheduler/stage_link/recipes/IRR許可。

## 文件與hash
精確changed source/test/tool清單及SHA：P3B_IMPLEMENTATION_SOURCES.json。所有新增工具僅隔離repo；p3b_*_edit.py是本次一次性編輯紀錄，非可重複安裝器。所有失敗run不刪除。
只讀檢查：P3B_READONLY_RECEIPTS.json。凍結successor源138/138匹配BASELINE、MANIFEST SHA匹配。原庫138已讀，134匹配凍結baseline，4個差異為backend .gitattributes/README/P3A_LOCAL_CHECKPOINT、Card README；本worker沒有寫原庫，不能把凍結baseline當成原庫任務開始時snapshot；00:30前後late-check stability另存，不冒稱完整原庫before/after證明。第二審查snapshot及既有evidence未有完整before receipt，仍需父端獨立核對。

## 指令（從隔離backend根）
```text
D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe tools/evidence.py <全新p3b-label> tests -q
```
bridge需P3B_CARD_PYTHON指向原Card venv；CHROMIUM_EXECUTABLE用指定1248 chrome.exe。Card根 tools/p3b_evidence.py <新label> node tests/test_contract.cjs；browser以Card venv -m unittest discover -s tests -p test_browser.py -v，BROWSER_EVIDENCE_DIR必設新label/browser。
