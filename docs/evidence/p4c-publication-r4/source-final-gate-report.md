# P4c final R4 凍結整合驗證

- 結果：GATE_PASS_WITH_HISTORICAL_QUALIFICATIONS；非 SPEC／品質批准。
- 全量 native：553/553 unique、82/82 modules；四個 round-robin shards，未重試，focused98/13SPEC 未重複計入。
- 四份 JUnit／collection／call reports union：True；各 shard 詳見 FINAL.json。
- Static check-only：True；Ruff lint/format、Python compile、JSON、全部 Card JS/CJS Node syntax。
- 原 suite 8 opt-in consumer 與六種 terminal：True，為同一全量 run，不另加總。
- 當前 native Core/shipped Card join：pass；Options Save/reopen/Cancel、registered private WS、physical Store/fresh-load/Card、四階段閉合、result GET/native attrs/Card 對照；provider 僅 native handoff，非外部送達。
- Card unit14／DOM91：沿用舊證據，未重跑；31個保守 executable/test/schema input superset 與原證據 hash 核對。
- 全 source 6660 files + 5 metadata pre/post hash／集合守衛：True。
- Manifest SHA256：c8432ecf9d9bdec0d091890af9f90466b4edf68e60f69ca0893e1723daa42ba3。
- Notification runtime：980aeed830f72e64facceb25feef2fba419a89f39686da7cf7e7af4c79092f02。
- Mix runtime：f0f3b5239941b91d23d0d58341153a0066b107fa65860ef8b861123da3dd9605。
- 所有輸出僅本 evidence；沒有改產品／原站、推送、release、部署或安裝。
- 歷史 M0 4秒 TimeoutError、readonly capture 違規、INSUFFICIENT 根因、invalid persistence RED 均保留；R5 凍結前 Ruff cache 事故不稱一直 readonly。
- 舊 G runner 準備縮排錯誤與 420 秒監控限制僅作歷史資格引用；本次從開始使用 tracked background。
- Runtime/auth/.storage/wire-local snapshots 不打包；closed artifact 清單見 CLOSED_ARTIFACTS.json。

## 最終封存補充

- Shards actual executed: [144, 116, 137, 156]；exit: [0, 0, 0, 0]。
- 當前 join completed + confirmed；provider 僅 handoff_returned，非外部送達。
- 真DTO/event/wire schema validation: 11；existing Hermes jsonschema，未安裝套件。
- 本次從開始使用 tracked background，僅觀察到的 ancestry 抽樣；不宣稱 continuous descendant monitor。
- 所有 runner／finalizer／controller 結束並關閉 logs 後封存。
