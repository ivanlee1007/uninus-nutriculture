# P3b 最後 Q successor 獨立 SPEC 重查

## Verdict：PASS（joint P3b SPEC；不是品質／發布批准）

原品質 Q-C1、Q-I1a、Q-I1b 的原始三個 assertions 在此 exact successor 全 PASS；再由 reviewer 選定 **invalid nutrient identity＋unknown ownership 不可 reset** 鄰界，合法其他 roles 獨立 OFF、replacement／foreign 零 OFF、aggregate running 保留、reset 拒絕且零新增輸出呼叫，亦 PASS。一般 N identity 損失仍走原 `stop_unconfirmed` 優先序。組合先前 SPEC 的不變覆蓋與已獨立核對的新 full-native 證據，批准本 exact candidate 的 joint SPEC；**原品質 REQUEST_CHANGES 不改寫、不追稱批准，仍需父端另開修後品質重查**。沒有自修碼，修補預算維持 2/2。

## 1. Exact source binding

- Root：`C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3b-review-q-successor`。
- MANIFEST SHA256：`a22f4988f6b26754a73a8185cd1e76bc1e6dacecb95f5e4a9f9fc458e1ded3c2`。
- `pre.json`／`post.json`：**175/175 declared files 前後完全相同，0 mismatch**；實體176檔含 MANIFEST，無額外／缺失檔。
- 相對 R1 successor，舊檔僅三個 production modules 改變：`control.py`、`nutrient.py`、`p3b_projection.py`；新增本輪 handoff、progress、5-case 永久品質回歸。無刪除。所有既有 tests、契約、Card、parser 與 fixture raw bytes 不變，見 `comparison.json`、`production.diff`。
- control.py：`bd5d86eaae396af67fa8bffb7cd08a553436dbf58591b691f0d08ec72e3c51ca`。
- nutrient.py：`d1534e865356f8776297dcb0e8945a1e8b96bb3ba61da24ff0b9e8950a30e509`。
- p3b_projection.py：`42aaf07b8655aac85e7f1a05de986f8e8da6e6e055546674dc388050aef7e4c7`。

已讀 frozen P3B_ACID_MIX_CONTRACT、修補 handoff、R1 SPEC 與原品質完整報告；依 emergency closure、不可觸碰 replacement、unknown 不得冒充停止、global S 高 pH 僅觀察及 native reasons 契約判定，而非以綠 summary 代替讀碼。

## 2. Production delta 判讀

1. emergency arm 先保存 immutable bindings／operations／owns_io，不 eager resolve 全部 acid/mix targets；既有 dispatcher 對各角色獨立驗 identity 並 OFF，不因一個 replacement 阻斷其他合法 owners。N owner 仍明確指向 nutrient_stage，R1 不回歸。
2. cleanup failed 僅保留明確 `emergency_stop` latch；一般 run identity／OFF 失敗仍覆寫為原 `stop_unconfirmed`。不採「保留任意舊 fault」的過寬修補。
3. schema4 observer 讀唯一 `safety_parameters`，支援 commissioned N／acid／mix；仍驗 active、finite、pH 單位、last_reported 新鮮度。無效或回落來源清除 timer／alarm；只 publish，不致動、不寫設定。v3 仍讀既有 dosing S。
4. S4 projection 由既有 reasons 加入生效 `ph_high_alarm` 並去重；沒有降級 schema、改 parser 或放寬舊 v3 控制契約。

## 3. 本輪真執行：27 PASS，5 upstream warnings，child exit 0，無 skip

| 範圍 | 實跑結果 |
|---|---|
| 原品質 Q-C1 | 原 `test_quality_boundary.py` byte-exact copy，所有原 assertions 不改；invalid idle acid 後 N／circ／refill 關閉，acid replacement／foreign 仍 ON 且零 OFF，bindings／revision 不變，emergency latch 持久。 |
| 原品質 Q-I1a／I1b | 原 acid-only 延時 alarm 與 N commissioned 升 v4 native Sensor reasons 兩獨立 assertions 全 PASS，零 I/O／options mutation。原 v2 probe 直接 bytecopy，不重用有 harness TypeError 的 v1。 |
| 永久新5 cases | invalid acid／circulation 各合法 owner closure、replacement 隔離、unknown／running truth；acid-only native reasons 恰1次、unknown／invalid pH unit 重設；N升v4保留告警；mix-only 在 EC／level unknown 時仍僅依健康pH告警、零 I/O／設定變動。 |
| reviewer 新鄰界 | 額外 invalid **nutrient**（非原 acid／circulation case）：其他三合法 roles 全 OFF；N replacement／foreign 不碰，N owns_io=true、acid/mix settled、aggregate running=true，native output_states nutrient=unknown。真 native reset_fault 拒絕，fault／running／revision不變、無額外輸出calls；`adjacent-reset.json`。 |
| R1 原3 cases | acid/acid、acid/circulation、mix/nutrient held-OFF ACK ownership／Context 與收束全部通過。 |
| 原 N I/O 全檔 | late ON、OFF failure、identity loss 等全部保留；舊 `test_removed_identity_never_sends_off_to_reused_foreign_name` 真執行，原 assert `fault == stop_unconfirmed` 通過。沒有修改舊 assert。 |
| native→shipped→native | acid/mix 各 aborted/fault/completed 六終態，實跑 Chromium shipped consumer，原 UI payload 回 registered native replay；六 receipts page_errors=[]、shipped SHA相符，Enable／Apply／reset無多餘硬體calls。mix completed沿既有61s logical-clock seam，不冒稱實等。 |

27 是本 child 的實際總數；不同 suite 的重疊數不得相加成 distinct total。

## 4. Cwd、fixtures、imports 與 receipts

原 backend venv 僅供 interpreter／HA SDK；cwd、config、PYTHONPATH、tests 全在 successor。真 fixture 的 conftest 由 snapshot custom_components 複製進新 OUT；`import-binding.json` 記錄27 cases，逐一讀回 actual imported module 路徑/hash，全與 successor 相符。**486 個實際 fixture-copy Python files** 亦逐檔 hash 相符。

Owned OUT：`C:/Users/ivanl/.hermes/cache/scratch/p3b-spec-q-recheck`。

`native-run.json` 保存完整 argv／env／cwd／elapsed／真 child exit。核心命令為 backend SDK `python.exe -B -m pytest -c <successor>/uninus-nutriculture/pyproject.toml -p no:cacheprovider -p conftest --basetemp <OUT>/pytest -vv -s`，選原兩品質 probes、新鄰界、永久品質5、R1三案、整個原N I/O檔及 role terminal wire。明設 `P3B_CARD_PYTHON` 與 installed `CHROMIUM_EXECUTABLE`。本輪 native child 耗時29.23s，pytest自報26.36s。

- native.log SHA：`001e9ac6e4c848c7665d4816c544b0c1accd4e52ebae61c9ecf307c668ebcde2`。
- 原兩品質 probes SHA：`12886201f4e5ae3677144d3d5cb4b1a472872ed20608b7cf78ca4b789008caf9`／`31452f1a4ad2666a00d8ec9e305ce183d69383135257d7603d2fb2f0a1151caa`，archive／執行副本相同；binding plugin 僅 ROOT overlay，OUT 自然由 __file__.parent 定位。見 `overlay-proof.json`。
- shipped JS SHA：`4d6615afa83d736677fcf8f8791c695dcbd92b22b0e9d9aeeb731e2d75ab41bd`；六 receipts 見 `browser-receipts.json`。
- `audit_review.py` 真執行 exit0；`audit.json` 保存完整 binding／artifact hashes。

## 5. 完整回歸與不變範圍 composition

- 不將舊290當修後 full-suite。改採父端 `p3b-q-repair-2/recovered-final-native-green` 的 **295 PASS／5 warnings／child0**，本輪未再跑 full suite。其 run SHA `8cdb71317532ea6f795c93bd8c11fb275bdf8d2608531120699ff5af17cd6bba`；raw.log SHA `1adb62bed8383c1977921f941d7ca449d1b4a09b6253a5b5f6eed11ddf5eb925`。
- 獨立驗235個 archived source snapshot files 全符該 run inventory；其中163個亦與 successor inventory raw 相符，**107個 production／test／tool／config／shipped 可執行範圍 inputs 與 current 相符**；295 distinct cases 的 actual loaded modules 全符 current bytes，pre/post frozen inventory相同。
- broad inventory **不是175 successor全同**：72項 mismatch 明列 `audit.json`，限進度文件內容更新、未納 successor 的 docs／歷史reviews／test-results；不影響被採用 native gate 的實際來源。未 byte-archive 的 requirements兩檔、demo HTML、Card兩 CJS tests／fixture、debug.cjs 六檔另列 `unarchived-unchanged.json`，只證 R1/current 不變，不聲稱它們有本次 native snapshot 證據。
- Node12/browser33 與 prior SPEC pending/remount/CAS 等 frontend 鄰界，沿已驗 actual-consumed equivalence 的既有 SPEC composition；Card／fixtures／tests raw全未改，prior browser probe/log hash另核對。這不是本輪重跑12／33，也不冒稱 prior broad inventory逐項都等於新manifest。
- R1 SPEC REPORT SHA `9e2f46f3f73290a85af6f2c9371ec56eb412b35185fe4e360cceb7dae2676bd1`；原品質 REPORT SHA仍 `919220b0b19c68c480337d3989cd394216f5043fa6625d59614f486cec5a6856`，其 REQUEST_CHANGES 歷史保留。

## 6. 誠實失敗／限制／交付

初次 docs lookup 少 backend 子目錄，唯讀not-found後定位正確；另一次嘗試讀不存在 Card native_wire.py，實際 consumer 已由 lifecycle test 證實為 backend tools/p3b_postrun_check.py。兩次 audit verifier-assumption failures 保留：第一次假設 requirements txt 有 archive；第二次擴 tools scope 後發現 frontend debug.cjs 亦未 archive。修正 **owned verifier 邊界**後成功；不是產品FAIL，未改原測試／source／log，未因修 verifier 而重跑pytest冒充。

沒有實機cutoff認證、原HA／憑證／外網、live bridge、無界身份矩陣或所有provider注入保證；時鐘 seam 僅證邏輯。未本輪重跑 lint／CI／Node12／browser33，沒有把父端綠 gate 虛稱本輪實跑。

新增檔全部限本 owned OUT（report、probes、archives、raw receipts、audit及fixture outputs），source175 pre/post不變。沒有執行一次性edit腳本、安裝、stage／commit／push／deploy，也沒有第三輪自修。**此 exact successor joint SPEC PASS，待獨立品質重查；未批准不得發布。** 原P3a已交付不變；P3c順序／合法重疊／relative／weekday／preview仍未完成，Issue3保持open。
