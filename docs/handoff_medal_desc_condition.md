# 交接文档：F1/F2 详情显示「描述 + 获取条件」+ 删 Lv（对齐 AKEData 样式）

> 用途：供下一个对话（新设备、零上下文）接手。本文自包含。
> 生成时间：2026-07-31　·　分支：`dev`
> 续 `docs/handoff_medal_layout_compression.md`（双列压缩）。本文聚焦：删 Lv 标签、每条详情新增 AKEData「描述 + 获取条件」、F2 按玩家状态选档、**字体配色对齐本地 `AKEDatabase` 工程**、token 重新绑定。

---

## 0. 一句话现状

F1/F2 每条蚀刻章详情：**删除 Lv1/2/3 标签**；新增两行——「描述」（黑 `#1e2b3c`）取自 AKEData `levelInfos[L].completeDesc`，「获取条件」（浅 `#5b6f86`）取自 `levelInfos[L].conditions[].desc`（去重合并、不显阈值——文本本身已含数字），**无彩色标签/边框**。配色与字号取自本地 `E:\code\AKEDatabase\theme\achievement.css`（`.level-desc` / `.level-conditions`）。F2 按状态选档：未获得→`init_level` 档、未升满→`real_level+1` 档、未镀层→镀层条件。token 重绑为 18435966071（大妖精Yousei）。测试 140 passed。

---

## 1. 字段映射 + 字体来源（描述/条件是两个不同字段，勿混淆）

| 卡片显示 | AKEData 字段路径 | AKEDatabase CSS class | 配色/字号 |
|---|---|---|---|
| 描述 | `entry.levelInfos[L].completeDesc`（text-id→i18n） | `.level-desc` | `#1e2b3c` 黑，1rem |
| 获取条件 | `entry.levelInfos[L].conditions[].desc`（去重 `；`连） | `.level-conditions` | `#5b6f86` 浅，0.9rem |
| （废弃）顶层描述 | `entry.desc` | — | 生产数据**恒空** |
| 镀层条件 | `entry.plateConditions[].desc` | — | samples **全空** |

**字体来源**：`E:\code\AKEDatabase\theme\achievement.css`。描述/条件均无 `font-family`（用默认无衬线），关键差别是**颜色 + 字号**；`.condition-item` 无边框/标签 → bot 同样不加彩色标记。`plugin/js/achievement.js`：`lvl.desc`→`.level-desc`，`lvl.conditions[]`→`.condition-item`（内有 `.progress-value` 蓝色显阈值，bot 不显）。text-id 经 `_i18n_text(i18n, {id,text})`→`i18n[str(id)]` 解析，`completeDesc`/`conditions[].desc` 均已实测可解析中文。

---

## 2. 改动文件清单

| 文件 | 改动 |
|---|---|
| `plugins/endfield/models.py` | `MedalItemView` 加 `condition: str`、`plate_condition: str`、`tier_desc: dict[int,str]`、`tier_cond: dict[int,str]`（全档文本，供 F2 选档）。snapshot 持久化自动包含（`medal_store` 用 `asdict`/字段集）。 |
| `plugins/endfield/service.py` | `from dataclasses import replace`；`build_akedata_medal_snapshot` 遍历 `levelInfos` 填 `tier_desc`(completeDesc) + `tier_cond`(conditions 去重) + `plate_condition`，默认 `description/condition` 取 `init_level` 档；`build_medal_missing_view` 未升满/未镀层用 `replace(...)` 按目标档复制。 |
| `plugins/endfield/draw.py` | `_medal_item_html` 删 `Lv{max_level}` 标签、加 `<div class="medal-desc">` + `<div class="medal-cond">`；`MEDAL_CARD_CSS`：`.medal-desc`(黑 `#1e2b3c`/13px/clamp3) / `.medal-cond`(浅 `#5b6f86`/12px/clamp2)，**无边框**（对齐 AKEData）。 |
| `data/_manual_test/.token_cache` | 重新绑定为 18435966071 → 大妖精Yousei。 |

---

## 3. F2 选档逻辑（`build_medal_missing_view`）

| 分组 | 判定 | 显示的档位/条件 |
|---|---|---|
| `not_obtained` | `info is None` | `init_level` 档（snapshot 默认即此档） |
| `not_maxed` | `can_be_upgraded and real_level < max_level` | `target = real_level + 1` → `replace(medal, description=tier_desc[target], condition=tier_cond[target])` |
| `not_plated` | `can_be_plated and not info.plated` | `replace(medal, description=tier_desc[max_level], condition=plate_condition or tier_cond[max_level])` |

> 用 `dataclasses.replace` 复制：同一章可能同时进 `not_maxed` 和 `not_plated`，直接改共享对象会后者覆盖；replace 各建副本。`real_level = info.level + init_level - 1`（沿用 `bugfix_medal_investigator_max_tier.md` 偏移修正）。

---

## 4. 验证（本次会话已做）

- **必须先 `奖章 刷新`**：旧 `medal_snapshot.json` 无 `tier_desc/tier_cond`；改代码后只有重建快照才有条件数据。已刷新（140 枚，版本 1.4）。
- F1：`data/_manual_test/medal_view_1785591946_1.png`（2560×3946，双列 23 条带描述+条件）。
- F2：`data/_manual_test/medal_missing_offline.png`（大妖精 136/140，未获得 4 + 未升满 1，2560×2332）。
  - 未升满「潜能解放奖章」→ 下一级条件；未获得「谷地调查者奖章」→「于四号谷地收集4份调查报告」（第 1 档）。
- 测试：`pytest tests/test_endfield_medal.py tests/test_endfield.py tests/test_endfield_visual.py` → **140 passed, 3 skipped**。
- 视觉确认：Lv 标签已删；描述黑色、条件浅灰蓝、条件前无边框/标签（对齐 AKEData）。

> F2 离线渲染：`PYTHONPATH=. .venv/Scripts/python.exe scripts/_dev_medal_missing_offline.py`（读最新 `card_detail_raw_*.json` + snapshot，不依赖 token/网络）。在线：`重查`。

---

## 5. 已知问题 / 待办

1. **未 push**：改动（models/service/draw + 本文档）需 `git add` 后 `git push origin dev`。
2. **未在真实 QQ/bot 环境跑通**：仅命令行验证。接手后在 bot 里 `/zmd 奖章 刷新` + `/zmd 奖章 缺章` 验一遍。
3. **字体已对齐** `AKEDatabase/theme/achievement.css` 配色（描述黑 / 条件浅 / 无边框）；如需更精细（`font-family`/字重）可再调。
4. **镀层条件 `plateConditions` 当前全空**：未镀层组暂显示 max 档描述 + 兜底条件；若 AKEData 日后补文本则自动显示。
5. **玩家当前进度值无法显示**：条件只显阈值（文本已含数值如「收集4份」），森空岛 `card/detail` 不提供当前进度（`handoff_akedata_migration.md` §5.6）。
6. **`奖章 刷新` 是硬要求**：任何人接手改了条件相关字段后，必须重新刷新快照，否则详情为空。

---

## 6. 相关文档

- `docs/handoff_medal_layout_compression.md`：上次会话（双列压缩 + 六边形档位 icon）。
- `E:\code\AKEDatabase\theme\achievement.css`：描述/条件字体与配色来源（`.level-desc` / `.level-conditions`）。
- `docs/handoff_akedata_migration.md` §5.6：conditions 阈值说明。
- `docs/bugfix_medal_investigator_max_tier.md`：`levelInfos` 结构样例（completeDesc / conditions / progressToCompare）。
