> 現行狀態（2026-11-07）：P4b正式交付與exact-HEAD hosted CI／產物核對已完成。P4c R4來源已通過SPEC及獨立品質兩審，本機完整553 cases／82 modules（144／116／137／156）與真Core／shipped Card join已完成；目前僅準備出版successor，尚未push，未驗新exact-HEAD hosted CI。P4c初始2輪＋explicit Options卸載1輪＋explicit quota1輪＝4/4；P3歷史4輪＋explicit mix1輪＝5/5，皆結案、不重置。完整P4／P5、實機commissioning及HACS實裝未完成，未tag／release／部署。內嵌0.2.0保留既有封裝，不代表功能階段。


> 導航優先序：FUNCTIONAL_PARITY_REVIEW.md是舊commit的歷史F/D盤點，不代表目前沒有控制能力或所有D/R仍未決；不改寫其原文。P3C_FLOW_CONTRACT.md頂部提案語句屬來源歷史，現行以其§7已採納補充及本輪交付狀態為準，不再次凍結或重審。
# UNiNUS Nutriculture

## 目前開發狀態與完整目標

**P3b 加酸／獨立攪拌／S4：來源已接通並完成兩審；P3c 編排來源已接通並完成兩審。**

P3a 工程來源已交付，兩審與功能來源 CI 已完成，見 [P3A_PUBLICATION.md](docs/P3A_PUBLICATION.md)。本倉 P3b 加酸、獨立攪拌與 S4/schema4 已接通唯一後端並完成獨立規格及品質兩審；已審來源的 295 項 native 假硬體測試不代表真 HA／HACS／實機驗收。P3c 四階段可編順序／合法重疊／相對延遲與條件／星期及七日有效流程預覽已接通並完成兩審，完整 P3 的 Issue #3 保持 OPEN；本文件不更新遠端 Issue。P3b 來源交付不必等待完整 P3。P3b 遠端 CI 只以最終 commit 的實際 Actions 為準，不以本機 gate 代替；沒有內建 scheduler 或獨立 stage_link，未建立 tag/release 或部署。

**P3a 加養工程來源已推送，獨立規格／品質與功能來源的遠端 CI 均通過；未建立正式發行或部署實機。** 詳見 [P3A_PUBLICATION.md](docs/P3A_PUBLICATION.md)。

- 本機已接通原生 Options、整組參數／星期 CAS、schema3 Card，以及必要循環→加養脈衝→中點停泵→混合→新樣本穩定確認。設定保存不致動；原生 Switch 與外部 `start_flow` 共用後端。
- 隔離原生回歸、實際 Card 的設定與加養跨層已執行；都是假硬體，不是原 HA／HACS／實機驗收。精確來源與剩餘關卡見[本機 checkpoint](docs/P3A_LOCAL_CHECKPOINT.json)及[加養接手紀錄](docs/P3A_REVIEW_CANDIDATE.md)。
- **P3b 加酸與獨立攪拌已接通；P3c 四階段可編順序／合法重疊／相對延遲與條件／星期及七日真正預覽亦已提供。** P3a 只是開發順序，不代表整個 P3，也不能把核心編排延至 P5。
- P4a配方已交付；P4b品質/完成/許可已實作並兩審及本機隔離驗證。舊S1–S5 `ready_for_irrigation` 固定false，新quality_v1與唯讀permit有效時可True；P4c通知/外部結果R4來源已兩審及本機完整gate，尚未出版。沒有內建排程器、獨立 stage_link 或瀏覽器關泵計時器。
- 已凍結的工程策略不再反覆要求使用者逐項決定；實際設備保護、最低液位與來源採樣能力仍由每槽 commissioning 明確確認。

目標對齊與有限後續順序見[GOAL_ALIGNMENT.md](docs/GOAL_ALIGNMENT.md)。下方 P2 段落是已發布基線的歷史範圍，不限制本倉 P3a／P3b 已提供的功能；現況以上方交付狀態為準。


## 已發布 P2 基線：隔離測試入口與限制（歷史範圍）

**P2補水候選已通過獨立SPEC與品質／安全審查；未部署原HA，不應直接接管實機。**完整結果與交付界線見[P2_ACCEPTANCE.md](docs/P2_ACCEPTANCE.md)。

- 後端原生Options明選已註冊補水輸出、commissioning確認、回饋期限及星期；保存/取消不致動。
- 先允許總開關與補水子開關，再用原生整輪Switch或`uninus_nutriculture.start_flow`請求一次補水；ON不會自行打開其他Enable。
- 新版Card選擇後端實際的**schema2控制狀態Sensor**，即可看見總/補水/整輪、急停/復歸；舊schema1監測Sensor仍無控制按鈕。不要使用來源pH/EC/液位Sensor作入口或猜測Entity ID。
- 高水位、正常停止、過期/無效來源、逾時及急停交由後端處理；未確認OFF不顯示假成功。運行中重複ON不重啟，重啟HA不續藥。
- 人類操作預設僅管理員；原生automation可使用內部Context。P2只有補水，養/酸/獨立混合不可啟動，也沒有流程編排UI或內建排程。
- Commissioning勾選不是韌體/斷線保護的軟體證明；HA當機/通訊失效時，一般Switch不保證會自停。只能識別已知Registry/平台uniqueId綁定，不能推測所有實體別名；部署前需另行確認設備端保護。
- 本機已驗證：backend151項、Card Node9項/真Chromium23項及shipped UI→真隔離HA handler→SwitchEntity假硬體。這不是原HA前台宿主、HACS安裝或物理驗收；最新CI只以對應commit的Actions為準。



Home Assistant自訂整合，網域`uninus_nutriculture`。**內嵌版本0.2.0保留既有封裝metadata，不代表目前只到P2：P1–P3與P4a／P4b軟體來源已交付；P4c結果／通知R4來源已兩審及本機完整gate、尚未出版。現行能力以本文件頂端狀態及共同規範為準，實機與HACS安裝未驗收。**

舊schema1 Sensor僅監測；另有schema2控制Sensor、總/階段/整輪Switch與急停/復歸。初始無綁定、總OFF，不會自動啟動；沒有MQTT客戶端或原站帳密。P1及P2的ready_for_irrigation都固定false。監測Sensor的shadow表示此介面不控制，不代表同槽控制器一定閒置。

## 安裝與設定

已在隔離的 **Home Assistant Core 2026.10.4 / Python 3.14.5** 執行原生測試。該 Core 套件要求 Python ≥ 3.14.2。Windows 僅作離線測試環境，不代表 HA 官方支援 Windows 正式部署；未接觸任何運作中的 HA。

1. 將本庫的 `custom_components/uninus_nutriculture` 完整複製到 HA 設定目錄的 `custom_components/` 下。
2. 在您自行管理的測試 HA 重新啟動後，到「設定 → 裝置與服務 → 新增整合」，搜尋 **UNiNUS Nutriculture**。
3. 輸入水槽名稱，選擇現有的 pH、EC、液位 `sensor` 實體，設定讀值最長有效時間。預設 300 秒，可設定整數 10–86400 秒。
4. 每個槽建立一個 config entry。身分以 HA 的穩定 `entry_id` 為準，名稱相同仍是不同槽，互不共用參數。
5. 到整合的「設定／選項」可更換三個來源與時效；更換來源會重新載入該 entry，保留參數與原生 registry 身分。

提供 `hacs.json` 作為自訂庫中繼資料；兩個 repository 已依使用者要求改為 Public，但**尚未執行實際 HACS 安裝驗收，未宣稱已在 HACS 預設清單上架**。目前文件提供手動安裝程序。沒有 release 或部署工作流程。

## 原生可編輯參數

十個整合擁有的 `number` 實體均為 `EntityCategory.CONFIG`、`NumberMode.BOX`，可在原生前端或透過 `number.set_value` 編輯，不是 `input_number` Helper 儲存紀錄。下表範圍是本 alpha 的參數限制，不是感測器量測規格或農藝建議。

| 參數 key | 預設 | 最小–最大 | 步進 | 單位 |
|---|---:|---:|---:|---|
| `level_low` | 2.25 | 0–10 | 0.01 | m |
| `level_high` | 2.4 | 0–10 | 0.01 | m |
| `ph_low` | 5.4 | 0–14 | 0.1 | 無 |
| `ph_high` | 5.8 | 0–14 | 0.1 | 無 |
| `ec_low` | 0.8 | 0–20 | 0.01 | mS/cm |
| `ec_high` | 0.9 | 0–20 | 0.01 | mS/cm |
| `refill_timeout` | 190 | 1–1440 | 1 | min |
| `ec_timeout` | 90 | 1–1440 | 1 | min |
| `ph_timeout` | 190 | 1–1440 | 1 | min |
| `mix_duration` | 10 | 1–1440 | 1 | min |

P1監測介面不啟動設備；P2補水控制會使用refill_timeout，本機 P3a 也使用 ec_timeout；P3b 已接通 ph_timeout／獨立 mix_duration 的後端執行。所有寫入均檢查有限數、界限、精確十進位步進及三組 `low < high`；不合格則整組參數與 options 保持不變。每槽共用鎖序列化寫入，並在取得鎖後重新確認 Number 的生命週期及 registry 擁有權。卸載後與排隊中的舊實體寫入會拒絕。

原生 HA 的服務 schema 可能先將布林轉成數字；本整合不覆寫全域服務 schema。自動化請傳數值而非布林。對整合內部保留型別的寫入邊界，布林會拒絕。

權威值儲存在 `ConfigEntry.options.parameters`。HA 的 `async_update_entry` **排程原生儲存**，不是已 fsync 的交易提交；突然斷電仍可能失去尚未寫入的變更。已驗證卸載／重載及原生正常關閉 final-write 後的新 Python 程序讀回，不宣稱 crash-durable。

## 來源、單位與時效

- pH：接受無單位（缺少 unit／`null`／空字串）或精確 `pH`。
- EC：只接受精確 `mS/cm`。`µS/cm`、`μS/cm`、`uS/cm`、S/m 等一律判為 invalid，**不會默認當成 mS/cm，也不自動換算**。
- 液位：只接受精確 `m`，其他單位不換算。需要換算時，請先在 HA 另建具有正確數值與單位的來源感測器。
- 三個讀值都必須落在包含上下界的品質區間內，才是 `within_range`。
- 缺少、刪除、unknown、unavailable、非數字、NaN、Infinity、單位不符、過期或未來時間戳讀值都為 `invalid`。
- 新鮮度讀取原生 `last_reported`，不是 `last_changed` 或 `last_updated`。相同值再次回報也會續期。來源事件立即更新，另每 5 秒重新檢查，故沒有新事件的卡住讀值也會在到期後最遲約 5 秒失效。
- 卸載會移除事件訂閱、共享監聽與週期計時器。HA registry 可能保留 unavailable placeholder；整合不再發佈活動狀態。

## 固定消費端契約（P1）

每槽一個 status `sensor`；以實體 registry 查找，不依賴示例名稱。狀態只有 `within_range`、`out_of_range`、`invalid`，invalid 優先於越界。屬性：

```yaml
schema_version: 1
mode: shadow
ready_for_irrigation: false
source_entities: {ph: sensor.ph, ec: sensor.ec, level: sensor.level}
parameter_entities: {}  # 執行時填入可用、屬於該 entry 的實際 number entity_id
parameters: {}          # 執行時固定包含上表十個數值 key
reasons: []
```

上述來源僅為無位址的示例 ID。`parameter_entities` 透過原生 registry 的 domain + platform + entry + unique ID 取得，**不拼湊名稱**。重新命名後會跟隨實際 ID；停用、刪除、缺少 state、unavailable、unknown、非有限數或非數字 state 的 Number 不會暴露可寫目標；健康 state 恢復後會重新發布同一實際 ID。消費端必須允許目標字典少於十個，不得自行猜測缺少的 entity ID。

`reasons` 最多三項，順序固定 pH → EC → level。每個來源只取一個穩定碼，優先序為 `{key}_missing`、`{key}_unit`、`{key}_invalid`、`{key}_stale`、`{key}_out_of_range`。不包含任意例外文字或來源機密。

## 完整產品範圍（P1–P3軟體已交付；P4a已實作並兩審）

| 階段 | 範圍 | 目前狀態 |
|---|---|---|
| P1 | 影子監測、原生來源選擇／選項、十個原生 Number、固定 status 契約 | 本 alpha 已實作與離線原生 Core 測試 |
| P2 | 總/四子開關、統一gate、外部整輪服務契約、補水安全骨架 | 補水候選已實作；native/瀏覽器/跨層測試通過，獨立審查已通過；發布/CI以對應commit為準，實機尚未驗收 |
| P3 | 四階段可配置順序/重疊/相對延遲與條件、每階段七日複選、最小階段列UI/預覽、加藥/混合/仲裁、原子群組參數 | P3a 群組 CAS、schema3 與加養已在本機接通，已完成兩審與功能來源 CI；P3b 酸／獨立混合已接通並完成兩審，P3c 可編流程已接通並完成兩審；P3c有限圖語意已凍結並交付；實機commissioning另列 |
| P4 | 配方、外部action/結果互通與通知、完成/品質/灌溉許可介面 | P4a已交付且exact-HEAD CI通過；P4b品質/完成/許可已實作並兩審及本機隔離驗證，來源與exact-HEAD hosted已驗證；P4c結果/通知R4來源已兩審及本機完整gate，尚未出版，不建排程器、不管理外部腳本 |
| P5 | 進階視覺化編輯器、手機/鍵盤、診斷/歷史、多槽產品體驗、release candidate | 待實作；P1 已有 entry 隔離，不等同完整多槽產品 |

本庫僅包含後端整合；[伴隨儲存庫 `uninus-nutriculture-card`](https://github.com/ivanlee1007/uninus-nutriculture-card) 已提供P1相容、P2補水與P3a/b/c加藥/混合/有限流程編輯預覽Card，不在本庫內。也可使用 HA 原生 Entities 卡片呈現 Numbers 與 status。P2已完成獨立審查，不代表HACS安裝或實機驗收。完整計畫仍以 `docs/DEVELOPMENT_PLAN.md` 為準。

## 控制規範與後續設計

- [總開關、四階段子開關與可配置流程](docs/CONTROL_SWITCHES.md)：P2骨架已實作，P3c 四階段已接通；舊schema1監測介面保留。
- [流程編排/UI、每階段星期與外部啟動研究](docs/FLOW_DESIGN_RESEARCH.md)：建議階段列＋開始條件/延遲＋並行組＋預覽；R01取消鏈結及R03實際開始前查星期已確認；新增整輪運行Switch，R04 已由 P2/P3a 契約凍結；P3c 有限圖語意已凍結。何時啟動整輪由外部排程/HA automation決定；星期僅為允許gate，混合/脈衝/安全期限仍由後端管理。
- [原系統與新規範功能差異盤點](docs/FUNCTIONAL_PARITY_REVIEW.md)：區分已實作、保留用途、刻意改善與待決策，作為後續驗收基準。

## 測試

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-test.txt
.venv/Scripts/python.exe tools/evidence.py local-check tests -v -s
```

Linux 改用 `.venv/bin/python`。`tools/evidence.py` 會建立新的不可覆蓋 evidence 標籤目錄、複製當時完整 source/tests、記錄 SHA-256、實際命令與退出碼。詳見 `docs/TESTING.md` 與 `docs/P1_HANDOFF.md`。CI 設定為 Ubuntu／Python 3.14；遠端驗證結果以本儲存庫 Actions 的對應 commit 為準，本機測試不等於遠端 CI 或正式站驗收。

## 共同開發規範

[DEVELOPMENT_SPEC.md](docs/DEVELOPMENT_SPEC.md)統整已確認結論、前後端責任、開關/流程/星期/外部排程邊界與決策／工程待辦狀態；已定案不代表已實作，P1仍為影子監測。

控制目標與前台可調安全參數已補入[CONTROL_PARAMETERS.md](docs/CONTROL_PARAMETERS.md)：平均目標停止投藥、危險門檻預設採原HA且可調；D01已定，不阻擋繼續開發。

## P3c 現行流程與原生操作

- 四列必須各含一次 `refill`、`nutrient`、`acid`、`mix`。可改順序；第一列為 `flow_start`，其餘可選 `flow_start`、`after_previous_started` 或 `after_previous_finished`，延遲相對於該錨點，不是任意腳本或排程時間。合法 overlap 仍受後端輸出資源、最低液位、採樣及安全 gate 約束，不保證同時致動。
- 必要加藥循環與獨立 mix 不同：停用獨立 mix 不會解除加藥必要循環。共用 circulation 由後端仲裁；不能以 Card 或其他入口繞過 ownership。
- 有限 condition 僅 `level` / `ph` / `ec` 的 `gte` / `lte` 有限數值，或 `none`；不是 template。液位用 m（0–10）、pH 0–14、EC 用 mS/cm（0–20）。每列等待期限與整輪期限有界。
- 到「設定 → 裝置與服務 → UNiNUS Nutriculture → 該槽的設定／選項」，勾選 **Open flow plan editor (no settings saved)**（`flow_plan`），開啟 **Flow plan / 流程計畫**。這是原生 selector 表單，不必貼 JSON；進入編輯器不會保存同頁其他設定。
- 每列有 stage、start rule、delay seconds、wait timeout seconds、condition source/operator/value 及 weekdays；`run_timeout_seconds` 為整輪期限。用 **Save / seven-day Preview / Cancel / move row up or down** 的 `row_0_down` / `row_1_up` 等動作調序；規則隨列保留，調序後第一列仍須 `flow_start`。
- `action=preview` 讀草稿，列出七日有效流程；`save` 才以版本衝突檢查原子保存，作用於下一輪，不啟動設備；`cancel` 不保存。其他頁面已改設定時須重開並協調，不能覆蓋新版本。Card 同樣提供階段列、上下移動、星期、Preview／套用／取消；參數群與流程草稿為分開 namespace。
- 每階段真正 admission 前依 **HA 設定時區** 的當地星期重查；跨午夜不沿用整輪開始日。星期是允許 gate，不會自行排程、補跑或啟動。外部 automation／`uninus_nutriculture.start_flow` 與原生整輪 Switch 共用後端；Enable 開關不是 start。
- Preview 使用相同有限依賴／略過與資源模型，反映停用、星期、條件、等待和依賴，不再只是單一 eligible 清單。未來感測、實際加藥／補水完成時刻及跨日 admission 可能未知；七日預覽不是確切時間表、成功保證或灌溉許可。無致動也不建立運行任務。
- P3c交付時永久 native suite 為 335；P4a交付時 suite 為378；R4 full 339 包含四項外加 QA probes，不屬正常 repo，不能要求乾淨 CI 收集 339。源碼兩審不取代 publication-equivalence 審核或 exact-commit hosted CI。內嵌版本未升正式發行版本；不為顯示美觀修改 bundle/hash/version metadata。

## P4a 本輪交付範圍（已實作並兩審；非完整P4/發布宣稱）

- [參數配方契約](docs/P4A_RECIPE_CONTRACT.md)
- 原生Options與Card共用entry-owned UUID配方庫：建立/編輯/選擇/刪除二確認，Save/Cancel不改運行參數，Apply原子更新既有10參數且零致動。不能變更commissioning、Enable、fault、流程、星期或裝置保護。
- P4a切片來源歷史（非現行整案範圍）：只交參數配方；P4b品質/完成/許可已實作並兩審；完整配方擴充及P4c外部結果/通知仍待後續，不標全P4完成；舊S1–S5 ready_for_irrigation固定false；新quality_v1／唯讀permit有效時可True。
- 不新建通用測試框架，不重做已交付P3，不用物理驗收待辦阻擋隔離軟體開發。每個主要行為真RED→GREEN、一次整合SPEC→品質；P4a最多兩輪具體repair，P3的4/4歷史不重置。

## P4b 現行操作與交付界線

見[P4b原生／Card操作與唯一權威](docs/P4B_OPERATION.md)。P4b source、兩審、出版等價、push與exact-HEAD hosted CI及下載產物核對均已完成；仍不等同HACS或實機驗收。P4c來源兩審／本機gate完成但出版／新HEAD CI未完；P5進階體驗、兩槽皆commissioned與shared-output實機驗收仍pending；Issue #4維持OPEN。修復預算4/4不重置。

## P4c 來源已兩審，出版／實機尚未完成

- 以 [docs/P4C_RESULT_NOTIFICATION_CONTRACT.md](docs/P4C_RESULT_NOTIFICATION_CONTRACT.md) §8及 [P4C_API_SCHEMA.json](docs/P4C_API_SCHEMA.json)優先：既有整輪trigger→穩定result_v1投影／事件；nativeOptions與Card共用私有通知權威、選native provider／事件／cooldown；default disabled。無scheduler、任意service runner或直接灌溉。
- P4c R4來源兩審與本機完整gate已完成；本出版prep本身不是APPROVED，尚待出版等價／真Card commit pin／新exact-HEAD hosted CI。P4c 4/4、P3 5/5結案，不重開產品修復。通知失敗／ACK不改安全OFF、fault、quality或permit；Core STOP與普通flow Stop分辨；明確private reconcile，不自動entry reload。
- P5進階視覺、手機／鍵盤、完整歷史／診斷、兩槽各自全流程／跨槽共output commissioning、HACS與實機仍保留；P4c必要idle低pH／高EC唯讀告警G1不延後。原F/D及歷史失敗不回寫。
