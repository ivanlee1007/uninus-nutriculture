# UNiNUS Nutriculture

## P2候選：隔離測試入口與限制

**P2補水候選已通過獨立SPEC與品質／安全審查；未部署原HA，不應直接接管實機。**完整結果與交付界線見[P2_ACCEPTANCE.md](docs/P2_ACCEPTANCE.md)。

- 後端原生Options明選已註冊補水輸出、commissioning確認、回饋期限及星期；保存/取消不致動。
- 先允許總開關與補水子開關，再用原生整輪Switch或`uninus_nutriculture.start_flow`請求一次補水；ON不會自行打開其他Enable。
- 新版Card選擇後端實際的**schema2控制狀態Sensor**，即可看見總/補水/整輪、急停/復歸；舊schema1監測Sensor仍無控制按鈕。不要使用來源pH/EC/液位Sensor作入口或猜測Entity ID。
- 高水位、正常停止、過期/無效來源、逾時及急停交由後端處理；未確認OFF不顯示假成功。運行中重複ON不重啟，重啟HA不續藥。
- 人類操作預設僅管理員；原生automation可使用內部Context。P2只有補水，養/酸/獨立混合不可啟動，也沒有流程編排UI或內建排程。
- Commissioning勾選不是韌體/斷線保護的軟體證明；HA當機/通訊失效時，一般Switch不保證會自停。只能識別已知Registry/平台uniqueId綁定，不能推測所有實體別名；部署前需另行確認設備端保護。
- 本機已驗證：backend151項、Card Node9項/真Chromium23項及shipped UI→真隔離HA handler→SwitchEntity假硬體。這不是原HA前台宿主、HACS安裝或物理驗收；最新CI只以對應commit的Actions為準。



Home Assistant自訂整合，網域`uninus_nutriculture`。**0.2.0為P2補水候選：已實作需明確commission的受控補水，並保留P1監測與10個原生Number。獨立審查已通過，實機及HACS安裝尚未驗收。**

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

P1監測介面不啟動設備；P2補水控制會使用refill_timeout，其他加藥/混合時間仍待P3。所有寫入均檢查有限數、界限、精確十進位步進及三組 `low < high`；不合格則整組參數與 options 保持不變。每槽共用鎖序列化寫入，並在取得鎖後重新確認 Number 的生命週期及 registry 擁有權。卸載後與排隊中的舊實體寫入會拒絕。

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

## 完整產品範圍（P2補水候選已接通，其餘分期保留）

| 階段 | 範圍 | 目前狀態 |
|---|---|---|
| P1 | 影子監測、原生來源選擇／選項、十個原生 Number、固定 status 契約 | 本 alpha 已實作與離線原生 Core 測試 |
| P2 | 總/四子開關、統一gate、外部整輪服務契約、補水安全骨架 | 補水候選已實作；native/瀏覽器/跨層測試通過，獨立審查已通過；發布/CI以對應commit為準，實機尚未驗收 |
| P3 | 四階段可配置順序/重疊/相對延遲與條件、每階段七日複選、最小階段列UI/預覽、加藥/混合/仲裁、原子群組參數 | 待實作；R03評估時點已確認，其他R02等細節待確認，P1仍僅逐項Number |
| P4 | 配方、外部action/結果互通與通知、完成/品質/灌溉許可介面 | 待實作；不建排程器、不匯入排程、不管理外部腳本/旁支 |
| P5 | 進階視覺化編輯器、手機/鍵盤、診斷/歷史、多槽產品體驗、release candidate | 待實作；P1 已有 entry 隔離，不等同完整多槽產品 |

本庫僅包含後端整合；[伴隨儲存庫 `uninus-nutriculture-card`](https://github.com/ivanlee1007/uninus-nutriculture-card) 已提供 P1相容／P2操作 Card，不在本庫內。也可使用 HA 原生 Entities 卡片呈現 Numbers 與 status。P2已完成獨立審查，不代表HACS安裝或實機驗收。完整計畫仍以 `docs/DEVELOPMENT_PLAN.md` 為準。

## 控制規範與後續設計

- [總開關、四階段子開關與可配置流程](docs/CONTROL_SWITCHES.md)：P2骨架已實作，P3完整階段待接入；舊schema1監測介面保留。
- [流程編排/UI、每階段星期與外部啟動研究](docs/FLOW_DESIGN_RESEARCH.md)：建議階段列＋開始條件/延遲＋並行組＋預覽；R01取消鏈結及R03實際開始前查星期已確認；新增整輪運行Switch，R02/R04等細節待確認。何時啟動整輪由外部排程/HA automation決定；星期僅為允許gate，混合/脈衝/安全期限仍由後端管理。
- [原系統與新規範功能差異盤點](docs/FUNCTIONAL_PARITY_REVIEW.md)：區分已實作、保留用途、刻意改善與待決策，作為後續驗收基準。

## 測試

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-test.txt
.venv/Scripts/python.exe tools/evidence.py local-check tests -v -s
```

Linux 改用 `.venv/bin/python`。`tools/evidence.py` 會建立新的不可覆蓋 evidence 標籤目錄、複製當時完整 source/tests、記錄 SHA-256、實際命令與退出碼。詳見 `docs/TESTING.md` 與 `docs/P1_HANDOFF.md`。CI 設定為 Ubuntu／Python 3.14；遠端驗證結果以本儲存庫 Actions 的對應 commit 為準，本機測試不等於遠端 CI 或正式站驗收。

## 共同開發規範

[DEVELOPMENT_SPEC.md](docs/DEVELOPMENT_SPEC.md)統整已確認結論、前後端責任、開關/流程/星期/外部排程邊界與11項未決策；已定案不代表已實作，P1仍為影子監測。

控制目標與前台可調安全參數已補入[CONTROL_PARAMETERS.md](docs/CONTROL_PARAMETERS.md)：平均目標停止投藥、危險門檻預設採原HA且可調；D01已定，不阻擋繼續開發。
