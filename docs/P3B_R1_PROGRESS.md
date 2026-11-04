# P3b R1 修補 1/2 進度

狀態：首 GREEN 已達成，3/3 native permanent regressions PASS（p3b-r1-green-2，child exit0）。RED 原 3 FAIL 保留；第一次最小 arm-only patch 仍 3 FAIL，找到 nutrient_dispatch 無 stage 時仍選 active owner，Controller 中一併改為明確 nutrient_stage 後 GREEN。未動 nutrient.py。原 probe + 兩 role terminal wire 已完成：6/6 PASS，child exit0；原雙 held ACK 不改 assertions，N 均 prompt OFF，foreign 保持 ON；hot/C-F 仍 PASS；六個 browser child 通過 unchanged assertion，shipped JS hash 未變。完整 native 兩次均 290 PASS / 0 skip / 5 upstream deprecation warnings / child exit0（原287+新增3，與 focused/probe 不相加）；p3b-r1-full-bound 加 read-only loaded-module hash binding，每 case 留存實際 imported modules 清單，不宣稱 broad inventory 是每 case 都實消費。尚未 SPEC 重查，禁止發布。

範圍：僅 isolated-development backend control.py、永久 regression 與本文件/handoff；不改 stage/schema/parser/contract/demo/Card JS。根因：emergency N arm 使用 active execution_stage，acid/mix 已 owns_io 時跳過真正 nutrient owner。

驗收：真 Options all commission、四個不同 Registry output、合法 mix_duration=1 min、singleEligible；保留原 acid/circulation held ACK 反例，另測 active mix；每 known role prompt OFF、獨立 pending truth、foreign 零 OFF。原 probe byte exact archive + ROOT/OUT-only execution overlay；native 完整回歸與兩 role terminal wire。證據目錄：C:/Users/ivanl/.hermes/cache/scratch/p3b-r1-repair-1。

P3a 不重開；P3c 完整編流程未完成，Issue3 不關。待 SPEC PASS 才交父端品質 gate。
