# P3c SPEC 修補第3/3輪
授權僅 I1–I4；不發布、不自行批准。已讀正式 REPORT/FINAL 與 §7。先將原四 sourcebound native 反例逐字複製到 owned build，保留 RED 前後來源與原始 probe。尚未修改 production。

I1/I2 native UI 主路徑已接通：round3-native-ui-green child0，2 passed。原四反例 round3-original-red 真 4 failed child1；來源副本/命令/原始log/imports均保留。新版星期僅 plan頁，legacy v5 settings writer 拒跨namespace。仍須鄰界和全回歸、獨立SPEC；尚未完成。

I3 runtime 反例已GREEN：round3-refill-green child0/1 passed；無可獨立達admission refill即level_unsafe，靜態Save仍接受。四前列錨點小pure規則供Preview共用。I4正接通，待focused/full。

I4及所有focused32真綠；首次full327跑完為326 passed/1 failed，唯一失敗是既有translations exact-set未納入新flow_plan入口。依授權必要相鄰assert擴充精確鍵集合並新增plan欄位exact-set；原失敗保留 round3-final-full，無產品新blocker。最後full重新fresh OUT。

交接完成：最終327 passed/0 skipped child0；Ruff .17.3 check/format0。auth確認原192和SPEC artifacts不變、70actualimports精確binding。原probe post仍1 fail（舊weekday欄位正確被拒），原始字節及失敗保留；適配新UI四反例與鄰界真綠。完整詳HANDOFF。待父端freeze→affected SPEC/S5join→quality，不發布、不第四輪。
