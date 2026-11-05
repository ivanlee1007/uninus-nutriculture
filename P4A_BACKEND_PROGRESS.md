# P4a backend checkpoint

更新：原生 Options CRUD/Apply/Cancel/二次確認刪除已可用；full-final2 為350 collected、349pass/1fail/0skip（exit1），唯一 frozen metadata exact-set 待 parent 授權加入 recipe_management 預期鍵。完整交接見 P4A_BACKEND_HANDOFF.md / P4A_BACKEND_FINAL.json。下列保留首個 API 早checkpoint，非最新未完清單。

首條真 native registered Save(return_response=False) → options catalog → response get → 原子 Apply → 10 Number/S5 讀回已可操作；唯一更新 listener 觀察一次 commit、fake hardware calls 均零。

- 行為 RED: `_backend-work/red-human-save2` 真保存後 catalog 仍 0 筆，exit1。
- GREEN: `_backend-work/green-save-apply2` 1 collected/1 passed，exit0。
- 保存 exact build source/tests + command/raw/exit；fixture修正失敗另存，不充當 RED。
- 已變動: manager.py, services.py；新增 recipes.py、tests/test_p4a_recipes.py。
- 未完成: Options完整CRUD/Cancel/二confirm、刪除service、ACL/CAS/busy邊界、shutdown新程序、full335、lint；目前非完整交付/非approved。
- 無publish/commit/deploy/network；Card使用immutable baseline companion，非newCard整合。
