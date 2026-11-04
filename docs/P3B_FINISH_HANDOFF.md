# P3b finish handoff（隔離；待獨立兩審，未自批准）

## 本輪結果
- 承接 recovered native275 / writer30，沒有重做 writer；本輪新增 compact10 role probes 與2個 role terminal-wire tests（合計12個新role case，非Cartesian）。
- `p3b-finish-12-full-wire`：**287 passed / 5 upstream warnings / exit0 / 129.69s**。其中酸與mix各真跑 aborted/fault/completed，再master OFF、必要reset、原生snapshot→byte-exact shipped Chromium→emit Enable/Apply→真native replay；每次都斷言零新增物理calls，accepted stage terminal保留。不是手造合法snapshot。
- Card `p3b-finish-07-node`：**12 passed / 0 failed / child exit0**。Card `p3b-finish-10-browser`：**33 passed / child exit0 / Chromium156.0.8078.4**。兩者不可與native相加作distinct總數；包含先前v1/v2/v3回歸。
- Ruff check與format check `custom_components tests`：全綠，75 files already formatted。

## 真正新增／修補
1. 原生新role永久補充：酸circ ACK後auth撤銷禁止pump ON；late physical ON追補OFF；OFF provider失敗時circ仍prompt OFF／fault不假OFF；獨立pH token repaint不得累計stable；C cutoff；mix真Core STOP/unload。
2. behavioral RED `finish-05/06` 證明mix-only reset誤依pH/EC、mixed酸+refill emergency被酸OFF ACK串等。最小修補：先arm所有新role，再由Controller.stop同時join所有owned stage與refill。running仍採owned union，physical dispatch仍唯一Controller，沒有新dispatcher。
3. behavioral RED `finish-08` 證明mix恢復健康level後仍被歷史revoked擋reset；reset專用健康檢查不忽略目前level新鮮度/單位/最低液位/OFF/identity/owned pending，只在全部通過後清mix revoked，零致動。
4. v4 outer exact keys、明列HA metadata、正常參數range/step的recovered改動本輪已實讀並由Node12驗證；未再跑一次性edit。新增browser Number子集不撤其他native controls、缺Number mapping禁止整組Apply、最新不合法Q step讓過期mutation零call。v1/v2/v3未放寬。
5. v4 memory-only demo新增`settings4`；真browser RED（缺情境）→GREEN，Apply/Cancel/reload reset、無非file請求；沿現CSS compact。只是記憶體模擬，不宣稱真設備保護。
6. 正式繁中新增acid/mix/circulation Options labels及說明、移除未支援的過時weekday標籤；services YAML補v4 units/null/S權威說明與revision step=1。全部服務field selectors已用本機真HA `selector.selector()`建構成功（Text/ConfigEntry/Number/Object），非僅YAML parse。
7. backend18個先前P3b未格式化檔以Ruff formatting整理；fixture import依既有明示re-export模式，不移除pytest fixture、不放寬lint。無功能性大重構。

## 保留的失敗及harness修正
- 所有finish-05起RED/raw logs/snapshots保留，沒有覆寫。
- `finish-05` pH repaint以不存在stable_count欄位讀取屬harness錯誤，改讀原stage.progress；不算behavioral RED。
- Card finish-08 full browser：31pass/1fail；嚴格outer exact正確拒絕test40把service envelope的config_entry_id/expected_revision塞進sensor attributes。fixture改成僅讀回七個native群組，沒有放寬production validator。
- Card finish-09：32pass/1error；不合法snapshot會移除controls而非保留disabled按鈕，改斷言controlTarget拒絕、controls不連接、零call。
- backend finish-11：mix三終態wire綠，酸completed等待逾時；前兩次真Apply已把ph_low改5.3，舊固定5.6不再達中點。fixture改讀本次native ph_low作合法stable sample；production未改，finish-12酸三終態全綠。

## 仍須獨立審查／未證明（不是全P3b安全批准）
- 新測混合emergency證據為**酸+refill+共用circulation**；尚未新跑N+酸+mix全commission且active酸時外部N ON的四路held-ACK矩陣。emergency分支仍使用`execution_stage`處理N，需重點審核active role與N idle owner選擇；不能把本輪證據擴大成所有commission role完整保證。
- 酸runtime hot-target tightening/loosening與C-F精確等號／重取lease絕對時鐘未新增完整邊界；已有cutoff與原酸midpoint/fresh-token測試，不等於這些新邊界全部驗收。
- Card v4已補exact/range/subset/latest-invalid及基本Apply/Cancel/readback；複製v3的所有pending/remount/repeated-Apply組合到v4不是本輪完整矩陣，不宣稱已全部覆蓋。
- mix completion用明示**domain clock seam**加速，原生Number保留合法1 min，未手改到1 min以下；不是實等60秒／實機保護驗收。
- No install、無token／原HA／實機／外網。無stage/commit/push/tag/release/deploy。父端P3a已批准並remote CI成功，不復活舊Q1；P3b隔離候選仍需SPEC與quality獨立兩審。
- P3c完整四stage可編順序、重疊、relative、星期preview仍保留原契約，不挪P5；本輪不新增generic DAG／scheduler／網路功能。

## 精確交接與唯讀證明
- `P3B_FINISH_SOURCES.json`：backend99 / Card16 source/test/tool/config/demo檔之SHA256、bytes、相對父端published worktree差異；`docs/evidence/p3b-finish-13-final-audit/snapshot/`為精確bytes，包含bridge工具及shipped JS。
- final-audit `receipt.json`驗全部指定GREEN child exit0、run source pre/post完全相同；舊evidence未改。
- frozen contract SHA256仍為`77df237d88acbf313327c6c959b54de4e161b8f8cc16a287322a30f570d318b7`。
- 原庫protected production/tests/config/demo/CI：backend73 / Card9 tracked檔前後SHA完全相同，0 mismatch。父端合法docs-only HEAD現為backend`810ce6d3c0805d8d9d2b6c211574e27059c4d3ee`、Card`81660d7909b6a2532adaf38df3dfe821d7806bef`；相對功能published heads ba40214/342f19的文件推進未誤判為本worker寫入。
- `P3B_IMPLEMENTATION_HANDOFF.md`保留作歷史，不再代表最新剩餘清單；根`P3B_PROGRESS.md`及本文件為恢復入口。
