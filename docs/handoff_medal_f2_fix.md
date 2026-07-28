# 交接文档：F2 缺章 bug 修复 + 渲染增强

> 用途：供**下一个对话（新设备、零上下文）**接手。本文自包含。
> 续 `docs/handoff_medal_module.md`（那份是实现交接，但其 §4「id 共享 achv_ 命名空间」是**错的**，以本文件为准）。
> 生成时间：2026-07-27　·　分支：`dev`　·　基线提交：`ad56b06`

> **✅ 更新（2026-07-28）**：本文 §0/§4 原标「代码未提交」，**现已落库**——逻辑修复在 `7248b8b`（fix(endfield): F2 奖章缺章改按 name 关联），本文档+样例图+调试脚本在 `2bca98b`。`git pull origin dev` 即可拿到全部改动，工作区干净。下文「未提交」字样保留作历史记录。
>
> **⚠ 更新（2026-07-28，更重要）**：本文核心方案「**按 name 关联 + suspect 启发式**」**已被推翻**——实测发现森空岛 `achievementData.id == md5(achv_id)`（115/115），F2 已改回**按 `md5(FZ.medal_id)` 关联**，suspect 启发式已删除。详情见 **`docs/skland_medal_id_mapping.md`**（权威）与 `docs/endfield_medal_stats.md` §6。本文「id 命名空间不同、不能按 id 关联」「按 name 关联 135/140」「suspect」等陈述仅作历史记录。

---

## 0. 一句话现状

上个交接的奖章模块，**F2 真实 SDK 实测发现核心 bug**：森空岛 `achievementData.id` 是 hex 哈希、FZ 是 `achv_` 语义 id，**命名空间不同**，原「按 id 关联」假设错误，导致 F2 恒输出 `owned=0`（所有章都判未获得）。**已修复为按 name 关联**（实测 135/140 命中），并按用户反馈加了等级分布显示 + 调度券命名 bug 的「可能已拥有」标注。

⚠️ **代码修改 + 本文档 + 样例图都在工作区，尚未 git commit。** 接手前请先确认这些改动到位（见 §5）。

---

## 1. 本次已完成

| 项 | 结果 |
|---|---|
| 部署环境（venv + 依赖 + pytest） | ✅ Python 3.10.11 |
| §5 渲染输出验证 | ✅ F1/F2 出图正常 |
| §5 F1 全量抓取验证 | ✅ 140 枚 / 13s，数值与基线吻合 |
| §5 F2 真实 SDK | ✅ **发现 id 命名空间 bug → 改 name 关联 → 验证 owned 135/140** |
| 命令行手动测试工具 | ✅ `scripts/_dev_medal_repl.py`（无需 QQ 协议端） |
| 用户需求①：等级分布 | ✅ F1/F2 都加 Lv1/2/3 数量条 |
| 用户需求②：调度券·Ⅴ 命名 bug | ✅ 标 ⚠「可能已拥有」（启发式） |
| 用户需求③：潜能奖章定位 | ✅ name 关联修复后，潜能解放奖章正确归到「未升满」 |

---

## 2. 改动文件清单（工作区未提交）

| 文件 | 改动 |
|---|---|
| `plugins/endfield/service.py` | 新增 `_norm_medal_name`（去空白+去引号）、`_base_name`+`_ROMAN_SUFFIX`（去罗马后缀，用于 suspect）；`_parse_player_medal_progress` **从按 id 改为按规范化 name 索引**；`build_medal_missing_view` 按 name 关联，并填充 `level_counts` + `suspect_names` |
| `plugins/endfield/models.py` | `MedalMissingView` 新增 `level_counts: dict[int,int]` 与 `suspect_names: set[str]` |
| `plugins/endfield/draw.py` | 新增 `_medal_level_bar`+CSS（等级条）；`_medal_item_html` 加 `suspect` 参数（⚠ 标注）；`_medal_section_html` 加 `suspect_names`；F1 `_draw_medal_stats_page` 与 F2 `draw_medal_missing_card` 都插入等级条，F1 总数 tile 的 small 文案改为「各等级分布见下方」 |
| `tests/test_endfield_medal.py` | `test_cross_reference_categories` 的 `raw_progress` 改用 `achievementData.name`（id 故意写成 hex 风格，验证按 name 而非 id 关联） |

`pytest tests/test_endfield_medal.py` → **10 passed**。

---

## 3. 关键事实 / 决策（勿推翻，勿重复调研）

- **F2 不能按 id 关联**：森空岛 `achievementData.id` 是 32 位 hex（如 `99b08fcb...`），FZ 是 `achv_xxx`。原 `handoff_medal_module.md` §4「id 与 FZ/Warfarin 共享 achv_ 命名空间」**错误**。
- **按规范化 name 关联**：`_norm_medal_name` = 去全部空白 + 去首尾中英文引号。实测 135/140 命中（森空岛 135 枚全在 FZ 找到）。
- **FZ 无 hex id**：FZ 单件 entry 16 字段（`id/desc/name/order/levels/groupId/iconUrl/groupName/initLevel/categoryId/canBePlated/categoryName/plateIconUrl/applyRareEffect/noObtainCanView/plateConditions`），`id` 仅 `achv_`。→ **id 根治不可行**（已用 `scripts/_dev_fz_inspect.py` 确认，勿重查）。
- **调度券·Ⅴ 命名 bug**：鹰角客户端已修正为·Ⅴ（FZ 跟进），但**森空岛滞后仍标·Ⅳ**，与 FZ 真·Ⅳ 撞名。靠 name 无法区分用户是升到·Ⅴ 还是停·Ⅳ。当前用 **suspect 标注**（启发式：未获得的章若系列名＝去罗马后缀的 name 出现在玩家进度里，标⚠「可能已拥有」），**只标注不改变判定**。
- **测试方式**：用户本机无 QQ 协议端（Satori），用户选择**命令行手动测试**（`_dev_medal_repl.py`），不走 QQ。协议端路线暂搁置。

---

## 4. 已知 bug / 待办（用户说「很多 bug，明天修」）

1. **suspect 假阳性**：同系列用户有低级章时，未拥有的高级章也会被标「可能已拥有」。目前仅标注不误判，可接受；要更准需逐枚核对那 5 枚未获得。
2. **5 枚未获得**（用户账号实测）：`武陵调度专家奖章·Ⅴ`(命名 bug，实际可能有) + `“山中见犼”`/`“暗夜战术”`/`“奇境探索者”`/`“六方巧境”`(4 枚活动章，`plate=True`，**大概率真未获得，待用户确认**)。
3. **渲染视觉**用户未最终确认。样例图：`docs/medal_missing_sample.png`（F2）、`docs/medal_stats_sample.png`（F1）。
4. **代码未提交 git**（service/models/draw/test + 本文档 + 样例图 + 调试脚本）。
5. 原 `handoff_medal_module.md` §4 / 需求文档 `endfield_medal_stats.md` §2.1 里「id 共享 achv_ 命名空间」错误陈述**未更正**。
6. 用户提到的「干员潜能奖章」已定位为**潜能解放奖章**（max=3 可升级，森空岛 lv=2），name 关联修复后正确归到「未升满」——已解决，非 bug。

---

## 5. 如何接手（新设备，零上下文）

```bash
git pull origin dev
# ⚠ 若 §2 的代码改动未提交，新设备拉不到 —— 需从原设备先 commit，或手动同步工作区

python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
.venv\Scripts\python.exe -m playwright install chromium   # 可选；渲染默认用系统 Edge，装了更稳
.venv\Scripts\python.exe -m pip install pytest pytest-asyncio

# 逻辑测试（无需网络/浏览器）
pytest tests/test_endfield_medal.py            # 应 10 passed

# 离线验证 F1 抓取+渲染、F2 mock 渲染
.venv\Scripts\python.exe scripts/_dev_medal_smoke.py

# 命令行手动测试（交互）
.venv\Scripts\python.exe scripts/_dev_medal_repl.py
# > 奖章 刷新      # F1 全量抓取 ~13s，建/滚动对比基线
# > 奖章           # F1 查看统计图（读快照秒回）
# > 奖章 缺章      # F2：交互选 1.粘贴token / 2.手机号验证码 / 3.缓存重查
# > 发码 <手机号>           # F2 手机号方式第一步
# > 手机登录 <手机号> <验证码>  # 第二步，换 token 并查缺章（token 缓存到 data/_manual_test/.token_cache）
# > 重查                     # 用缓存 token 重查（调试用，不再发码）
```

环境要求：Python ≥3.10（<3.14，勿用 `py` 默认的 3.14）。F1 不需任何配置；F2 需森空岛账号（手机号验证码登录，无需 `.env`/`ENDFIELD_CREDENTIAL_KEY`，token 仅内存+本地缓存）。

---

## 6. 调试脚本（`scripts/_dev_*.py`，未提交，可重建）

| 脚本 | 用途 |
|---|---|
| `_dev_medal_repl.py` | **主力**：命令行手动测 F1/F2（交互+单次模式，token 缓存+重查+诊断 dump） |
| `_dev_medal_smoke.py` | 离线一次性验证 F1 抓取+渲染、F2 mock 渲染 |
| `_dev_match_check.py` | FZ vs 森空岛 name 匹配率（读本地 snapshot+dump） |
| `_dev_verify_view.py` | 打印 `build_medal_missing_view` 的 suspect/三段/潜能章状态 |
| `_dev_inspect2.py` | 调度券 level + 未匹配项详情 |
| `_dev_fz_inspect.py` | FZ 单件 entry 字段（已证无 hex id） |

注：这些脚本在原设备 `scripts/` 未提交。`data/_manual_test/card_detail_raw_*.json` 是用户奖章 dump、`.token_cache` 是用户 token，**敏感**，gitignore 不会进仓库。

---

## 7. 用户测试账号（实测数据，2026-07-27）

- 手机号 `18435966071`，角色「**大妖精Yousei**」
- 已获得 **135/140**，未升满 **2**（谷地调查者奖章、潜能解放奖章），未镀层 **0**
- 未获得 5：武陵调度·Ⅴ(⚠命名bug) + 山中见犼/暗夜战术/奇境探索者/六方巧境

---

## 8. 不要重复做的事

- FZ 是否有 hex id —— 已确认**没有**（`_dev_fz_inspect.py`）。
- 按 id 关联 F2 —— 已证不可行，用 name。
- §5「渲染 / F1 抓取」验证 —— 已通过。
- 重新纠结 F2 数据源 —— 森空岛 `card/detail` 已确认（签名 GET 通过，返回 136 枚 achieveMedals）。

---

## 9. 相关文档

- `docs/handoff_medal_module.md`：F1/F2 实现交接（基线，但其 §4 id 命名空间陈述过时）
- `docs/endfield_medal_stats.md`：需求与统计口径（§2.1 id 命名空间陈述需更正）
- `docs/skland_endfield_ui_data_inventory.md` §4.7：森空岛 achieve 字段（`achieveMedals[]` 含 `achievementData.name/id/level/isPlated`）
