# P3c SPEC 修補第3/3輪 — 實作交接（非審查批准）

## 狀態
授權額外且最後一輪只處理 I1–I4；本輪已執行，不開第四輪、不重置budget。source可交父端重新freeze→affected joint SPEC（含新的 native UI 與 affected S5 join）→獨立品質。未發布、未關Issue3、未給完整P3批准。

## 實作
- I1：原有 init/commissioning 表單及 v1–v4 路徑保留，新增 `flow_plan` 原生入口。`plan` 真非JSON四列欄位含stage順序、move up/down動作、start_rule、delay、有限condition、wait、星期及globaldeadline；Save/七日Preview/Cancel分開。所有move保留列設定重新驗證，不暗改首列規則；首列非flow_start會拒。開頁、Preview、Cancel零write；首次明確Save重用 `flow_settings.save` 同Tank.lock/CAS/validator/一次update。首次v5仍masterOFF且無owner/pending；不偽造commission。既有v5 plan保存不換Controller。
- I2：v5 weekday僅native plan頁提交，雙revision沿既有plan writer同交易增加；no-op不加版。v5一般init不提供weekday；更重要 `Tank.write_settings` 層拒跨namespace weekday變更，非僅UI藏欄位。沒有加legacy整包overwrite。native頁只編plan namespace，未新增跨兩namespace一起編輯模式。
- I3：四固定前列錨點可達性小pure規則 `reachable_refill`，排除必須先等低液位mix admission的refill；獨立flow_start（含後列）可達refill仍允許等待。實際admit每次重新計算，條件/資源等完仍重查。低液位Save不拒合法未來計畫，不自補水。
- I4：`dependency_ready` 小pure規則供runtime anchor與Preview共用；blocked無finished釋放；skipped_disabled/skipped_weekday能釋finished但無started。未知finished時間保持null，不偽造完成時間。Preview及runtime共用refill可達性。

## 真執行及不可覆寫證據
所有run在 `nativefixtures/round3-*`：每個有fresh build（完整source/test bytes）、receipt command/cwd/env/source_before/source_after/exit、raw.log與actualimports；runtime為ephemeral，不作交付包。
- `round3-original-red`：SPEC `probe_spec_v2.py` 逐字複製，SHA `9428720958c4ebb0095d1e3a638eb76baded3404c58c72ec753a7277d41b2004`；真Core **4 failed / child1**，四個真assert失敗，非fixture錯。
- `round3-native-ui-green`：2 passed，I1/I2。
- `round3-refill-green`：1 passed，I3。
- `round3-focused-green`：32 passed，含四原反例（僅UI導航/欄位bootstrap適配，保留版本/原子/no-write等原assert）及原22。不可與full加總。
- `round3-final-full`：**326 passed/1 failed**，既有translations exact-set未加入新flow_plan標籤；原始失敗保留。只擴必要相鄰exact-set assert並加plan exact-set，未弱化runtime安全斷言。
- `round3-final-full-verified`：**327 passed，0 skipped，child0，156.69s**，Python3.14.5/Core2026.10.4。raw SHA `8a39a2db478e55a8e9ad402adadec0b5826a49174daffb0d37598700f0254412`。含10個新增永久case與既有317。
- `round3-original-post`：原字節probe重新跑 **3 passed/1 failed child1**：I2舊init `mix_weekdays` 路徑現在被原生schema拒絕（InvalidData），非誤報原probe全綠；新UI路徑成功雙rev已由永久case驗證，manager直接legacywriter也另有拒絕/zero-write斷言。交獨立SPEC重新判。
- 最終Ruff **0.17.3** check及format --check全0，scope `custom_components tests tools/p3c_fix_gate.py`，84 files formatted。初次import-order/format問題已修並保留工具結果。
- 所有SDK測試5 warnings皆既有HTTP/backoff deprecation。

## provenance
`P3C_SPEC_FIX_AUTHENTICATION.json`：原192 frozen inputs全部不變、原SPEC FINAL列所有artifacts全部不變；RED實跑原來源runtime/tests/tools逐一匹配manifest；最終70個actualimports全部在owned build且hash對source_before，無原庫code誤import。最終全suite inputs_unchanged=true。peer由 frozen integration-input sibling固定S5 bundle，非live peer；P3A/P3B_CARD_PYTHON明設，舊bridge確實包含於全suite。
原四RED/修前bytes、失敗logs與歷史evidence不修改。write/patch遇CRLF及read pagination工具限制，改用保留原CRLF的正式patch，沒有approval拒絕/timeout或繞過授權。

## 修改檔案
既有：`custom_components/uninus_nutriculture/{config_flow,flow,flow_settings,manager}.py`、`strings.json`、`translations/{en,zh-Hant}.json`；必要相鄰 `tests/test_boundaries.py`。
新增：`plan_options.py`、`tests/test_p3c_spec_fixes.py`、`tools/p3c_fix_gate.py`、`P3C_SPEC_FIX_PROGRESS.md`、本HANDOFF及`P3C_SPEC_FIX_AUTHENTICATION.json`、七組owned run輸出。

## 後續與限制
父端先freeze新source，再跑affected joint SPEC及fresh S5 shipped Card↔native join，才獨立品質。I4已改Preview，不能把舊attempt3的所有join cells直接稱本輪重跑。Node13/browser38/trustedtyping/geometry封存僅compose未變bytes，這裡沒重跑，也不算入327。原庫/peerCard/契約/wire/根BASELINE/歷史evidence只讀；未stage/commit/push/install/外網/siteHA/認證/實機/tag/deploy。原HA實體cutoff不作claim。

## 可重用工作流（留在owned scope，不改profile skill）
先把sourcebound原probe逐字複製freshOUT並真跑RED，凍結前後bytes；每主path綠即更新checkpoint；UI路由改變時留原失敗、只調新copy導航而保留assert；最後full實際case/child與actualimports逐一比來源、固定peer sibling並明設bridge interpreter；永不把舊Card join當改後Preview的驗證。
