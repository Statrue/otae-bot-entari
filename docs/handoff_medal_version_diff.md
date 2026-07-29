# 交接文档：蚀刻章版本对比改为 akedata 源和源历史版本对比

> 用途：供下一个对话（新设备、零上下文）接手。本文自包含。
> 生成时间：2026-07-29　·　分支：`dev`
> 续 `docs/handoff_akedata_migration.md`。本文为版本对比（F1）机制的**最新权威**。

---

## 0. 一句话现状

F1 版本对比的 bug 已修：原先靠本地 `current`/`previous` **滚动基线**（刷新时旧 current 滚入 previous），换稳定 akedata 后 previous 恒为同版本数据 → diff 恒空、几乎永远显示不出新增。现改为 **akedata 当前版本 vs 上一游戏版本**（源和源），刷新时抓取并存盘，查看秒回。

---

## 1. 关键发现（勿重复调研）

- **akedata 历史版本直接可得，无需问作者**：`manifest.json` 的 `versions[]` 保留多个版本（实测 5 个游戏版本 × 若干 revision），CDN 上各版本 `<tableCfgPath>/AchievementTable.json` 都可访问。
- **版本粒度 = major.minor**（id 前两段，跟着游戏大版本走）：`1.4.4@…` / `1.3.3@…` / `1.2.5@…` / `1.1.9@…` / `1.0.14@…` 去重为 1.4 / 1.3 / 1.2 / 1.1 / 1.0。「上一版本」= manifest 中第一个 major.minor 与 latest 不同的条目（跳过同 major.minor 的多个 revision，如 1.4.4 的 -5/-6/-7）。
- **实测对比**（AchievementTable 的 achv_id 集合差集，跨版本只增不减）：
  - 1.4(140) vs 1.3(117) = 新增 23、移除 0
  - vs 1.2(106) = 新增 34；vs 1.0(71) = 新增 69
- **数据量**：AchievementTable 175KB、TypeTable 4KB、I18n 17MB（仅刷新抓）；奖章图标 400×400 PNG 每张 625KB、全量 85MB，但 F2 每次只拉「缺的几枚」（实测 ~6 枚 ≈ 3.75MB），F1 新增约 23 枚 ≈ 14MB。

---

## 2. 改动文件

| 文件 | 改动 |
|---|---|
| `plugins/endfield/models.py` | 新增 `MedalBaselineView`（version / version_id / ids / fetched_at） |
| `plugins/endfield/akedata_client.py` | `_get` 透传 `ttl_seconds`；新增 `game_version_label`、`pick_previous_game_version`、`fetch_akedata_achievement_table`（历史版本默认 7 天长 TTL） |
| `plugins/endfield/service.py` | 新增 `fetch_akedata_baseline`（manifest → pick_previous → AchievementTable → id 集合，失败返回 None 不阻塞 current）；`build_medal_diff` 第二参改 `MedalBaselineView \| None`；`fetch_medal_snapshot_akedata` 的 version_label 改 major.minor；加 loguru logger |
| `plugins/endfield/medal_store.py` | 移除滚动 previous 与 `load_previous_view`；新增 `replace_baseline` / `load_baseline_view`；`_persist_current` 顺手清理旧 previous 残留；快照结构 `current` + `baseline` |
| `plugins/endfield/__init__.py` | `_handle_medal` 刷新抓 baseline、查看用 baseline |
| `plugins/endfield/draw.py` | 空基线文案「首次快照」→「暂无更早版本」；页脚「数据来源 FZ Wiki…」→「AKEData（游戏客户端 TableCfg）」 |
| `scripts/_dev_medal_repl.py` | 刷新/查看同步 baseline；帮助文案 FZ→AKEData |
| `tests/test_endfield_medal.py` | store/diff 用例改 baseline；新增 `AkedataVersionSelectTest`（label + pick_previous）。**17 passed** |

---

## 3. 关键决策（已敲定）

- **源和源对比**：版本对比两方都是 akedata 版本数据（current = 当前版本，baseline = 上一游戏版本），口径一致、准确。不再掺本地滚动快照。
- **仅对比上一游戏版本**：本次不做「对比任意历史版本」命令（列为后续可选）。
- **不做奖章图标磁盘缓存**：按需拉即可（F2 只拉缺的几枚）。
- **baseline 仅存 achv_id 集合**：抓 175KB 的 AchievementTable 即可，**不抓 18MB 的 I18n**（新增章名字/图标取自 current）。
- **FZ 降级死代码保留**：待 akedata 生产稳定后再删（见 `handoff_akedata_migration.md` §5.4）。

---

## 4. 验证（已通过）

- `pytest tests/test_endfield_medal.py` → **17 passed**。
- `PYTHONPATH=. .venv/Scripts/python.exe scripts/_dev_medal_repl.py 奖章 刷新`：
  `已抓取 140 枚 · 基线 1.3(117 ids) · 耗时 2.6s`
  `总数 140 · … · 相较 1.3 本版本新增 23 · 版本 1.4`
- 落盘 `data/endfield/medal_snapshot.json` 顶层 keys = `["current", "baseline"]`（无 previous）。
- 交叉核验：`scripts/_dev_akedata_history_diff.py` 算 latest(1.4) vs 1.3.3 = 新增 23，与 diff 一致。
- bot 环境（待跑，需 Satori）：`/zmd 奖章 刷新` → `/zmd 奖章`。

---

## 5. 不要重复做的事

- **不要恢复本地 `previous` 滚动基线**——akedata 稳定，滚动 diff 恒空（这正是本次修复的 bug）。
- **不要按整个三段版本号（1.4.4）界定「上一版本」**——同 major.minor 的 revision 间蚀刻章不变，必须按前两段 major.minor。
- **不要给 baseline 抓 I18n（18MB）**——只需 AchievementTable 的 achv_id 集合。
- **不要把版本对比的一方换成本地快照**——用户明确要求源和源对比，结果更准确。

---

## 6. 相关文档

- `docs/endfield_medal_stats.md` §3 FR-3 + §4：版本对比需求与快照设计（已更新为源和源机制）。
- `docs/handoff_akedata_migration.md`：数据源迁移到 akedata 的权威交接（F2 md5-id 关联、I18n/图标规则）。
- `scripts/_dev_akedata_history_diff.py`：akedata 历史版本对比的实证脚本（对比 latest 与各历史版本 id 差集）。
