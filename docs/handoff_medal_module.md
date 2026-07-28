# 交接文档：蚀刻章/奖章模块

> 用途：供**下一个对话（新设备、零上下文）**快速接手。本文自包含，新会话只需读它 + 仓库内相关文档即可继续。
> 生成时间：2026-07-27　·　分支：`dev`　·　基线提交：`16f0195`（其上 `ccff574` 是森空岛调研文档）

---

## 0. 一句话现状

终末地 QQ bot（`taikeladi/otae-bot-entari`，fork 自 `otae-1204`）的**蚀刻章/奖章模块已实现并推送到 `origin/dev`**，包含两个功能：

- **F1 版本对比**（全局）：`/zmd 奖章` 查总数+新增、`/zmd 奖章 刷新` 重抓滚动基线。
- **F2 个人缺章**（绑定账号）：`/zmd 奖章 缺章` 查未获得/未升满/未镀层。

**数据层逻辑已用真实 FZ 数据验证；渲染、全量抓取、F2 真实 SDK 调用尚未在 bot 环境跑通**——这是回家后首要验证/调试的部分。

---

## 1. 如何接手（新会话起步）

```bash
git pull origin dev        # 拉到 16f0195
```

阅读顺序（都在仓库内）：
1. 本文件（交接）
2. `docs/endfield_medal_stats.md`（需求与统计口径，已对齐实现）
3. `docs/skland_endfield_personal_api.md` + `docs/skland_endfield_ui_data_inventory.md`（F2 端点与字段来源）
4. `docs/fz_wiki_open_api_summary.md`（FZ 取数基础）

代码入口：`plugins/endfield/`（见 §3 文件地图）。

> 注：上个会话的计划文件留在原设备 `C:\Users\user\.claude\plans\vectorized-percolating-dahl.md`，**不在仓库里**，新设备没有；设计已沉淀到上面 §2 的需求文档，不需要那个计划文件。

---

## 2. 关键决策（已敲定，勿推翻）

| 决策 | 结论 | 理由 |
|---|---|---|
| 主数据源 | **FZ Wiki 权威**，Warfarin 次源/降级 | FZ 跟进官方客户端修正。实证：`achv_fac_coupon_wuling_5` Warfarin 仍是错误重名「·Ⅳ」，FZ 已修正「·Ⅴ」 |
| F1 刷新方式 | **手动双命令**（`奖章` 查看 / `奖章 刷新` 重抓） | 可控、不频繁打 FZ 源站；查看秒回 |
| 快照设计 | `current`/`previous` 双槽，JsonStore 落 `data/endfield/medal_snapshot.json` | 既是版本对比基线，也是避免每次命令实时抓 140 页的性能缓存 |
| 版本对比 | **id 集合差集**，不依赖版本号 | FZ 无 `meta.version`，用根条目 `updatedAt[:10]` 当标签 |
| F2 数据源 | 森空岛 `card/detail` 端点（**已确认**，非猜测） | 用户抓包提供的 `docs/skland_*` |

---

## 3. 文件地图与数据流

### 数据流
```
F1:  FZ roster(蚀刻章) + 140 单件详情 → service 解析 → 快照 → diff(对比 previous) → draw 图片
F2:  森空岛 card/detail → achieve.achieveMedals[] → {id: 进度} → ×快照交叉比对 → draw 图片
```

### 改动文件（commit `16f0195`）
| 文件 | 职责 |
|---|---|
| `plugins/endfield/sources.py` | fz/warfarin 的 `kinds` 加 `medal` |
| `plugins/endfield/models.py` | `MedalItemView`/`MedalSnapshotView`/`MedalDiffView`/`MedalProgressView`/`MedalMissingView` |
| `plugins/endfield/medal_store.py`（新） | `MedalSnapshotStore`：双槽快照，`asyncio.Lock`+`to_thread` 写盘，dict↔View 往返（**注意 level_counts 的 int 键经 JSON 会变 str，已处理**） |
| `plugins/endfield/service.py` | `_fz_medal_entry_attrs`/`_derive_medal_levels`/`build_fz_medal_item`/`build_fz_medal_snapshot_view`；`EndfieldService.fetch_medal_snapshot_fz`/`build_medal_diff`/`build_medal_missing_view`；`_parse_player_medal_progress` |
| `plugins/endfield/account_client.py` | `endfield_card_detail(account_token, role)`：`GET /api/v1/game/endfield/card/detail?roleId&serverId`，复用 `_signed_skland_request`（query 入签名） |
| `plugins/endfield/draw.py` | `draw_medal_stats_card`（F1）+ `draw_medal_missing_card`（F2），复用 `_draw_neutral_card` + gacha 分页范式 |
| `plugins/endfield/commands.py` | `MEDAL_ALIASES` 等 + `_parse_personal_command` 里的奖章分支 + 帮助文案 |
| `plugins/endfield/__init__.py` | `medal_store`/`_MEDAL_LOCK` 单例；`_handle_medal`（查看/刷新）、`_handle_medal_missing`（F2）；命令分发 |
| `tests/test_endfield_medal.py`（新） | 快照往返、diff、缺章交叉比对+截断 |
| `docs/endfield_medal_stats.md` | 需求文档（已改写为 FZ 权威+双源+F1/F2 规格） |

### 复用的既有范式（不要重造）
- HTTP+缓存：`utils/http_client.py:fetch_json`（`namespace="endfield-api"`，TTL 600s，信号量 8 自动限流）
- FZ 解析：`service.py` 的 `_fz_overview_entries`（roster）、`_ordered_fz_levels`、`_first_value/_first_text/_to_int/_fz_asset_raw_url/_clean_fz_rich_text`
- 渲染：`draw.py` 的 `_draw_neutral_card`、`_image_data_urls`（inline 图标）、`_is_gacha_height_limit_error`、`esc`/`esc_attr`
- 账号：`account_store.resolve_role/decrypt_token`、`ROLE_TASKS.claim`、`EndfieldRole`

---

## 4. 数据源结构（实测，准确）

### FZ Wiki 奖章
- **roster**：`GET /articles/by-title?ns=0&title=蚀刻章&withRevision=1` → 模板「蚀刻章一览」→ `roster.entries[]`，**140 条**，字段精简（name/title/categoryName/groupName/icon/plateable/desc，**无等级**）。
- **单件**：`GET /articles/by-title?ns=0&title=<entry.title>&withRevision=1` → 模板「蚀刻章·单件档案」→ `entry`（id/name/initLevel/**levels[]**/canBePlated/categoryId/categoryName/groupId/groupName/order/iconUrl/desc）。
- **推导（关键，FZ 无 maxLevel/canBeUpgraded 直字段）**：
  - `maxLevel = _ordered_fz_levels(levels)[-1].level`（≈ len(levels)）
  - `canBeUpgraded = len(levels) > 1`

### 森空岛 F2
- `GET /api/v1/game/endfield/card/detail?roleId=<id>&serverId=<id>`（签名 GET）→ `data.detail.achieve.achieveMedals[]`
- 每枚：`achievementData.id`（**32 位 hex 哈希，与 FZ 的 `achv_` 不同命名空间——本节早先写的「achv_，与 FZ/Warfarin 同命名空间」是错的**）/ `level` / `isPlated` / `obtainTs`
- **只有已获得的在列表里** → 不在列表 = 未获得，驱动交叉比对
- ⚠ **关联键更正（2026-07-27 实测，以 `docs/handoff_medal_f2_fix.md` 为准）**：id 命名空间不同，**不能按 id 关联**，F2 改按规范化 `name`（`_norm_medal_name`：去空白+去引号）交叉比对，实测 135/140 命中。原「按 id 关联」假设会导致 `owned` 恒为 0。

---

## 5. 验证状态（已做 / 未做）

✅ **已验证**（真实数据 + 独立脚本，上个会话）：
- FZ 单件解析+推导（多级「Delta救星」max=3/可升级；单级「武陵调度·Ⅴ」修正名）
- 全量快照管线（roster 140→title 匹配→聚合排序）
- `build_medal_diff`（首次空、新增、自比空）
- F2 交叉比对+截断（未获得/未升满/未镀层 + owned 计数 + limit//3 截断）
- 快照 level_counts int 键 JSON 往返
- 全部文件 `py_compile` 通过

⚠️ **未验证**（需 bot 环境跑）：
- **渲染输出**：两张图实际效果、高度超限时分页是否触发
- **F1 全量抓取**：140 页并发耗时、失败详情是否被优雅跳过
- **F2 真实 SDK 调用**：`endfield_card_detail` 签名 GET 能否拿 `code:0`、`achieveMedals[]` 解析是否吻合

---

## 6. 回家测试步骤（bot 环境，Python 3.10+）

```bash
git pull origin dev
pytest tests/test_endfield_medal.py            # 纯逻辑，无需网络/Playwright
# 跑起 bot 后：
/zmd 奖章 刷新      # 首次 ~15–25s，建 data/endfield/medal_snapshot.json
/zmd 奖章           # 读快照出图
/zmd 奖章 缺章      # 需已绑定账号 + 快照已建立
```

环境要求：
- Python ≥3.10（pyproject：<3.14）；依赖 `pip install -e .`
- Playwright 浏览器：`playwright install chromium`（渲染必需）
- `ENDFIELD_CREDENTIAL_KEY` 环境变量（账号 token 加密；跑抽卡/签到已有则不用动）
- F2 需先 `/zmd 绑定` 绑定账号

---

## 7. 已知坑点 / 调试提示

- **140 页抓取慢**：首次刷新 15–25s 属正常；查看命令读快照秒回。`_MEDAL_LOCK` 串行避免重入。
- **FZ 无 meta.version**：版本标签用根条目 `updatedAt[:10]`；diff 靠 id 差集。
- **level_counts JSON 键**：int 键落盘变 str，`_dict_to_snapshot` 已 `int()` 还原——若改快照结构别破坏这个。
- **同步 sqlite + async**：endfield 插件在 async 处理器里直接调同步 sqlite（既有模式），奖章快照用 JsonStore 同理。
- **签名 query 顺序**：森空岛要求 query 顺序/编码与签名一致；`_signed_skland_request` 用同一 `params` dict 构建 canonical 和 URL，roleId/serverId 是纯数字字符串，无编码歧义。若 F2 报签名错（code 10000），重点查这里。
- **首次快照无 previous**：`build_medal_diff(None)` 返回空 `new_medals`（设计如此，首版只展示总数）。

---

## 8. 待办（后续可选）

- 渲染调优：F1 新增奖章网格、F2 三段布局的视觉细节（首次跑通后按效果调）。
- Warfarin 降级适配器（FZ 宕掉时；当前只在 sources.py 注册了 medal，未接 Warfarin 解析）。
- FR-3「同 id 字段变更」UI 段（捕获官方修正，首版仅日志）。
- FZ 基线数值重测（`docs/endfield_medal_stats.md` §8 的 v1.4 数字是 Warfarin 实测）。
- 若考虑提 PR 到上游 `otae-1204`：先把本交接文档（`docs/handoff_medal_module.md`）删掉或移出。

---

## 9. 不要重复做的事

- 数据源探测、FZ/森空岛结构调研——已完成，结论在 §4 和 `docs/`。
- 上个会话已写并验证了：FZ 解析、diff、缺章交叉比对、快照往返。若测试发现 bug，是定向修复，不是重写。
- 决策（§2）已与用户确认，勿重新纠结。
