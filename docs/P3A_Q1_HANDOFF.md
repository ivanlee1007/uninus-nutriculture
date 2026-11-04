# P3a Q1 限定修補交接 — 最後第 2/2 輪，未批准

2026-11-03。整個 P3a 修補預算沿用 F1 的 1/2，本輪為 **2/2**，沒有更名重置。下一步由父端進行 affected SPEC 重查，通過後品質重查；若仍有阻擋，交父端升級，不能自行第三輪。Issue #3 不可因此關閉。

## 修補與真相

- `sensor.py` 分離全域 flow state 與 accepted nutrient stage outcome；root `disabled` 合法，nutrient stage 不再跟著變 `disabled`。accepted `run_stage` 不清除，不用現在的 Enable 猜歷史。
- 檢查實際 `NutrientStage` 後確認：原本沒有 `result` 成員，`run()` 的 result 只是區域變數；Sensor 單改無法在 fault reset／master OFF 後找回歷史。因此只在 `nutrient.py` 加最小 outcome 記錄：初始化 None、真正受理新 run 時重置 None、cleanup 確認 `owns_io=false` 後記錄實際 terminal flow state。未進入的 task 不當 completed，pending I/O 不創造成功 terminal。
- Sensor 僅在沒有 owned I/O 且 result 已存在時使用 outcome；否則保留實際 starting/stopping/fault，以及 dosing/mixing/waiting_sample/stabilizing→running 映射。不更動 dispatcher、cleanup 程序、authority、source latch、F1 closed allowlist、running union。
- `control.py` 完全未改，Card sibling、consumer strict validation 與原測試斷言未改。
- 原生 route 的持久 master=false、running=false、owns_io=false、nutrient/circulation 均 OFF；這是投影相容性缺陷，不是停泵失敗。重新 Enable／Apply 不會自動 ON；明確新 start 才致動。

## 永久回歸

新增 `tests/test_p3_stage_projection.py` 共 4 cases：aborted 後 master OFF；fault/reset 後 master OFF；completed 後參數更新/master OFF；accepted 尚未執行與 held OFF ACK 不可假成功。前三條還實際再次 Enable/start/stop。

新增唯一 tool `tools/p3a_postrun_check.py`：輸入真 Core snapshot，不重寫 state/map，載入 sibling 真 shipped JS，用 Chromium 檢查 controls、master/emergency/reset 可用；實際填 ph_low→Apply，要求發出 master ON 與整組 settings request。由 native test 將這些 **shipped UI 發出的 payload** 逐一經已註冊 Core service 執行，讀回持久 master=true、ph_low=5.3、outputs 仍 OFF。這是 capture→shipped consumer→native request replay，不冒稱同瀏覽器內的即時 HTTP/readback bridge；另兩個既有完整 live bridges 仍實跑通過。

Native suite 不要求 backend venv 安裝 Playwright。明確設 `P3A_CARD_PYTHON` 才啟動 postrun consumer gate，Card venv 已有 Playwright；子程序 stdout/stderr 有界收回，失敗也 finally cleanup。未安裝任何套件。

## RED → GREEN、實際 gates

cwd：`D:/UNiNUS Projects/AI project/uninus-nutriculture`。
OUT：`C:/Users/ivanl/.hermes/cache/scratch/p3a-q1-repair-20261103/`。
所有完整 argv/cwd/child exit/raw-log SHA/prepost 83 inputs 在 `OUT/*-receipt.json`，不是 wrapper exit 冒充 child。`run_q1.py` 呼叫 `tools/evidence.py p3a-q1-*` 保存 pre-run source/test 原 bytes。

| Gate／label | 實際結果 |
|---|---|
| `red` | child1，3 failed/1 passed；真 disabled 與 aborted/fault/completed 不相等 |
| `probe-red` | child1，原斷言 1 failed/1 passed；真 native capture |
| `capture-red` | child1，真 shipped JS controls_attached=false，calls=[] |
| `green` | child0，4 passed；first GREEN |
| `full-final` | child0，**249 passed**，5 upstream warnings，93.34s pytest；原245＋永久新增4，focused 不重複加總 |
| `bridge-postrun-final` | child0，4 passed，前三 outcome 各真 Chromium156.0.8078.4，page_errors=[] |
| `probe-green` | child0，2 passed，5 upstream warnings |
| `capture-green` | child0，stage=aborted/root=disabled/master=off；controls_attached=true、master/emergency enabled，實際發出 ON/emergency requests |
| `node` | child0，10 pass、0 fail/cancel/skip，Node v18.6.0；experimental runner warning 保留 |
| `browser` | child0，canonical 30 tests，Chromium156.0.8078.4 |
| `dosing` | child0，live UI→native：pump ON/midpoint OFF 0.001184s/mix/fresh sample complete；page_errors=[] |
| `settings` | child0，live Apply/Cancel/conflict/readback；hardware_calls=[]、page_errors=[] |
| `ruff-final` | child0，All checks passed |
| `format-final` | child0，66 files already formatted |
| `git diff --check` | exit0，既有 manager/sensor CRLF normalization 提示保留 |
| `verify_q1.py` | exit0，baseline/receipts/snapshot maps/final current-source/staged empty 全通過 |

原 capture checker 的 `settings_disabled=true` 是 **尚無草稿的 Apply**，並非 settings 不可用；永久 checker 真輸入後確認 Apply enabled、發送及 native 持久讀回。沒有捏造 clean draft 時 Apply enabled。

命令摘要（PY=.venv/Scripts/python.exe；完整參數見 receipts）：

```text
PY -B tools/evidence.py p3a-q1-red tests/test_p3_stage_projection.py -v -s -p no:cacheprovider
PY -B tools/evidence.py p3a-q1-green tests/test_p3_stage_projection.py -v -s -p no:cacheprovider
PY -B tools/evidence.py p3a-q1-full-final tests -v -s -p no:cacheprovider
P3A_CARD_PYTHON=<Card .venv/Scripts/python.exe> PY -B tools/evidence.py p3a-q1-bridge-postrun-final tests/test_p3_stage_projection.py -v -s -p no:cacheprovider
PY -B OUT/run_q1.py {browser|node|dosing|settings|probe-green|capture-green|ruff-final|format-final}
PY -B OUT/verify_q1.py
```

全部 browser 使用 `CHROMIUM_EXECUTABLE=C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe`。first/full 後 checkpoints 在 `scratch/nutriculture-p3a-q1-progress.md`。first GREEN 後只額外加 test 子程序 timeout cleanup，已用新 labels full-final/bridge-postrun-final 重跑綁定 final test bytes，前次結果保留不覆寫。

## 原 probe／sealed evidence 保護

- 先 byte-identical 複製原 `test_quality_adjacent.py`、`check_native_capture_ui.py`、`run_gate.py` 到新 OUT。原 quality 目錄及 frozen successor 逐檔 hash baseline→final 不變，沒有改原斷言或覆寫其 JSON/log。
- 原 probe 硬編碼 ROOT=frozen backend，故另建 `test_quality_adjacent_working.py` **僅替換 ROOT 為 working backend**，所有 assertions/OUT/source_bound 保留。原副本仍 byte-identical，SHA：`05aeca55309d666fc004637a5ba8045112da4bdd7a26a2e28751839780ef5c51`。
- capture checker 副本無修改，硬編碼 shipped frozen JS 路徑保持；其 JS 與 working shipped SHA 一致。新 permanent checker 消費 working sibling shipped。
- 本輪 RED JSON 在 `OUT/red-captures/` 留存後，GREEN 才更新本輪 OUT capture；原 quality capture 不動。舊 provider probe、四個 F1 snapshots、第一輪環境失敗與既有 sealed snapshots 都未改動。
- successor manifest SHA 仍為 `1562fbc72421466659e22fd34059e9331ecf1484de267619bb54eca84cae02ff`；其 baseline 中全部檔案未變。294 baseline files 僅下列兩 production 檔改動，其餘全相同。每次 gate 的83 consumed inputs pre=post；所有 receipts raw-log SHA 已驗證。

## Final exact SHA256

| 檔案 | SHA256 |
|---|---|
| `custom_components/uninus_nutriculture/nutrient.py`（修改） | `7e119412b4beeeebbedad677fc5c6352367c73c14993027cb197bb397fc7285e` |
| `custom_components/uninus_nutriculture/sensor.py`（修改） | `776356bb5bca551326277da24da9c3ae62cde87068e1e333a4c0286fdf13d97d` |
| `tests/test_p3_stage_projection.py`（新增） | `1c352fdbe335a8882e95d8f5ab09207e8f53c38d8d14fee013d9bc7c9552ae8d` |
| `tools/p3a_postrun_check.py`（新增） | `483e0244edbe22a0cbf4d546a131e44ac84ab83b3eb835408a7f5664b4d0de99` |
| `control.py`（未改） | `7b61e287eb458cf05a7f8d762b211297529f6c24a5a1d38c193e78e7ee41e259` |
| shipped JS（未改） | `8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f` |

另新增本文、`docs/evidence/p3a-q1-*` 八組 source/test/run/log snapshots、scratch runner/verifier/receipts/captures/browser artifacts/final-owned-bytes；只更新 default profile 既有 native checkpoint skill 的通用規則。未改其他 profile。

Final full raw log SHA：`16392da1ff9348d1930ca131a2a1f07d49c3676f1c6759105eb4250414a8b06d`。
Final postrun gate raw log SHA：`0850338ff9bb31f0735e1563a358d461c199630f402299e5ce5bc67d2112f146`。
其餘 raw hashes 見 `OUT/final-verification.json`。

## 限制與下一步

本機隔離 native Core + fake hardware + 真 shipped Chromium，非實機/原 HA/hosted CI 認證。未接憑證、部署、外網 API；未 stage/commit/push/tag/release，staged empty 已驗。未擴酸、獨立 mix、enum 或框架。沒有自批准；父端需 SPEC affected recheck（尤其 result ownership/投影）再品質重查。若再有未解阻擋，停止修補並升級父端，不啟動第三輪。
