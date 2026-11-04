# P3b exact175 Q-successor 獨立 joint 品質／安全重查

## Verdict：APPROVED（本 exact candidate 的 joint P3b 品質／安全；非發布／部署批准）

**原 Q-C1、Q-I1a、Q-I1b 均已封閉，未發現仍需阻擋此 joint slice 的 Critical／Important。** 本輪先驗修後 SPEC PASS，再獨立讀完整可操作 backend／Card／demo 邊界、byte-copy 原三個失敗路徑的 assertions 並實跑，另選 fresh→stale→fresh／active 切換與 reasons 去重的新鄰界。不是把品質限成三行 diff，也不是以 SPEC 的27代替品質執行。原 `p3b-quality-review-1/REPORT.md` 的 REQUEST_CHANGES 原封保留，不追稱它曾批准。

本輪兩個原生 child 各 **27 PASS／16 PASS，皆 exit0、各5 upstream warnings、無skip**；audit已驗兩者 nodeid 不重疊。六個 acid/mix 終態另在首個 child 真跑 Chromium shipped Card→registered native request replay，屬上述27的一部分，不另加總。完整295只組合已核對的父端執行，不聲稱本輪重跑。另有一項**既存 CI format baseline failure**，詳§6，未隱藏為全綠。

## 1. Exact source／隔離

- Frozen root：`C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3b-review-q-successor`。
- MANIFEST SHA256：`a22f4988f6b26754a73a8185cd1e76bc1e6dacecb95f5e4a9f9fc458e1ded3c2`。
- `pre.json` 是175-entry hash map；`post.json.files` 與它及 manifest 全同，0 mismatch；physical inventory 176檔含 MANIFEST，無額外／缺失。兩種 receipt 結構不同，不假稱整份 JSON 字節相同。
- 對 R1 的完整 inventory 差異只含三個舊 production modules：control.py、nutrient.py、p3b_projection.py；新增handoff／progress／永久5-case test。所有舊 tests/assertions、契約、Card／parser／demo raw bytes 不變。
- control.py SHA `bd5d86eaae396af67fa8bffb7cd08a553436dbf58591b691f0d08ec72e3c51ca`；nutrient.py SHA `d1534e865356f8776297dcb0e8945a1e8b96bb3ba61da24ff0b9e8950a30e509`；projection SHA `42aaf07b8655aac85e7f1a05de986f8e8da6e6e055546674dc388050aef7e4c7`。
- backend 原 venv 僅為 interpreter／HA SDK。兩 child cwd、config、PYTHONPATH、原tests都在 frozen candidate；scratch probes／basetemp 都在本 OUT。逐case actual imported modules 的真 path/hash 分別27／16筆，皆 candidate 或 owned fixture path 且與 manifest 相符；486／288個實際fixture-copy Python files 亦逐一相符。

## 2. 原品質 blockers 的實際封閉

### Q-C1：invalid idle acid 不再截斷其他 emergency OFF

原 `test_quality_boundary.py` 原字節副本、原 assertions 全 PASS，SHA `12886201f4e5ae3677144d3d5cb4b1a472872ed20608b7cf78ca4b789008caf9`。

真 Options commission N／acid／mix／refill，四個不同Registry outputs外部ON；acid unique_id變更後，registered native emergency button 回傳無error。**N／circulation／refill 全OFF；acid replacement及foreign仍ON且零OFF**。acid owner owns_io=true、aggregate running=true、fault與持久 latch=emergency_stop、master=false；bindings及settings_revision不變。證據 `emergency-identity.json` 在fixture-only teardown前寫入，teardown OFF不算產品 closure。

讀碼確認 `control.py:521–554` 先 capture 各 owner bindings／operations／owns_io，無 eager resolve；`nutrient_dispatch:251` 逐role解析身份，cleanup gather隔離一個輸出的失敗，不觸 replacement。原 R1 的 N owner仍明確是 nutrient_stage，無stage dispatch不依 execution_stage。原三個 held-ACK／Context／pending ownership cases本輪全PASS；永久invalid acid／circulation兩案亦PASS。這不是允許unknown冒充已停。

`nutrient.py:508–511` 只為明確emergency_stop保留fault；一般run identity loss／OFF failure仍優先stop_unconfirmed。原完整N I/O檔本輪PASS，包括原 `test_removed_identity_never_sends_off_to_reused_foreign_name` 的既有fault assert。未改assert來掩蓋父端第一次full失敗。

### Q-I1a：acid-only 高pH延時告警

原 `test_acid_only_global_high_ph_alarm` PASS：無N binding，合法新鮮pH=7.0，S延時過後flag=true，options不變、owner idle、零硬體call。v4 observer讀唯一global safety_parameters，N／acid／mix任一 commissioned可觀察健康pH，不要求EC／level健康；finite／unit／last_reported freshness／tank.active仍保留。只 publish，不自動ON、不全局STOP。

### Q-I1b：真正S4 native Sensor不再漏reason

原 `test_projection_boundary_v2.py` byte-exact副本SHA `31452f1a4ad2666a00d8ec9e305ce183d69383135257d7603d2fb2f0a1151caa`，原assertions PASS。真N commissioning加酸草稿升v4後，先驗observer active，再驗native control Sensor schema4 reasons含ph_high_alarm；零I/O、options不變。原有harness TypeError的v1未採用也未改寫。

`p3b_projection.py:53–57` 以base reasons加active告警並去重，沒有改schema/parser或降級v3。永久acid-only／N升v4／mix-only五案全PASS；mix-only在EC及level unknown仍可觀察健康pH，但並非因此允許無level啟動standalone。

## 3. 品質獨立新鄰界：告警生命週期與去重

本輪新寫 `test_alarm_lifecycle.py`，不是SPEC的invalid N/reset鄰界。使用真Options、registered Sensor及原observer，僅明示domain clock／UTC freshness seam，按順序驗：

1. fresh high開始timer，延時後active；重複觀察仍只有一個ph_high_alarm。
2. 將UTC超過max_age後，stale立即清timer及native reason。
3. fresh recovery重新開始完整delay，不沿用舊active時間；延時後再active。
4. tank inactive清timer／reason，active恢復重新計時。
5. pH等於threshold不算high並清timer。

九次native觀察均PASS，options前後完全相同、無fault／running、兩組fixture hardware calls均空；`alarm-lifecycle.json` 保存全部值。這只證受控生命週期，不宣稱自然等待600秒、任意事件排列或實機告警送達。

## 4. 整個 joint slice 的品質／安全判讀

| 邊界 | 本輪獨立判讀與根據 |
|---|---|
| 酸／mix兩個native入口 | 額外mainline child直接跑原test_p3b_native、test_p3b_mix、test_p3b_safety：16PASS。真Options save/reopen、Enable零I/O、start_flow及flow_run各入口；酸中點立即OFF→必要mix→fresh pH完成，EC repaint不替代pH新樣本；standalone只依level保護、缺pH/EC不阻、bounded OFF。 |
| 原生急性／late I/O | mainline直接驗emergency、正常STOP、invalid source、Boolean sample、low level、danger pH/EC、late ON、reset零輸出。首child另驗N I/O與R1 held-OFF。讀完整Controller／NutrientStage／MixStage：ON前及ACK後auth／identity重驗、唯一dispatcher、pending union、normal先劑泵OFF再釋放循環；acute fault concurrent closure、不將必要mix凌駕故障。 |
| deadline／lease／重啟 | 完整讀dose reservation、shared lease、首次未結清circ dispatch的C−F絕對時限、stage deadline、cleanup及shutdown。既有hot tightening／same-run lease與restart/unload等由已核對full295及先前whole-slice品質讀碼結論組合，非宣稱本輪再跑所有deadline cases。declared cutoff不是物理認證。 |
| global S／null migration／writer | 完整讀config_flow、control_settings、dosing/p3b_settings、Tank.write_settings、services及Number：sentinel不混null；未commission map保持null但保留內部草稿；v4 S單權威、N13鏡像；meaningful delta才升版；全組驗證、同Tank.lock、CAS、queued重驗admin/active/runtime/Registry，一次update與publish。原十Number ID／單位／ACL不改，舊writer拒v4本輪直跑PASS。沒有發現新增可達半套mutation或越權反例。 |
| schema4／終態／native targets | 讀Sensor及projection；accepted stage結果由cleanup結算，未知output明示unknown，targets省略缺失／disabled映射。首child酸/mix各aborted/fault/completed六capture，真shipped Chromium消費，再把UI Enable／Apply requests交回native services，零多餘硬體calls；每receipt page_errors=[]、shipped hash及原native capture hash實際核對。 |
| Card／demo | 完整讀shipped 473行及離線demo：strict S4 keys／null／N-S mirror、Number子集、latest validated target、draft CAS、revision/全組讀回、Cancel不寫、remount/promise epoch、per-target flight隔離；外部值以textContent，沒有innerHTML注入或隱藏外網call。demo明示memory-only，不扮實機控制。既有pending/remount鄰界沿前SPEC與原品質結論及不變bytes組合，不把本輪六終態當全部UI race覆蓋。 |
| 靜態安全 | `static-scan.json` 掃所有production Python、shipped Card、demo的shell/eval/deserialization、credential assignment、HTML/network patterns，0 matches；配合上述實際權限／身份／故障碼讀碼，不把pattern silence等同安全證明。 |

尚留非blocking維護項：Card editor/customCards說明仍偏P1/P2，S4部分長行與Q/S tuple位置依賴降低維護性。沿原Minor，不為此引入大重構。

## 5. 組合證據的實際範圍

- 修後SPEC REPORT／audit／native.log三hash逐一讀回核對：`ce6153ac94494ade16087dc4e50870a62a190c6d2424557eac3cb5d3df275140`／`c47fe452bbf13f9b0d8ddc5f723d7810e9edd5b259ffb312d731d7fba103f4f0`／`001e9ac6e4c848c7665d4816c544b0c1accd4e52ebae61c9ecf307c668ebcde2`。SPEC PASS本身不是品質批准。
- 獨立讀回父端`p3b-q-repair-2/recovered-final-native-green`完整295PASS／5warnings／child0；run SHA `8cdb71317532ea6f795c93bd8c11fb275bdf8d2608531120699ff5af17cd6bba`，raw SHA `1adb62bed8383c1977921f941d7ca449d1b4a09b6253a5b5f6eed11ddf5eb925`。295 distinct cases皆有actual loaded modules，記錄hash逐個符合current candidate；235 archived raw snapshot files皆符合其inventory，pre/post不變。
- broad archive不是exact175全同：163項與current inventory相同，其中107個production/test/tool/config/shipped inputs已核；72 mismatch限docs／progress／歷史reviews/test-results等，逐項列audit.json，不把235冒稱current全同。六個未byte-archive inputs列`unarchived-unchanged.json`，只證R1/current不變。
- Node12／browser33沿前SPEC/原品質的actual-consumed equivalence結論作背景；本輪沒跑、不另稱新批准過的全部broad inputs。舊browser probe/log hash另核，Card等raw不變。本輪27、16、full295、SPEC27、Node12/browser33有重疊或不同邊界，不相加成總覆蓋數。

## 6. 命令、raw handles、誠實失敗

所有輸出只在 `C:/Users/ivanl/.hermes/cache/scratch/p3b-quality-q-recheck`。

- `native-run.json`、`mainline/native-run.json` 保存完整argv／cwd／env／child exit／elapsed／log hash；runner實際以backend SDK `python.exe -B -m pytest -c <candidate>/uninus-nutriculture/pyproject.toml -p no:cacheprovider -p conftest --basetemp <OUT>/... -vv -s <exact probes/tests>`，明設candidate PYTHONPATH、P3B_CARD_PYTHON、CHROMIUM_EXECUTABLE。首child35.21s，mainline12.27s。
- 首child native.log SHA `8025b7aa3579d7c5d3407bffacc3c0d7b2d3950bf0bbab0e92e3b368c02e6838`；mainline log SHA `d381f2171fac2b0845878acf6f64057563916f88017acd29d02c460d3f82659d`。
- `audit_review.py`真執行exit0，raw在audit-run.log／audit-run.json；audit.json SHA `9e14e08c9cb4f0b060c087d5b238a650cbd83f01d0cdd3715d0b0d7431d495c0`。初版audit已保留audit-initial.py/json，未以新tests覆寫它的結論。
- 照讀到的CI scope執行Ruff：`check --no-cache custom_components tests tools/evidence.py` exit0；`format --check --no-cache`同scope **exit1**，77檔已format，僅`tools/evidence.py:57`既存source_after長行不合格式。R1/current該檔及pyproject原字節hash全同；再對唯讀R1同檔及相同config執行baseline，真exit1且同診斷。見format.log、format-baseline.log及各run JSON。此為原本CI-format技術債，不是本修補新增失敗；不改source、不假稱CI全綠。77個production/tests format乾淨；沒有跑compileall以免寫候選pycache。
- 最初docs lookup少backend子目錄造成唯讀MISSING，隨即按manifest定位讀到兩份要求docs。不是產品fail。所有實際test child皆exit0；本輪沒有pytest/verifier失敗被抹除。新增format失敗及baseline原始log完整保存。

## 7. 批准限制與交付

批准的是此manifest限定的**joint P3b酸／standalone mix／global S／null migration／S4／Card／demo／安全outputs**；不是P3c或所有排列的完整證明。無真HA／現場認證／實機／外網、無live browser bridge、無實機cutoff或所有provider保證；時鐘seam僅證邏輯。未重跑完整295、CI、Node12/browser33；現有CI-format baseline failure仍需發佈流程自行處置。

只有本OUT新增probes／runner／fixtures／raw logs／audit／report／FINAL；未改候選175、原兩庫、舊evidence、歷史REQUEST_CHANGES或profile skills，未執行一次性edit.py、安裝、stage／commit／push／tag／release／部署、未第三輪修補。修補預算維持2/2。

P3a原庫已交付不重做；四stage可編順序／合法重疊／relative／weekday／preview仍屬P3c待做，Issue3保持OPEN。父端可採本exact175的品質APPROVED與獨立SPEC PASS組合，但本報告不授權發布或部署。
