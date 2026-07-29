# 交接文档：奖章模块 md5-id 关联 + 数据源迁移到 AKEData

> 用途：供**下一个对话（新设备、零上下文）**接手。本文自包含。
> 生成时间：2026-07-29　·　分支：`dev`　·　HEAD：`ecd0e97`
> 续 `docs/handoff_medal_f2_fix.md`（那份的「按 name 关联 + suspect」方案**已被本文推翻**）。
> **本文为最新权威**；`handoff_medal_module.md` §4、`handoff_medal_f2_fix.md` 里关于 id/name 关联的陈述仅作历史。

---

## 0. 一句话现状

奖章模块两件事定稿：① 个人缺章（F2）关联键从 name 改回 **id**——但用 `md5(FZ/AKEData.medal_id) == 森空岛 hex`（实测 `森空岛 achievementData.id == md5(achv_id)`，115/115），精确、不受命名滞后影响，suspect 启发式已删；② 全量快照数据源从**易超时的 FZ Wiki 迁移到 AKEData**（游戏客户端 TableCfg，CDN 稳定，140 枚 2.5s 抓全）。代码 + 测试 + 文档均已提交本地，**尚未 push**。

⚠️ 本地 `dev` 领先 `origin/dev` **4 个提交**，未推送。`data/`（token/快照/dump/渲染图）被 gitignore，不会进仓库。

---

## 1. 本次已完成（4 个提交）

| commit | 类型 | 内容 |
|---|---|---|
| `7994732` | fix | F2 改 md5-id 关联；FZ 抓取 3 轮重试补丢页；图标下载重试；删 suspect |
| `d7d6a03` | docs | 新增 `skland_medal_id_mapping.md`；同步更正三份旧文档的 id 命名空间陈述 |
| `13ed27d` | feat | 奖章数据源迁移到 AKEData（新 `akedata_client.py` + 构建器 + 接线 + 2 测试） |
| `ecd0e97` | chore | 4 个调研脚本（档位/level 语义、AKEData 图标规则抓取） |

---

## 2. 核心发现（勿推翻，勿重复调研）

### 2.1 森空岛 hex = `md5(achv_id)`
- 森空岛 `card/detail` 的 `achievementData.id` 是 32 位 hex，等于 `md5(游戏 achv_id)`。FZ/Warfarin/AKEData 的 `achv_*` id 三源一致（FZ↔Warfarin 直接相等，AKEData 是客户端原表）。
- **F2 关联键**：`md5(FZ/AKEData.medal_id) == 森空岛 hex`。name 仅兜底（FZ 缺 achv_ id 时；实测基本不触发）。
- 验证：115/115 命中，且玩家 136 个 hex 全部能在这套 achv_ 里找到对应。
- 详见 `docs/skland_medal_id_mapping.md`（含调试脚本与复现一行式）。

### 2.2 「等级」语义（解释 app 与 API 的差异）
- **API `level`** = 玩家**当前档位**（icon 索引，1/2/3），森空岛返回的图标只含当前档及以下。
- **app「N级」筛选** = 奖章**固有/设计档位**（= FZ/AKEData 的 max_level），所有玩家一样。
- 两者不同概念。例：「苏醒」`level=1` 但属「3 级」章（单档、不可升，拿到即满）；「武陵调度·Ⅴ」「谷地调查者奖章」都因设计档位=3 出现在「3 级」筛选里。
- **「谷地调查者奖章」实测档位**（AKEData 客户端 `levelInfos` 权威）：`['2','3']`，可升级，initLevel=2，max=3；玩家停在 2（4 份调查报告），需 6 份升 3 → **确实未升满，判定正确**。FZ 与 AKEData 一致，无数据过期。

### 2.3 AKEData 数据架构（迁移后的主源）
- 站点域：`cf.akedata.top` / `www.akedata.wiki`；**数据 CDN**：`data.akedata.wiki`。
- `https://data.akedata.wiki/manifest.json` → `latest`（如 `1.4.4@8764515-7`）→ `versions[].tableCfgPath`（如 `public/1.4.4/8764515-7/TableCfg`）。
- 三张表（均 `<dataBase>/<tableCfgPath>/<Name>.json`）：
  - `AchievementTable.json`：140 枚，按 achv_ id 索引；`canBeUpgraded`/`canBePlated` 直字段、`initLevel`、`levelInfos`（逐档 `achieveLevel`+`conditions`）、`order`、`groupId`、`name`/`desc` 只有 text-id（`text` 空）。
  - `I18nTextTable_CN.json`：~13.8 万条 text-id→中文（**约 18MB，需把 fetch 的 `max_bytes` 提到 64MB**，默认上限 10MB）。
  - `AchievementTypeTable.json`：8 分类，含 `categoryName`(text-id)/`categoryPriority`/`achievementGroupData[]`(groupId+groupName)。
- **图标**（从站点 `v3-table-data.js` 反推）：`<dataBase>/public/images/assets/beyond/dynamicassets/gameplay/ui/sprites/medaliconbig/<achvId>_lv<NN>.png`，NN=maxLevel 零填充（lv01/02/03）。实测互异有效 PNG。
- 站点用 service worker（`/ake-sw.js`）只代理 `/public/images/...` 到数据域并加 `?v=sharedRevision`；`/public/CH/...` 预构建数据走 `akeFetch` 的 `resolveUrl`。**抓数据直接打 `data.akedata.wiki` 的表 JSON 即可，不要走站点 SW。**

---

## 3. 改动文件清单（相对 `handoff_medal_f2_fix.md` 基线）

| 文件 | 改动 |
|---|---|
| `plugins/endfield/akedata_client.py`（新） | AKEData 抓取：`fetch_akedata_manifest`/`fetch_akedata_medal_tables`；常量 `AKEDATA_DATA_BASE`/`AKEDATA_ICON_BASE`/`AKEDATA_HEADERS`；I18n 走 64MB 上限 |
| `plugins/endfield/service.py` | `_i18n_text`；`build_akedata_medal_snapshot`（achv_id 当 medal_id、name/desc 按 text-id、levelInfos→max_level、图标路径、type→category/group）；`fetch_medal_snapshot_akedata`；F2 关联改 md5-id + name 兜底；`fetch_medal_snapshot_fz` 加 3 轮重试；删 `_base_name`/`_ROMAN_SUFFIX` |
| `plugins/endfield/models.py` | 删 `MedalMissingView.suspect_names` |
| `plugins/endfield/draw.py` | 删 suspect 渲染 + CSS；`_prepare_assets` 图标下载加 3 轮重试（解决「无图」） |
| `plugins/endfield/__init__.py` | `_handle_medal` 刷新改走 `fetch_medal_snapshot_akedata` |
| `tests/test_endfield_medal.py` | md5-id 用例（含命名撞名回归、name 兜底）+ AKEData 构建用例（字段 + md5 关联）。**14 passed** |
| `scripts/_dev_medal_repl.py` | 刷新改 AKEData；FZ 客户端超时 30s |
| `scripts/_dev_*.py`（新 4 个） | `_dev_medal_levels`/`_dev_recheck_level`/`_dev_two_medals_cmp`/`_dev_akedata_icons`：档位/level/图标调研 |

---

## 4. 关键决策（已敲定）

- **主源 = AKEData**（CDN 稳、字段直、achv_ 主键）。FZ 代码（`fetch_medal_snapshot_fz` 等）保留为**可选降级**，但默认不再走。
- **F2 按 md5-id 关联**，name 兜底；**suspect 启发式删除**（精确判定后不需要猜测）。
- **图标用 maxLevel 那档**（`_lv<NN>` 里 NN=maxLevel）。如需按当前档显示，要改 `_prepare_assets` + 视图（目前快照只存单 icon_url）。
- I18nTextTable 18MB，抓取频率 = `奖章 刷新`（不频繁），可接受。

---

## 5. 已知问题 / 待办

1. **未 push**：本地 `dev` 领先 `origin/dev` 4 个提交。`git push origin dev`。
2. **未在真实 QQ/bot 环境跑通**：仅命令行 REPL 验证（无 Satori 协议端）。接手后首要在 bot 里 `/zmd 奖章 刷新` + `/zmd 奖章 缺章` 验一遍。
3. **`sources.py` 仍为 fz/warfarin 注册了 medal kind**：奖章快照不走 `source_order`（直接调 `fetch_medal_snapshot_akedata`），该注册已属冗余，可清理（低优先）。
4. **FZ 降级路径长期可删**：AKEData 在生产稳定一段时间后，可移除 `fetch_medal_snapshot_fz` 与 FZ 单件解析，精简代码。
5. **Warfarin 奖章适配器仍缺**：仅注册未实现（与本次无关，沿用旧 TODO）。
6. **「未升满」展示可增强**：目前只显等级；可加「Lv2/3 · 4/6 调查报告」进度（AKEData `levelInfos[].conditions[].progressToCompare` 有进度阈值，但玩家**当前进度值**森空岛 `card/detail` 不提供，只能显示阈值）。
7. **玩家账号实测**（2026-07-28，角色「大妖精Yousei」）：136/140，未升满 2（谷地调查者奖章、潜能解放奖章），未镀层 0，未获得 4（山中见犼/暗夜战术/奇境探索者/六方巧境，均活动章）。武陵调度专家奖章·Ⅴ 经 md5-id 确认**已拥有**（森空岛误标·Ⅳ）。

---

## 6. 如何接手（新设备，零上下文）

```bash
git pull origin dev          # 拿到 ecd0e97（或 push 后的 origin/dev）
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
.venv\Scripts\python.exe -m pip install pytest pytest-asyncio
# .venv\Scripts\python.exe -m playwright install chromium   # 渲染默认用系统 Edge，可选

pytest tests/test_endfield_medal.py            # 应 14 passed

# 命令行手动测试（无需 QQ）
PYTHONPATH=. .venv\Scripts\python.exe scripts/_dev_medal_repl.py 奖章 刷新   # AKEData，~2.5s 建 140 快照
PYTHONPATH=. .venv\Scripts\python.exe scripts/_dev_medal_repl.py 奖章         # 读快照出 F1 图
PYTHONPATH=. .venv\Scripts\python.exe scripts/_dev_medal_repl.py 奖章 缺章    # F2（交互选登录方式）
PYTHONPATH=. .venv\Scripts\python.exe scripts/_dev_medal_repl.py 重查         # 用缓存 token 重查
```

环境：Python ≥3.10（<3.14）。F2 需森空岛账号（手机号验证码登录）。token 缓存在 `data/_manual_test/.token_cache`（gitignore）。

---

## 7. 调试脚本（`scripts/_dev_*.py`）

| 脚本 | 用途 |
|---|---|
| `_dev_medal_repl.py` | **主力**：命令行测 F1/F2（刷新/查看/缺章/发码/手机登录/重查） |
| `_dev_medal_smoke.py` | 离线 FZ 抓取+渲染、F2 mock 渲染（仍走 FZ，离线用） |
| `_dev_id_compare.py` | FZ↔Warfarin achv_ id 对照（证两源同命名空间） |
| `_dev_hex_vs_achv.py` | 森空岛 hex ↔ FZ achv_ 并排（md5 关系） |
| `_dev_two_medals_cmp.py` | 「苏醒」「谷地调查者」森空岛 vs FZ 原始数据对比 |
| `_dev_medal_levels.py` | FZ `levels[]` 原始档位（谷地系列） |
| `_dev_recheck_level.py` | 用缓存 token 查指定章当前 level/initLevel/图标 |
| `_dev_verify_view.py` | 打印 `build_medal_missing_view` 三段 + 潜能章状态 |
| `_dev_akedata_icons.py` | playwright 抓 AKEData 图标 URL 规则（一次性，规则已固化进代码） |

`data/_manual_test/card_detail_raw_*.json` 是玩家 dump（敏感，gitignore）；`.token_cache` 是 token。

---

## 8. 不要重复做的事

- **不要按 name 做主关联键**——命名滞后会撞名（武陵·Ⅳ/·Ⅴ实证）。name 仅兜底。
- **不要拿 achv_ 与 hex 直接比相等**——它们是 md5 关系（115/115）。
- **不要从站点 `cf.akedata.top/public/CH/...` 抓数据**——走 SW，直接打 `data.akedata.wiki/<tableCfgPath>/*.json`。
- **不要怀疑「谷地调查者奖章」的未升满判定**——AKEData 客户端 `levelInfos=['2','3']` 权威，玩家在 2/3。
- **AKEData 图标规则已知**——`medaliconbig/<achv>_lv<NN>.png`，勿重新扒。
- **FZ 抓取慢/丢页是已知**——已加 3 轮重试；且默认源已是 AKEData，FZ 仅降级。

---

## 9. 相关文档

- `docs/skland_medal_id_mapping.md`：md5 关系 + 三源对比 + 调试方法（**权威**）。
- `docs/endfield_medal_stats.md`：需求与统计口径（§6 已改为 md5-id）。
- `docs/handoff_medal_module.md` / `docs/handoff_medal_f2_fix.md`：历史交接（id/name 关联陈述已过时，顶部有更新注指向本文/`skland_medal_id_mapping.md`）。
- `docs/skland_endfield_ui_data_inventory.md` §4.7：森空岛 `achieve` 字段结构。
