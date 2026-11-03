# P2 整合候選獨立 SPEC 審查

**結論：BLOCKED — 1 個已實測的凍結契約違反（人類停止命令的 Context 遺失）。**

審查時間：2026-11-03 11:12–11:16 台北標準時間。範圍限 P2，不是品質／安全全面審查；未將 P3–P5 未實作列為問題。兩庫只讀，未修改 production/tests/docs，未 commit/push，未連原 HA，未讀取憑證。所有本輪執行產物均在 scratch。

## Must fix

### SPEC-1：原生 OFF／急停下傳實體輸出時遺失人類 Context

- 契約依據：backend `docs/P2_CONTROL_CONTRACT.md:23` 明確要求人類控制 admin-only、傳遞 Context、Switch/Button/domain 共用控制器；`:21–22` 將正常停止與急停列為本切片控制入口。
- 程式位置：backend `custom_components/uninus_nutriculture/control.py:143–176`（action 收到 context，但在 `165`/`173` 呼叫 stop 不傳）；`:178–193`（急停同樣在 `192` 丟棄 context）；`:347–350`（stop 無 context 參數）；**`:372–375`**（實際 `switch.turn_off` 沒有 `context=`）。對照 ON 在 `:269–275` 明確傳遞 context。
- 精確重現：隔離 native HA，使用現有 `p2_fixtures` 的真 `SwitchEntity` 假硬體、原生 Config/Options 及 Entity ServiceRegistry，不 mock service dispatch。commission 後開啟總／補水，以同一管理員 `Context(user_id=owner.id)`，依次向原生 `flow_run` Switch 呼叫 `switch.turn_on`、`switch.turn_off`。
- 實際結果：輸出 ON 收到相同 context id／管理員 user_id；輸出 OFF 收到新的 context id，**user_id=null、parent_id=null**。因此非僅使用衍生 Context，而是整段人類來源鏈皆遺失。現有 `test_admin_context_reaches_native_output` 只斷言第一個 ON，沒有覆蓋 OFF。
- 重現程式：`C:/Users/ivanl/.hermes/cache/scratch/p2_spec_context_probe.py`
- 原始輸出：`C:/Users/ivanl/.hermes/cache/scratch/p2_spec_context_probe.log`
- 命令（backend 根目錄）：`PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe C:/Users/ivanl/.hermes/cache/scratch/p2_spec_context_probe.py`
- 工具執行 exit code 0；probe 明確驗證 ON 有管理員、OFF 為 None，因此是成功重現違反，不是報稱合約測試通過。
- 最小驗收方向：正常 flow OFF、總／子 OFF、急停的直接人類停止下傳保留該 Context（或保持可追溯來源鏈的明確契約）；timer／shutdown 等內部安全 OFF 可使用內部 Context，且不得為傳遞／重查人類身份而阻擋安全關閉。此輪不修實作。

## 已核對的 SPEC 範圍

| 契約 | Source 核對與本輪／既有證據 | 結論 |
|---|---|---|
| 明選輸出、Registry 穩定身份、改名跟隨、禁替換／停用、多槽 ownership | `control_settings.py:12–86`；原生 commission／registry／busy Options 案例 | 未見其他違反 |
| 原生註冊與操作、admin/internal、entry 目標、OPTIONAL 回應 | `__init__.py:6–18`、`services.py:11–42`、`control_auth.py`、`control_entity.py`、`switch.py`、`button.py`；真 native 選測 | 除 SPEC-1 外符合來源核對 |
| Enable/start/normal stop/emergency/reset；資料有限值／單位／新鮮度、低／高水位與 weekday | `control.py`、`manager.py:snapshot`；原生 gate、來源 past/future/missing/unit/nan、out-of-range 可補水、high-level stop、reset 選測 | 未見其他違反 |
| starting 與 refilling 的保守 timeout/high bounds、late I/O、停止／卸載／重啟 | `control.py:82–89,122–141,209–390` 與 race/feedback/lifecycle/restart 原生測試來源；本輪重新跑 starting bounds/restart | 父端 starting timeout 修補在現行來源且選測綠；未再報歷史 bug |
| schema1 保留／新增 schema2、實體 map、未支援階段不可操作 | `sensor.py:12–117` 對照 Switch/Button unique ids／handlers；原生 wire 選測 | schema1／schema2 分離，10 Numbers、P3 capabilities=false、unsupported Switch unavailable |
| shipped Card events 對 map/domain/state/capability 再驗證、schema fail closed、v1 不致動 | 實讀根目錄 shipped JS `:175–211`，對照 backend wire 與原生 handlers；`:15–18,108–118,221–238`；Node 9/9 | Source 對接一致；不是跨層實測完成的宣稱 |
| P1 回歸保留 | 實讀四個 backend 窄適配 diff；原始 Card 16 個 browser methods AST source-identical，5 個 Node test 區塊 source-identical | 未見削弱原始案例；native 無輸出 fixture 原斷言仍在 |

## 本輪實際執行／證據核對

1. 隔離 native 選測：`test_p2_control.py test_p2_acceptance.py test_p2_wire.py test_p2_start_bounds.py test_p2_restart.py test_p2_options.py`，**46 passed，5 dependency deprecation warnings，9.21 秒**。
   - 使用 backend `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`，`PYTHONDONTWRITEBYTECODE=1`，basetemp 指向 scratch；沒有向 repo 寫 pytest cache／bytecode。
   - 原始 log：`C:/Users/ivanl/.hermes/cache/scratch/p2-spec-native-selected.log`。
2. 現行 shipped JS Node tests：`node tests/test_contract.cjs`，**9 passed / 0 failed**；Node experimental test runner warning。
3. Card `docs/evidence/p2-06-canonical-green/result.json`：9/9 Node、23/23 Chromium child returncode 全 0。程式驗算其中全部 9 個檔案的 SHA256 與現行 worktree 相同。**本輪沒有重跑 Chromium**，23/23 是已存在、已驗證來源吻合的紀錄，不冒稱本輪新跑。
4. backend 歷史 p2-41 的 137 pass + metadata 1 fail 不列現行缺陷。程式比較 p2-41 snapshot hashes 與現行：只有 `tests/test_boundaries.py` 不同；實讀差異確認其版本已改 0.2.0 並加入 P2 Options 欄位。其後已讀回父端 `docs/evidence/p2-42-parent-final-native/run.json` 與 `pytest.log`：returncode 0，**138 passed、無 skip，5 dependency warnings，44.14 秒**；其中 control.py 指紋與本輪被審來源相同。ruff/format/compile 通過由父端回報，本輪未另跑。
5. OFF Context 的額外獨立 native probe 如 SPEC-1；實際走真原生 handler 與假硬體。

## 父端整合交付尚需完成（不是新增 production 缺陷）

- 凍結契約 `:73` 的跨層 gate **已實測完成，非 pending**。已讀回父端 `docs/evidence/p2-bridge-native-01/receipt.json`，並確認 `tools/p2_bridge.py` 已存在：shipped JS SHA256 與本輪一致；真 Chromium 156.0.8078.4 的 10 次 UI 操作映射到 native Switch/Button handlers，記錄 8 次實際假硬體動作（4 組 ON/OFF）；high_water、normal_stop、emergency_reset、external_service_readback 全 true，page_errors 空，active_run=false，physical_device_test=false、external_ha_access=false。這是隔離 HA 真原生 handler／SwitchEntity 假硬體的跨層實測，**不是實機 HA 宿主或物理馬達驗證**；本輪讀回 receipt，沒有重跑父端橋接。此橋接不取代本輪另測的人類停止 Context 契約。
- 文件收尾由父端擁有：backend README `:77` 仍寫 P2 待實作、沒有任何輸出；Card README `:9,65` 仍只有 P1 不控制／schema1 文案。依契約 `:9,75`，正式交付前需區分舊監測模式與新 P2 原生控制，不能讓兩份 README 保持全面『不控制』宣稱。這是已知父端交付 gate，不要求 worker 越權改 README。
- exact-head CI／Issues／共同規範不在本輪唯讀 SPEC 審查完成範圍。不得因本報告關閉 Issue #2 或 P3–P5。

## 審查來源指紋

- backend `control.py` SHA256：`c371df31ac7d763bba1bb17b1feda1861613cbf8eda6305ea0cf243b88ded2a2`
- backend `services.py` SHA256：`5c9f03e5030609d7a607df97db50c772c1f0394933f2a78c12f6c396661fdd65`
- Card shipped JS SHA256：`04304bc0f62c5a26bbaa4a28018543a0ab46728e5148c44f1f2e221bb4a8d25f`

最終判定：**BLOCKED（SPEC-1 已具體重現）。其餘已讀契約範圍未發現第二個需修 production 違反；父端跨層 gate 與 native 138/138 全回歸已完成，文件／發布收尾仍由父端處理。**
