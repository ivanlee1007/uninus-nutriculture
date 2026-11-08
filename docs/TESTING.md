> 現行來源狀態（2026-11-08）：P1–P3、P4a／P4b／P4c軟體來源及對應精確HEAD hosted CI已交付。本版P5a四階段視覺工作台／手機鍵盤已實作，修正後完整SPEC與品質兩審均批准，Q-01已關閉；Preview／Apply／Options／Store與fresh SDK隔離驗收已通過。P5a joint-review repair 1/1已用，P4c 4/4及P3 5/5結案不重置。本提交仍須以其精確HEAD hosted CI與遠端產物完成來源交付核驗；不得將本機或來源審查當成hosted CI／完整P5／實機／HACS驗收。完整P5十二項後續範圍保留，未tag／release／部署。

# P1 測試紀錄

## 實際執行環境與範圍

- Windows 離線 Python venv，CPython **3.14.5**；真正的 `homeassistant==2026.10.4`，非框架替身。
- `pytest==9.2.0`、`pytest-asyncio==1.4.1.post1`、`ruff==0.17.3`，見 `requirements-test.txt`。HA 套件的 Requires-Python 為 `>=3.14.2`。
- 先嘗試 WSL Ubuntu-26.04，但主機回報 `HCS_E_HYPERV_NOT_INSTALLED`。未修改虛擬化或系統設定。改用本庫 `.venv` 安裝真正 Core；第一次套件下載逾時，第二次完成安裝。
- 使用真正 `HomeAssistant`、原生 base bootstrap、ConfigEntries／ConfigFlow／OptionsFlow、實體 registry、平台 setup/unload、StateMachine、`number.set_value` ServiceRegistry 與原生 `.storage/core.config_entries`。
- 沒有 pytest HA 假框架、SDK stub、全域 HA 相容性補丁或 auth 關閉。fixture 的服務事件觀察器只記錄並拒絕任何非 `number` 的已派送服務；不取代原生分派。另有 AST 安全檢查禁止控制服務呼叫／MQTT／輸出平台。
- 不啟動 HTTP listener、不連線任何既有 HA。來源使用原生 StateMachine 建立的隔離 sensor states；不是實體農場感測器或瀏覽器 UI 驗證。

## 真實 RED → GREEN 垂直切片

命令形式：

```sh
.venv/Scripts/python.exe tools/evidence.py <label> <test-path> -v
```

每個 evidence 目錄包含：**執行前**的 source/tests 完整 bytes、SHA-256、命令、UTC 時戳、退出碼與未改寫的 pytest 原始輸出。舊的失敗與 harness 錯誤均保留，沒有事後重建為 RED。

| 行為 | RED evidence | GREEN evidence | 真正失敗點 |
|---|---|---|---|
| 原生十個 Number 與 status | `01e-setup-behavior-red` | `01-setup-green` | 可正常載入的空整合沒有註冊實體，`0 != 10` |
| 原生 set_value、同步與 options | `02-write-red` | `02-write-green` | 真正服務到達 Number 邊界但尚不支援 setter（NotImplementedError），不是 import error |
| 完整候選驗證與並發序列化 | `03-validation-red` | `03-validation-green` | 不合法 pair／步進／NaN 未拒絕，並發可破壞 pair |
| 來源事件、單位與刪除 | `04-sources-red` | `04-sources-green` | 真正 StateMachine 更新後仍舊回報 within_range |
| last_reported 與週期到期 | `05-freshness-red` | `05-freshness-green` | 等待真實 timer 後仍未失效 |
| 原生設定／來源選項流程 | `06-flow-red` | `06b-flow-green` | 真正 flow manager 得到 abort 而非設定表單 |
| 卸載寫入與 registry 目標 | `07-lifecycle-red` | `07b-lifecycle-green` | 排隊舊寫入成功、改名後 status 仍暴露舊 ID |
| B1：不可用 Number 目標省略及原生恢復 | `11-target-red` | `11-target-green` | 實際 status 的 parameter_entities 仍包含 unavailable／unknown／非有限數／非數字的 ph_low |

`01-setup-red`、`01b-setup-red`、`01c-setup-red` 是 bootstrap fixture 順序錯誤；`01d-setup-red` 尚缺 config_flow import；**均不計為行為 RED**。只從 `01e` 開始計算 setup 行為證據。

`06-flow-green` 保留三個 harness 錯誤：原生 selector 的拒絕會在進入整合前拋 `InvalidData`，不一定返回有 errors 的 form。測試修正為接受原生拒絕，仍檢查無 entry 建立；沒有更改 production 來迎合 fixture。

`07-lifecycle-green` 保留一個 harness 錯誤：原生 registry 在 unload 後可留 unavailable placeholder，並非一定移除 state。修正為驗證無活動狀態、無參數變更與無監聽；沒有移除 HA 原生 placeholder。

`08-restart-safety-verification` 的 restart 與 AST 已通過，但嘗試對 slotted ServiceRegistry 實例附加 spy 造成其他 fixture errors；改為只讀的原生服務事件觀察器，`08b-restart-safety-verification` 全綠。這不是 production RED。

`08b` 的 fresh-process/storage、`09-identity-verification` 的 rename/disable/delete queued-write 與精確 metadata，以及最後的 inclusive-boundary/translation 測試是**補充驗證**：加入時已綠，不冒稱新的 RED。

## 原始 52 案例結果（歷史證據，未覆寫）

```sh
.venv/Scripts/python.exe tools/evidence.py 10-final-native tests -v -s
.venv/Scripts/python.exe -m compileall -q custom_components tests
.venv/Scripts/ruff.exe check custom_components tests tools/evidence.py
.venv/Scripts/ruff.exe format --check custom_components tests tools/evidence.py
```

- **52 passed，0 failed，0 skipped，5 upstream deprecation warnings，31.21 秒**。
- Compileall 成功；Ruff check：`All checks passed!`；format：`20 files already formatted`。
- 主證據：`docs/evidence/10-final-native/pytest.log`、`run.json`、`snapshot/`。26 個 source/test/config snapshot 檔案的雜湊已逐一比對成功。
- 警告來自 Core HTTP application 繼承與其 backoff dependency 對 Python asyncio API 的使用；未全域壓抑或修改相依套件。
- 上述不同 GREEN runs 大多重疊，**不能相加成總案例數**；52 是最終一次收集並執行的數量。

## B1 修正後實際結果

獨立 SPEC review 重現不可用 Number 仍出現在 `parameter_entities`。修正僅限 `Tank.targets()`：保留原生 registry 的 domain／platform／entry／unique ID 與停用檢查，再要求 state 存在且為可解析的有限數值。不修改服務、schema 或寫入架構。

新增原生參數化 regression，透過真正 StateMachine 改變既有 registry-owned Number，等待原生事件，再讀取**實際 status sensor**；驗證該目標省略、其他九項不變，再由同一原生 Number 發佈健康 state，確認相同實際 ID 恢復，parameters／options 不變。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe tools/evidence.py 11-target-red tests/test_identity.py -v -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe tools/evidence.py 11-target-green tests/test_identity.py -v -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe tools/evidence.py 12-target-full-native tests -v -s -p no:cacheprovider
```

- RED（改 production 前）：**6 failed、5 passed、5 warnings，5.93 秒，exit 1**。unavailable、unknown、NaN、Infinity、-Infinity、非數字六案均在真實 status 仍包含 ph_low 的 assertion 失敗；missing-state 案原已綠，僅為補充 coverage。
- GREEN（相同測試 bytes）：**11 passed、5 warnings，3.11 秒，exit 0**，含既有 identity／metadata 四案與新增七案。
- 完整原生 suite：**59 passed、0 failed、0 skipped、5 upstream deprecation warnings，30.64 秒，exit 0**；與先前 52 案例為重疊測試，不相加。
- Compileall、Ruff check、Ruff format check 均 exit 0；format 為 `20 files already formatted`。原始輸出在 `docs/evidence/12-target-full-native/static-checks.log`。
- 三個新 evidence 目錄均含執行前完整 snapshot／SHA-256／命令／UTC 時戳／退出碼／原始 pytest.log；`10-final-native` 保持原歷史 52 案例證據。這是隔離原生 backend regression，不代表已通過整合 SPEC 複審、品質／安全審查或線上驗收；本修正未重跑 reviewer 的瀏覽器/native bridge。

## 原生正常停止／新程序儲存證據

`tests/test_restart.py` 分別啟動 write 與 read 兩個新的 Python 程序，兩者都載入真正 HA Core 2026.10.4。write 透過原生服務修改全部十個參數、原生 registry 改名一個 Number、unload，再呼叫真正 Core stop/final-write。read 從同一隔離目錄的原生 storage 載入，不重建 config entry，驗證 entry ID、改名後 entity IDs、全部參數、status 及固定 false。

最終 `pytest.log` 的 `FRESH_PROCESS_STORAGE=` 列包含兩次的實際 JSON，且測試直接檢查磁碟上的 `.storage/core.config_entries`。測試不是在相同 Python 程序中重用 manager，也沒有直接寫入偽造 HA 儲存檔。

**限制：這是 orderly-stop/restart-storage，不是突然斷電／kill／fsync 或實際 Supervisor 的部署驗收。**原生 `ConfigEntry.async_update_entry` 的 scheduled-save 語意保持不變。

## 尚未執行

- 遠端 Ubuntu CI（已建立 workflow，但本次禁止 push）。
- hassfest 完整官方倉庫驗證、公開 HACS validation（私人 repository，明確跳過）。
- 實際 HA UI、實際裝置、農場資料、任何 P2–P5 控制功能。

Windows evidence runner 目前強制使用 Hermes-owned scratch 作 pytest 臨時目錄；早期 runner 尚未設定 basetemp，原始日誌如實保留其 pytest 預設暫存路徑。歷史腳手架產生器移到 `docs/evidence/scaffolding/`，不是可安裝整合的一部分，勿重新執行或安裝 evidence 中的舊 snapshots。

## P4c現行portable驗收

Card canonical gate執行unit14及DOM38＋16＋21＋16＝91；P4c既有16 cases正式註冊，沒有wrapper或重複計數。Backend永久suite為553／82；完整gate是R4歷史來源驗收，本出版prep只重跑Card canonical及portable真join，不冒稱再次執行553。

Backend與Card使用明確sibling checkout；`python -B tools/p4c_native_join.py --output <owned-output>` 後執行 `python -B tools/p4c_native_verify.py --output <owned-output>`。可用`--card-repo`指定Card；`P4C_CARD_PYTHON`指定browser SDK，預設當前Python。Chromium可由Playwright安裝或`CHROMIUM_EXECUTABLE`明確指定。只用loopback假硬體；不讀現場auth。CI pins保持Ubuntu24.04／Backend Python3.14／Card Python3.13／Node22，本機Node18.6非hosted驗收。
