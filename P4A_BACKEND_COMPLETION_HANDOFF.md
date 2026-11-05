# P4a 後端必要補格完成（非審查批准）

- Native metadata 窄幅授權 regression 1/1；新補格28/28；fresh full-final **378/378，0fail/0skip**，明確335舊+15先前P4a+28補格，不將focused重複加總。
- 原生四服務 initial nonadmin/撤權在target lookup及catalog protected read前拒絕、等Tank.lock後撤權拒絕；disabled/unloaded全四服務；所有options不變。
- 兩個native已保存v5槽同名不同UUID、cross-target CRUD/Apply ID拒絕與CAS隔離；第二槽未commission、無共用output ownership。
- 原生API逐筆建立100筆，第100成功，第101 exact recipe_limit，完整options零寫。
- 四角色實際Start及pending dispatch/ACK拒Apply busy，accepted run_plan/options/IO不變；實際acquire lease及admission lock拒絕。既有queued Tank owner測試同full回歸綠。沒有指派running boolean。
- emergency_stop原生鎖fault後全settled允data Apply，fault/Enable/非recipe域保留、Apply零增IO/IRRfalse；普通Options/Number保持catalog，no-op revisions與last-applied偏離真值。
- 既有S5 native/browser join原腳本不改：exit0，13 native requests；native Store、新Card兩端CAS、terminal與真四stage。新fresh native terminal captures用owned路徑，無改歷史fixture。
- Production/tests與3個new owned tools Ruff check/format、compileall皆exit0。顯式actual-imports含路徑與SHA，source/build pre/post相等。Card companion為當前candidate完整拷貝。

## 修改與可稽核證據
- 新增 tests/test_p4a_completion.py；tests/test_boundaries.py在worker開始前已由父端窄幅加recipe_management，未再改。產品12檔與原BACKEND_FINAL完全相等；所有custom_components亦與joint-input-r1逐檔相等；本completion沒有product delta，不重開P3。
- 證據 ../_backend-completion-r1：FINAL.json、full-final/receipt.json/raw.log/actual-imports.json、joint-product-equivalence.json、raw6579-comparison.json、original6579-comparison.json與各lint/format/compile/cleanup原始log。
- completion-first 22pass/6fail、completion-corrected 25pass/3fail與首次lint/format失敗全部保留。它們是fixture/native初始化、dispatch signature/disabled-anchor、fault baseline與完整suggested Options提交的harness失敗，不冒稱production behavioral RED。只修新測試；未刪安全assert。
- 新run.py每次新snapshot/out、bounded child tree、exit propagation；原_backend-work/full-final2 349/1與原P4A_BACKEND_FINAL未覆。
- raw6579比較列明所有候選差異（真P4a/docs delta不稱全unchanged）；原兩庫另作逐檔raw SHA比對，結果見JSON。

## 尚待父端
最終input freeze→獨立SPEC→品質（目前0/2），父端P4a joint/UI gates另計。本報告不是整個P4完成、不代表approved或發布；沒有install/live/auth/stage/commit/push/tag/deploy。Owned pytest/bridge process cleanup exit0。
