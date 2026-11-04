# P3b 品質修補2/2恢復交接 — 未批准

Worker在2026-11-04 14:03因HTTP429中斷，但QC1/QI1程式和5個永久native回歸已保存，focused8已綠。父端承接而非重做；配額錯誤不等於工作沒發生。

## 修補

- emergency acid/mix先capture immutable bindings、owns_io、operations，不在arm時eager resolve。各合法輸出獨立OFF，identity失效的replacement/foreign不可碰；無法證明OFF的owner保留unknown/fault與running，原R1明確owner仍保留。
- v4高pH observer採全局S，支援N/acid/mix commissioning；保留新鮮度、單位和finite條件，invalid ph重設計時，不做輸出或配置寫入。S4 reasons加入唯一ph_high_alarm；P1/v3契約不放寬。
- Parent發現第一次full的回歸：一般run identity丟失後fault變成output_identity_invalid，舊永久測試要求stop_unconfirmed。原因是本輪新增『保留任意先前fault』太廣。只保留明確emergency_stop；一般unknown/OFF失敗仍沿原stop_unconfirmed優先，不改任何舊assert。
- Parent整理新test import與format、control三元式format，沒有改測試assert。原先RED與interrupted-focused、第一次full294pass/1fail都保留。

## 真執行

`p3b-q-repair-2`每個唯一run子目錄保存raw.log/run.json/source-inventory與實際bytes、frozen pre/post、runner。父端接回四個run：

- recovered-final-native：child1，294 passed/1 failed，真fault優先序回歸（非環境問題）。
- recovered-fault-priority-green：child0，21 passed；原N identity/OFF/lateON、品質5與R1三case均真跑。
- recovered-final-native-green：child0，295 passed、5 upstream warnings，明設P3B_CARD_PYTHON，含原酸/mix六終態真shipped Chromium→native payload replay；295 distinct cases實載module hashes核對。
- recovered-original-quality-probes：child0，原QC1/QI1三assertions均PASS，原probe byte內容未弱化；runner只複製至新probes子目錄避免OUT覆寫歷史。
- Ruff check custom_components tests及format --check：child0，77 files formatted。Node12/browser33實消費JS/fixture未變，原coverage按不變輸入重用，不虛稱本輪直跑。

## 最終來源

- `custom_components/uninus_nutriculture/control.py`: `bd5d86eaae396af67fa8bffb7cd08a553436dbf58591b691f0d08ec72e3c51ca`
- `custom_components/uninus_nutriculture/nutrient.py`: `d1534e865356f8776297dcb0e8945a1e8b96bb3ba61da24ff0b9e8950a30e509`
- `custom_components/uninus_nutriculture/p3b_projection.py`: `42aaf07b8655aac85e7f1a05de986f8e8da6e6e055546674dc388050aef7e4c7`
- `tests/test_p3b_quality_repairs.py`: `61fdc942a68cf7581892dca94da317defa50e5d15b39f1d29f134a1f59b78098`

## 限制與關卡

修補預算仍2/2，這是同一未完成的最後輪恢復與其回歸修復，沒有第三輪。尚需獨立affected SPEC→品質重查，綠測試不是批准。原庫P3a及sealed source/evidence未改；無原HA/現場憑證/實機/外網/install/stage/commit/push/tag/deploy。P3c編排僅草案，Issue3不關。
