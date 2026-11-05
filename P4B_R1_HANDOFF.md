# P4B R1/2 A/B 修復交接

僅兩案限定修復；不是完整 SPEC / quality APPROVED，不發布、不部署。

## 變更
- `custom_components/uninus_nutriculture/quality.py`：health 直接回報 regressed latch 的 allowlisted `sample_regressed`，DTO 自原權威顯示 invalid；不清 latch、不放寬恢復。
- Registry 不再用 guard()/closure_pending 當相關性；按本槽來源、entry-owned Registry identity、配置綁定 output registry_id／已捕獲 entity_id 與 rename 前身份辨認。保留 remove 後 row=None 的外整合 output 關聯與即時撤銷；guard 仍負責閉合／未知 identity 拒許可。
- 新 `tests/test_p4b_r1_regression.py` 11 cases：sequence 前進、單來源倒退鎖存與不可自恢復；無關 Registry create/update 在 preterminal 與 granted 鄰近不改 epoch/candidate/window；外整合實際 bound output remove/disabled/rename/unique identity replacement 即時 revoke、不復活；source/permit/quality Registry loss。

## 實跑
- `_repair-r1/red-original` 原 A/B＋完整四 stage 正例：2 failed /1 passed，exit1，0skip；原斷言原樣。
- `_repair-r1/red-neighbors`：5failed/6passed。其中 A、B 與 bound output rename 是業務反例；兩 source ID collision 是新 fixture 問題，絕非產品 RED。
- `_repair-r1/green-focused`：27passed/2failed；兩者均 source fixture 遙測未恢復，已保留。
- `_repair-r1/green-neighbors-final`：原17＋新增11＋正例1＝29passed，exit0，0skip。
- `_repair-r1/full-final` 單進程遭工具420秒上限中斷，沒有 XML/receipt，不算綠。
- 最終完整回歸由不重疊四分片執行：88＋89＋138＋117＝432 distinct PASS、0fail/error/skip，四child exit0。404既有＋17原父端＋11新增；不是把focused重複加總。
- Ruff check、format --check、compile 三項 exit0，見 quality-checks.json。format前bytes在 pre-format。

## 來源與證據
精確 command/cwd/exit/XML/log SHA 在各 run receipt.json；source-pre.json＋SOURCE 保存實際bytes，run.py為入口。FINAL.json 有 G→snapshot overlay map、SourceImport probe 與四loop SHA。G全6617檔逐一hash符合；D的declaredsource唯一差異為quality.py。原17／原26與其他test assertions未動；Card、wire、P3 loops不改。所有運行配置/cache/runtime均在owned；SDK唯讀。未封存.storage/auth或open stdout。舊 evidence 不覆寫。

Shard0/2的原receipt source_post_equal=false 是owned CWD新增測試JSON artifacts；FINAL核實182個原輸入全部未改，新增檔列明。verification-interim亦含路徑分隔符比較問題，僅供原始診斷，最終以FINAL normalized結果為準。

## 邊界
真HA Core/native services/state/registry＋原fakehardware與既有mix domain-clock seam，非實機。不是完整多槽P5；held-OFF/foreignlease、two-slot、disable/unloadFail、outputidentity完整矩陣及完整SPEC/quality仍待獨立檢查。父端須凍結successor並重跑Card/native join；不可把其他worker消費G的舊結果冒稱新quality bytes。P4a/P3既有審查不重開。本次未存skill，因owned外寫入禁令。
