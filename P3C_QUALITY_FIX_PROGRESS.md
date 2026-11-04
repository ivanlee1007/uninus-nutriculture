# P3C quality fix — 授權第4/4輪

僅 Q1 explicit-condition source runtime health 與 Q2 proven closure 後 fresh-run cutoff。授權 receipt: C:/Users/ivanl/.hermes/cache/scratch/p3c-round4-authorization.json。不得第五輪、發布或修改契約/peer Card/根 baseline/舊 evidence。

## Checkpoint 0
- 已讀 quality REPORT.md / FINAL.json，兩項 Important，無 Critical。
- 起始候選 manifest 477bf2eb9102adeddf26cfb72b3d062ee67f83da5a71cca9711c442a173eddaf，198 files；將逐檔驗 baseline runtime/tests。
- 原 probes 預期 SHA256: quality 98ef93eab2ab8ff3473adff549e3416428db1502aa42cfc2b4a04e054dd11640；repeat 411f73296567514affe626b177ae5a17d6a0d1eca96ba1c905187dee6a36d830。
- 本輪 owned evidence 將位於本 repo 的 quality-round4/；每輪保留 source/test snapshot、child exit、完整 raw、actual imports 與閉檔 hashes。
- 待完成: native RED、最小修補、永久邊界 case、GREEN、full suite/static、handoff。尚無批准。

## Checkpoint 1 — native RED → focused GREEN
- 原六案 red-native: 真 child1，4 passed / 2 failed / 0 skip，Q1/Q2原assert失敗；raw SHA a3e2799f6bb0b9cb142b58f61a0cc54a4b546319f33c1a507b1e674a93b7c484。
- 新邊界 red-boundaries: 6 failed / 1 passed；健康閾值對照原已pass，不冒稱RED。Mix補充明示stale-field/logical-completion seam；原N保留真實C-F等待。
- green-focused: 真child0，13 passed / 0 skip；raw SHA 1979970dbcfb9cb1b6893082bbdfd0d38f365adac5230576d1068c27de13fdb9。
- production modified: flow.py（凍結每owner required sources / supervisor / fresh closed reset），flow_settings.py（current/captured共健康validator），control.py（captured event交supervisor），mix.py（dispatch/run健康檢查）。未變wire/契約。
- raw/source/actual imports: quality-round4/{red-native,red-boundaries,green-focused}/{raw.log,receipt.json,build/}。每run源snapshot前後一致、imports全owned；原198重新hash一致。
- 首次 red-original 在setup輸入掃描包含nativefixtures內既有venv而逾150s，未啟pytest、沒有raw，不能算RED。保留partial build；runner改為只掃源資料夾，nativefixtures依manifest複製，不複製venv。
- 最終format/full/static尚待；不得將focused GREEN當獨立批准。
