# 交接文档：奖章等级图标 + AKEData 取数指南

> 用途：供下一个对话（新设备、零上下文）接手。本文自包含。
> 生成时间：2026-07-29　·　分支：`dev`
> 续 `docs/handoff_medal_version_diff.md`（版本对比）与 `docs/handoff_akedata_migration.md`（数据源迁移）。本文聚焦本次会话**新增**：等级分布横条图标、三档图标生成、AKEData 取数指南。

---

## 0. 一句话现状

本次会话完成 4 块工作，均已提交到 `dev`（待 `git push origin dev`）：

1. **蚀刻章版本对比修复**（源和源历史版本对比）——详见 `handoff_medal_version_diff.md`，已验证（1.4 相较 1.3 新增 23 枚）。
2. **F1 等级分布横条用图标替代 Lv1/Lv2/Lv3 文字**——当前实现：FZ 蚀刻章剪影 + CSS `mask` 按等级改色（`draw.py::_medal_grade_icon`）。
3. **AKEData 取数指南**——`docs/akedata_data_access_guide.md`（给朋友/自己用，覆盖各模块取表/解析/图标）。
4. **三档奖章图标生成工具 + 成品**——`scripts/_process_medal_icon.py` → `参考图/medal_grade_{1,2,3}.png`（深灰/银白/金）。

⚠️ **唯一待办（等用户）**：用户会提供新 icon 用于改 F1 横条版式。届时把 `_medal_grade_icon` 从「FZ 剪影 mask 改色」改成「按 level 加载三档 PNG（或用户的新 icon）」。详见 §2。

---

## 1. 本次改动文件

### 1.1 蚀刻章版本对比修复（详见 `handoff_medal_version_diff.md`）

| 文件 | 改动 |
|---|---|
| `plugins/endfield/models.py` | 新增 `MedalBaselineView` |
| `plugins/endfield/akedata_client.py` | `_get` 透传 `ttl_seconds`；新增 `game_version_label` / `pick_previous_game_version` / `fetch_akedata_achievement_table`（历史版本长 TTL） |
| `plugins/endfield/service.py` | `fetch_akedata_baseline`；`build_medal_diff` 第二参改 `MedalBaselineView`；`version_label` 用 major.minor；加 loguru |
| `plugins/endfield/medal_store.py` | previous 滚动槽 → baseline 槽（`replace_baseline` / `load_baseline_view`），清旧 previous 残留 |
| `plugins/endfield/__init__.py` | `_handle_medal` 刷新抓 baseline、查看用 baseline |
| `tests/test_endfield_medal.py` | store/diff 用例改 baseline；新增 `AkedataVersionSelectTest`。**17 passed** |
| `scripts/_dev_medal_repl.py` | 刷新/查看同步 baseline；帮助文案 FZ→AKEData |

### 1.2 F1 等级分布横条图标（`draw.py`）

- `_medal_grade_icon(level)`：用 FZ 蚀刻章剪影（`assets/image/endfield/medal_grade.png`，白色单色+透明）作 **CSS `mask`**，`background-color` 按等级变色（1 深灰 / 2 银 / 3 金）。
- `_medal_level_bar`：用图标替代 `Lv{lv}` 文字（F1 统计卡 + F2 缺章卡都生效）。
- mask 的 data URL **懒加载**（`_local_image_data_url` 定义在文件后段，模块级直接调会 `NameError`，首次用时才读）。
- `assets/image/endfield/medal_grade.png`：FZ Wiki 侧边栏蚀刻章图标（`assets.fz.wiki/.../353f4a000fd50d9c.png`，676 字节，52×56）。
- 顺带改了 F1 卡片文案：页脚「数据来源 FZ Wiki」→「AKEData」、空基线「首次快照」→「暂无更早版本」。

### 1.3 文档 + 工具

- `docs/akedata_data_access_guide.md`：AKEData 取数指南（manifest→版本→表→I18n→图标，含各模块速查表 + 完整 Python 示例）。
- `docs/handoff_akedata_migration.md`：上一会话遗留（untracked），本次一并提交。
- `scripts/_process_medal_icon.py`：三档奖章图标生成（去加号 + 改色 + 高光 + 阴影）。
- `scripts/_dev_akedata_*.py`（6 个调研脚本）：表清单 / 字段结构 / 图标规则 / 历史版本对比 / 通用图标探测 / 版本选择。
- `参考图/`：用户素材（`deco_medal_rare.webp` 原始六边形+加号、`SeaTalk_IMG_…` 游戏统计截图）+ 三档成品（`medal_grade_{1,2,3}.png`）+ `medal_grade_clean_preview.png`。

---

## 2. 待办：F1 横条接入三档 / 新 icon

用户会提供新 icon 改版式。接入方式：

- `draw.py::_medal_grade_icon(level)`：从「FZ 剪影 + CSS mask 改色」改成「按 `level` 加载 `参考图/medal_grade_{level}.png`（或用户给的新 icon）」，用 `_local_image_data_url(Path(...))` inline 成 `<img>` 或 background-image。
- `max_level` 只有 1/2/3 三档，正好对应三档图；超出档位兜底用第 3 档。
- 可保留当前 FZ mask 版作 fallback（图缺失时降级）。
- 接入后重新渲染验证：`PYTHONPATH=. .venv/Scripts/python.exe scripts/_dev_medal_repl.py 奖章`。

> 当前未接入三档，是用户明确说「图片渲染先放一放，之后直接提供 icon 用于改版式」。

---

## 3. 三档图标生成（`scripts/_process_medal_icon.py`）

**输入**：`参考图/deco_medal_rare.webp`（白色剪影：六边形 + 右上角加号，160×148）。

**流程**：
1. **去加号**：连通块分析——加号是独立 864px 块、六边形主体是 9786px 最大块；保留最大块，加号自动脱落，六边形一个像素不动。
2. **平涂基色 + 右下高光**：整体平涂 `base×FILL`（调亮）；只在右下实心图案区（`diag = y/H + x/W ≥ 1.0`）叠加 `base×HIGHLIGHT`，左上镂空区不渐变；**1 级不做高光**。
3. **边缘薄阴影**：右侧 + 右下侧 K=3px 内阴影，`×SHADOW_FACTOR`。

**当前参数**：`FILL=0.92, HIGHLIGHT=1.10, SHADOW_FACTOR=0.78, K=3`
**颜色**：1 深灰 `(95,97,105)` / 2 银白 `(210,214,222)` / 3 金 `(240,200,82)`

改 `grades` / 参数后重跑 `python scripts/_process_medal_icon.py` 即可重生成。

---

## 4. 关键结论（勿重复调研）

- **akedata 没有「通用三档档位图标」**。奖章图标 = `medaliconbig/<achvId>_lv<NN>.png`（每枚奖章每个档位一张；单档章只有 `_lv01`，`_lv02/_lv03` 是 404）。
- **akedata 通用奖章图标** = `itemiconbig/item_achievement_icon.png`（在 `ItemTable` 的 `iconId`，**不在 `AchievementTable`**；256×256 彩色金属六边形，无档位变体，不易改色）。
- **FZ 侧边栏蚀刻章图标** = `assets.fz.wiki/7176bae51d7523a6/353f4a000fd50d9c.png`（白色单色剪影，适合 CSS mask 改色）——从 FZ 首页 HTML 的侧边栏配置 `{"id":"medals","gameIcon":"..."}` 翻出来的。
- `deco_medal_rare.webp`（用户给的三档素材源）是白色剪影，加号是独立连通块（与六边形不连通）——所以去加号只需保留最大连通块。

---

## 5. 验证（本次会话已做）

- `pytest tests/test_endfield_medal.py` → **17 passed**。
- `_dev_medal_repl.py 奖章 刷新` → `基线 1.3(117 ids)`；`奖章` → `相较 1.3 本版本新增 23 · 版本 1.4`。
- 三档图标：PIL 验证加号残留 0、六边形 9786px 完整、高光差（1级 +3 无 / 2级 +41 / 3级 +30）；图像分析确认颜色与高光达标。

---

## 6. 相关文档

- `docs/handoff_medal_version_diff.md`：版本对比修复（源和源）权威交接。
- `docs/handoff_akedata_migration.md`：数据源迁移 + md5-id 关联权威交接。
- `docs/akedata_data_access_guide.md`：AKEData 取数指南。
- `docs/endfield_medal_stats.md`：需求与统计口径（§3 FR-3 / §4 已更新为源和源 + baseline）。
