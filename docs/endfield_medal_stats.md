# 终末地蚀刻章统计功能需求文档

> 分支：`dev`
> 创建时间：2026-07-26　·　最近修订：2026-07-27（纳入 FZ Wiki 数据源与两个最终功能）
> 性质：需求与统计口径文档，作为已实现功能的规格说明

## 1. 背景与目标

蚀刻章（奖章）数据由两个第三方同人 Wiki 提供，二者都基于官方数据：

- **FZ Wiki**（`api.fz.wiki`）—— **权威主源**。会跟进官方客户端对数据的修正。
- **Warfarin Wiki**（`api.warfarin.wiki`）—— 次源 / 降级备选，提供单次全量接口。

> **为什么 FZ 更权威（实证）**：`achv_fac_coupon_wuling_5` 一枚，官方曾因命名错误把它和 `·Ⅳ` 重名，后修正为 `·Ⅴ`。**FZ 已跟进为「武陵调度专家奖章·Ⅴ」**，Warfarin 仍停留在错误的「·Ⅳ」（2026-07-27 实测）。两源共享 `achv_` id 命名空间，差异主要体现在同 id 的字段值上——FZ 反映官方最新修正，Warfarin 可能滞后。

本模块提供两个面向用户的功能：

- **F1（全局·版本对比）**：查当前版本蚀刻章总数；对比上一版本找出**新增**蚀刻章；输出图片（总数 + 新增详情）。
- **F2（个人·绑定账号）**：通过森空岛 SDK 查询自己**未获得 / 未升满 / 未镀层**的蚀刻章；输出详情图，缺过多则只显示部分。

> 本文不涉及具体渲染实现细节，仅对齐需求口径、数据源、字段映射与统计规则。

## 2. 术语与数据源

- **蚀刻章**：指奖章数据。游戏内分类字段写作「奖章」，本文统一称「蚀刻章」。
- **主数据源（FZ）**：
  - 总览（roster）：`GET /articles/by-title?ns=0&title=蚀刻章&withRevision=1` → 模板「蚀刻章一览」→ `roster.entries[]`（约 140 条，**仅含名称/分类/图标，无等级信息**）。
  - 单件详情：`GET /articles/by-title?ns=0&title=蚀刻章/<分类>/<名>&withRevision=1` → 模板「蚀刻章·单件档案」→ `entry`（含 id / levels / canBePlated 等，**贴近客户端表**）。
  - FZ 无 `meta.version`；版本标签用根条目 `article.updatedAt[:10]`。
- **次数据源（Warfarin）**：`GET /v1/cn/medals` 一次返回全量扁平结构（含 `maxLevel` / `canBeUpgraded` 直字段）。当前仅注册为降级源，解析主走 FZ。

## 2.1 字段映射

| 视图字段 | FZ 单件来源 | Warfarin 来源（降级） | 统计用途 |
|---|---|---|---|
| `medal_id` | `entry.id`（`achv_*`） | `data[].id` | 版本对比主键 |
| `name` | `entry.name` | `data[].name` | 展示（FZ 值更权威） |
| `category_name` | `entry.categoryName` | `data[].categoryName` | 分组 |
| `group_name` | `entry.groupName` | `data[].groupName` | 可选分组 |
| `init_level` | `entry.initLevel` | `data[].initLevel` | 口径说明 |
| **`max_level`** | **推导**：`levels` 末项的 `level`（≈ `len(levels)`） | `data[].maxLevel`（直字段） | **FR-1 计数依据** |
| **`can_be_upgraded`** | **推导**：`len(levels) > 1` | `data[].canBeUpgraded`（直字段） | **FR-2** |
| `can_be_plated` | `entry.canBePlated`（bool） | `data[].canBePlated` | **FR-2** |
| `order` | `entry.order` | `data[].order` | 排序 |
| `icon_url` | `entry.iconUrl`（补 `@raw`） | `data[].icon` | 展示 |
| `description` | `entry.desc` | `data[].desc` | 展示 |

> **推导规则（关键）**：FZ 单件档案没有 `maxLevel` / `canBeUpgraded` 直字段，需从 `entry.levels[]` 数组推导：
> - `effective_max_level = max(level["level"] for level in levels)`（实践中等于 `len(levels)`）
> - `can_be_upgraded = len(levels) > 1`
>
> 已实测：多级章「Delta救星」(levels=1/2/3) → max=3、可升级；单级系列章「武陵调度专家奖章·Ⅴ」(levels=[3]) → max=3、不可升级。

## 3. 功能需求

### FR-1　蚀刻章总数与各等级统计

**需求**：统计蚀刻章总数，以及每个最高等级的蚀刻章数量。

**计数口径（关键）**：每枚蚀刻章一律按其**最高等级 `max_level`** 归类计数。

- **理由**：可升级与多等级蚀刻章升级后低等级形态消失，仅保留最高等级形态。总数与各等级分布都应以「最高等级」为准。
- 定义：`effective_level(medal) = medal.max_level`（FZ 由 `levels` 推导）。

**输出**：总数 + 各等级（Lv1 / Lv2 / Lv3 …）数量。

### FR-2　可镀层 / 可升级蚀刻章统计

**需求**：分别统计：
1. 可镀层蚀刻章：`can_be_plated = true`；
2. 可升级蚀刻章：`can_be_upgraded = true`。

> F1 图片中以统计数字呈现；F2 进一步用于个人「未镀层 / 未升满」判定。

### FR-3　版本对比：筛选新增蚀刻章

**需求**：当数据更新后，对比新旧快照，筛出**新增**蚀刻章。

**机制**：
- 本地维护 `current` / `previous` 两槽快照（见 §4）；
- 以 `medal_id` 为主键做集合差集：**新增** = current 中存在、previous 中不存在的 id；
- **首次快照无 previous 时，新增列表为空**（仅展示总数统计，「新增」语义需要上一版本）。

**同 id 字段变更（官方修正捕获，可选/首版仅记录）**：同 `medal_id` 但 `name` / `max_level` / `can_be_plated` 等发生变化的记录（即官方修正，如「武陵调度专家奖章·Ⅳ→Ⅴ」）。以 FZ 为准时，这类变更可被检测；首版仅记日志，UI「变更」段后续迭代。

## 4. 数据快照设计

快照文件：`data/endfield/medal_snapshot.json`（运行时产物，已 gitignore）。

- 结构：`{"current": {version, fetched_at, source, medals[...]}, "previous": {...} | null}`；
- **刷新机制（手动双命令）**：
  - `奖章 刷新`：重新抓取 FZ（roster + 全部单件详情，约 140 次请求，首版约 15–25s）→ 旧 current 移入 previous → 新数据写入 current；
  - `奖章`：直接读 current 快照（秒回，不触网）；
- diff 靠 id 集合差集，**不依赖版本号比较**；version 字段仅作展示标签。
- 写盘串行（`asyncio.Lock`），避免并发刷新互相覆盖。

## 5. 命令

| 命令 | 行为 |
|---|---|
| `/zmd 奖章` | 读快照，输出蚀刻章总数 + 各等级/分类统计 + 本版本新增详情（首次快照则提示「已建立，暂无新增对比」） |
| `/zmd 奖章 刷新` | 重抓 FZ 数据、滚动基线，再输出对比图 |
| `/zmd 奖章 缺章 [账号]` | F2：查询绑定账号未获得 / 未升满 / 未镀层（**待接入 SDK 端点，见 §6**） |

## 6. F2 个人缺章

**需求**：通过森空岛查询玩家自己的蚀刻章进度，与全量快照交叉比对，得出：
- **未获得**：快照中有、玩家进度中无该奖章（**按规范化 `name` 关联，非 id**——见下「数据来源」）；
- **未升满**：玩家持有但 `can_be_upgraded` 且当前 `level < max_level`；
- **未镀层**：`can_be_plated` 且玩家未镀层。

**截断口径**：三段合计过多时（默认 > 30）各段截断保留前若干，置 `truncated=True`，图顶提示「缺章过多，仅展示前 N 枚」。

**数据来源（已确认）**：`GET /api/v1/game/endfield/card/detail?roleId=<id>&serverId=<id>`（森空岛签名 GET，query 入签名）。奖章进度在 `data.detail.achieve.achieveMedals[]`，每枚含 `achievementData.id`（**32 位 hex = `md5(achv_id)`**）/ `level` / `isPlated`。**只有已获得的奖章出现在列表中**——不在列表即未获得。

> **关联键（2026-07-28 定论，以 `docs/skland_medal_id_mapping.md` 为准）**：森空岛 `achievementData.id` = **`md5(游戏 achv_id)`**，与 FZ 的 `achv_*` 经 md5 一一对应（实测 115/115，且能解释玩家全部 136 枚进度）。**F2 按 `md5(FZ.medal_id) == 森空岛 hex` 关联**（精确，不受命名滞后影响）；FZ 条目缺 `achv_` id 时回退按规范化 name。
>
> *历史*：早先以为两源 id 不相关、改按 name 关联（135/140 命中，靠 suspect 启发式补「武陵·Ⅴ」）——但 name 会被命名滞后击穿（武陵·Ⅳ/·Ⅴ 撞名）。改 md5-id 后 owned 136/140、未获得 4（仅活动章），suspect 启发式已删除。

## 6.1 跨源关联实现

- `_parse_player_medal_progress`：解析森空岛响应，返回 `(按 hex id 索引, 按 name 索引)`。
- `build_medal_missing_view`：对每枚 FZ 章，`md5(medal_id)` 查 hex 索引（主），缺 achv_ id 时按 name（兜底）。
- 静态元数据（最高等级、可升级、可镀层）以 FZ 为准，森空岛只提供玩家进度（level/isPlated/在不在列表）。

## 7. 验收标准

- **FR-1**：给定 medals 数据，输出总数及按 `max_level` 分组的各等级数量，各等级之和等于总数。
- **FR-2**：正确输出 `can_be_plated` 与 `can_be_upgraded` 两类数量。
- **FR-3**：给定 current 与 previous，正确输出新增蚀刻章；首次快照（previous 为空）新增为空；同一份数据与自身对比新增为空。
- **F1 命令**：`奖章 刷新` 能抓取并落盘；`奖章` 读快照秒回且不触网；二次刷新后 previous 已建立、无更新时新增为空。
- **F2**（待端点）：mock 小/大进度数据，三段分类与截断正确。

## 8. 基线数据（v1.4，Warfarin 实测，2026-07-26）

> 以下数字为 Warfarin `/cn/medals`（v1.4）实测，仅作历史参考。FZ 与 Warfarin 总数一致（均为 140），但 FZ 字段值更权威；**FZ 版各等级 / 可镀层 / 可升级计数在实现后由快照重测**，届时以 FZ 数据为准。

- 总数 140；按 `maxLevel` 分布：Lv1 = 24、Lv2 = 58、Lv3 = 58
- 可镀层 = 29；可升级 = 22
- 分类（依 `categoryPriority`）：章节 25 / 技艺 31 / 地区 26 / 锤炼 8 / 建设 24 / 社交 4 / 活动 9 / 奇想 13

## 9. 非目标 / 暂不实现

- 按 `categoryName` 的等级分布统计图（数字已在快照中，可作后续扩展）。
- FR-3 同 id 字段变更的 UI 展示段（首版仅日志）。
- Warfarin 作为奖章源的解析适配（仅注册为降级；FZ 宕掉时再加适配器）。
