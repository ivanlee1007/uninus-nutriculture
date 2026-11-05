# P4b 原生／Card 操作與唯一權威

狀態時間：2026-11-05（本機日期工具確認，UTC+08:00）。F4來源已實作、獨立SPEC與完整品質兩審及本機隔離驗證完成；本次僅出版準備，不宣稱新commit已push、hosted CI、實機或HACS驗收。

## 設定路徑

1. 在 HA 設定→裝置與服務→本槽設定／選項進入 quality editor；開啟編輯器不保存主頁其他欄位。必須已明確保存S5控制設定；舊控制版本讀取為unsupported，不在GET偷偷遷移。
2. 原生Options與Card都可調 `enabled`、`stable_samples`、`stable_interval_seconds`、`stable_duration_seconds`、`permit_ttl_seconds`、非空 `required_stages`（refill/nutrient/acid/mix），以及ph/ec/level各自的來源 `mode`（reported/sequence/timestamp）、`attribute`、`report_contract_confirmed`。schema_version/revision唯讀。品質上下界沿現有十個Number的低高標，不另造門檻。
3. `reported`需確認上游每次report確實代表新實測；sequence需嚴格前進的非負整數attribute；timestamp需aware ISO且合法新鮮、嚴格前進的attribute。sequence/timestamp不可空attribute；三來源都須明確認定報告合約才可啟用。確認勾選不是硬體未重播或設備保護的證明。
4. Card editor選後端registry實際quality_status Sensor作 `quality_entity`，不可猜Entity ID；combined配置同時選既有control `entity`，兩者須同一entry。只配quality_entity是standalone readonly展示，不能保存policy。展開品質面板後管理員可讀取／編輯；初次Save自動GET讀回，不必手動刷新。斷線、停用、錯槽、舊epoch／transport或權限變動不沿用cached True。
5. Save走同一後端transaction與三CAS：expected_policy_revision、expected_settings_revision、expected_flow_plan_revision。成功一次原子commit、revision+1並清窗口／撤銷許可，零設備致動；即使同值Save亦如此。Cancel/草稿/拒絕CAS不寫入；衝突保留草稿，先重新讀取並協調，不覆蓋新版本。沒有手動grant開關或直接滴灌按鈕。

## 工程預設與時效

初始disabled、三來源unconfirmed；8個round、最短間隔300秒、跨度2100秒是工程預設而非農藝或硬體安全認證。虛擬policy的TTL繼承該槽既有max_age_seconds（無值300秒），限制1–86400；保存後固定。預設必要四階段，可明選非空子集，但不能以skip、disabled、單階段執行或舊completed偽造新整輪成功。

terminal實際輸出OFF、所有operation/owner/lease閉合後，才收集新的三來源完整穩定窗口；getter/poll、同token不算樣本。許可期限取grant+TTL與來源freshness/timestamp截止最早值；後端可取消monotonic callback撤銷，UTC expires_at只是同一deadline展示。HA event loop不是硬即時物理保護。新報告不能延展grant+TTL硬截止。

出界、過期、故障、停止/急停、master OFF、必要子開關OFF、來源/設定/plan/commissioning變動、輸出不確定或pending、單階段或新輪、停用/卸載/關機，都撤銷且消耗candidate。健康恢復、reset或Enable ON不復活；需新的合格整輪。正常重啟也是permit=false、completion=none、count=0、新epoch；True與候選不持久化。recipe Apply成功（含同值）撤銷；catalog Save/Delete/selection/Cancel不撤銷。

## 三真值與外部接線

- quality.state：資料是否有效、範圍內及穩定；qualified不保證完成或授權。
- completion：本載入epoch最新整輪receipt；completed不保證品質或許可。
- permit.granted：新quality_v1 API與原生readonly irrigation_permit binary_sensor共用同一後端coordinator權威，條件全部成立時可True，失效立即False；Card只展示，沒有自己的許可計時器。

舊S1–S5 ready_for_irrigation固定false是legacy不授權欄位，不是新permit。外部automation必須明確改接新readonly binary_sensor或get_quality_v1的permit.granted，不把within_range、qualified、flow completed或legacy false當新授權。API仍要求active真人admin先授權再lookup；不改既有內部automation控制ACL。

## 尚未完成

P4c通知／外部結果、P5進階視覺化／歷史與多槽產品體驗、兩槽都commissioned與shared-output驗收、實機commissioning、HA部署、HACS安裝、tag/release皆pending。原19排程與8腳本不導入、不接管；不內建scheduler、不直接操作灌溉。Issue #4保持OPEN。本次不能重置已用4/4修復預算，也不是最終出版等價APPROVED。
