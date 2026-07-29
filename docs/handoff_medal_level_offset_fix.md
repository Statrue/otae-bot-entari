# 交接文档：F2 个人缺章「森空岛 level 偏移」修复 + 页脚换源

> 用途：供下一个对话（新设备、零上下文）接手。本文自包含。
> 生成时间：2026-07-30　·　分支：`dev`
> 续 `docs/handoff_grade_icon_and_guides.md`。本文聚焦本次会话：F2 等级横条 / 未升满判定的档位偏移修复、渲染图页脚换 AKEData、以及一份完整根因文档。

---

## 0. 一句话现状

F2 个人缺章卡的「等级横条计数偏 1 + 谷地调查者奖章误判未升满」已修。根因是**森空岛 `level` 字段对 `initLevel>1` 的章存在偏移**（实际档位 = `skland level + initLevel - 1`），不是 AKEData 的问题——AKEData 全程正确。`谷地调查者奖章` 是全游戏唯一一枚 2→3 升级章（`initLevel=2`），故只有它触发。代码 + 测试 + 根因文档均已提交本地，待 push。

---

## 1. 本次已完成

| 项 | 内容 |
|---|---|
| F2 档位偏移修复 | `build_medal_missing_view` 引入 `real_level = info.level + init_level - 1`；等级横条按 `real_level` 分档，未升满判定改 `real_level < max_level` |
| 渲染图页脚换源 | F2 缺章卡 / F1 统计卡 页脚 `FZ Wiki` → `AKEData`（去掉「游戏客户端 TableCfg」字样，只留 AKEData） |
| 根因文档 | 新增 `docs/bugfix_medal_investigator_max_tier.md`：完整数据对比（AKEData + 大妖精/信翼两份 live + 对照组）+ 偏移规律 + 修复说明 |
| 清理过时交接 | 删 `docs/handoff_medal_module.md`、`docs/handoff_medal_f2_fix.md`（已被后续交接推翻） |
| 测试 | `pytest tests/test_endfield_medal.py` → **18 passed**（新增 `test_init_level_offset_for_2_to_3_medal`） |

---

## 2. 核心发现（勿推翻，勿重复调研）

### 2.1 森空岛 `level` 对 `initLevel>1` 的章偏移
- 森空岛 `level` 从 1 开始计。`initLevel=1` 的章：`level` 即实际档位（1灰/2银/3金）。
- `initLevel=2` 的章：`level` 比实际档位**小 1**。**实际档位 = `level + initLevel - 1`**。
- 实证（两账号 live 样本，均 `initLevel=2`）：
  - 大妖精Yousei 金色（升满）：`level=2` → 实际 3。
  - 信翼 刚获得银色：`level=1` → 实际 2。
- 推论：图标槽位也随 `initLevel` 前移——`initIcon`=实际 `initLevel` 档、`reforge2Icon`=实际 `initLevel+1` 档……故 `谷地调查者奖章` 的 `reforge3Icon` 为空**不代表 max=2**（那是实际第 4 档，本就不存在），它真实 max=3。

### 2.2 全游戏只有「谷地调查者奖章」受影响
- 它是唯一「从 2 级升到 3 级」的章（`initLevel=2` 且可升到 3）。其余可升级章要么 1→2、要么 1→2→3，`initLevel` 都是 1，无偏移。
- 所以历史上只有它会被「直接拿 `level` 比 `max_level`」误判。

### 2.3 AKEData 全程正确
- `谷地调查者奖章` AKEData `levelInfos` = `{2, 3}`、`initLevel=2`、`canBeUpgraded=true` → `max_level=3`，与游戏一致。**F1 统计卡 / 全量快照无需改动**；图标 `_lv03.png` 亦正确。
- 旧交接 `handoff_akedata_migration.md` §2.2 说该章「max=3、确实未升满」——max=3 对，但「未升满」是拿偏移过的 `level=2` 误判，实际已升满。

> 完整数据与对比见 `docs/bugfix_medal_investigator_max_tier.md`（权威）。

---

## 3. 改动文件清单

| 文件 | 改动 |
|---|---|
| `plugins/endfield/models.py` | `MedalProgressView` 加 `init_level`（`achievementData.initLevel`） |
| `plugins/endfield/service.py` | `_parse_player_medal_progress` 记 `init_level`；`build_medal_missing_view` 用 `real_level = level + init_level - 1` 分档 + 判未升满；等级横条改为按「账号已拥有」统计（不再用全量快照总数） |
| `plugins/endfield/draw.py` | F2 缺章卡页脚「元数据：FZ Wiki」→「元数据：AKEData」；F1 统计卡页脚同步精简为「数据来源 AKEData」 |
| `tests/test_endfield_medal.py` | `test_cross_reference_categories` 断言改为 `{1:3}`（按 real_level）；新增 `test_init_level_offset_for_2_to_3_medal`（G=谷地调查者型 real=3 已升满 / H=潜能解放型 real=2 未升满） |
| `docs/bugfix_medal_investigator_max_tier.md`（新） | 完整根因 + 数据对比 |
| `docs/handoff_medal_module.md` / `docs/handoff_medal_f2_fix.md`（删） | 过时交接 |

---

## 4. 验证（本次会话已做）

- `pytest tests/test_endfield_medal.py` → **18 passed**。
- 命令行重建（大妖精Yousei，缓存 dump）：等级分布 `{3:57, 2:55, 1:24}`；未升满只剩 `潜能解放奖章`（`谷地调查者奖章` 移出）。
- `real_level` 公式经数据回算与玩家在游戏 / 森空岛 app 实测 57/55/24 完全一致。
- 渲染图：`data/_manual_test/medal_missing_fixed4.png`（F2）、`medal_view_fixed.png`（F1）——页脚均显示 AKEData。

---

## 5. 关键决策（已敲定）

- **以 `real_level = skland level + initLevel - 1` 为档位**，不碰 AKEData `max_level`（它本就正确）。
- **等级横条按「账号已拥有的当前档位（颜色）」统计**，而非全量快照总数（个人卡不应显示全游戏总数）。
- **未升满判定** = `can_be_upgraded and real_level < max_level`。
- **页脚只写「AKEData」**，不带「客户端 TableCfg」字样。

---

## 6. 已知问题 / 待办

1. **未 push**：本次改动提交本地后需 `git push origin dev`。
2. **未在真实 QQ/bot 环境跑通**：仅命令行验证（无 Satori）。接手后首要在 bot 里 `/zmd 奖章 刷新` + `/zmd 奖章 缺章` 验一遍。
3. **F1 等级横条 icon 接入仍等用户**：见 `handoff_grade_icon_and_guides.md` §2——用户会提供新 icon 改版式（当前仍是 FZ 剪影 + CSS mask 改色）。
4. **`token_cache` 当前是朋友账号**：本次用朋友账号（信翼）做第二份 live 样本验证，其 token 缓存在 `data/_manual_test/.token_cache`（gitignore）。`重查` 现在查的是朋友账号；要查大妖精Yousei 需重新发码登录。
5. **Warfarin 奖章适配器仍缺**：仅注册未实现（沿用旧 TODO，与本次无关）。

---

## 7. 如何接手（新设备，零上下文）

```bash
git pull origin dev          # 拿到本次提交
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
.venv\Scripts\python.exe -m pip install pytest pytest-asyncio

pytest tests/test_endfield_medal.py            # 应 18 passed

# 命令行手动测试（无需 QQ）
PYTHONPATH=. .venv\Scripts\python.exe scripts/_dev_medal_repl.py 奖章 刷新   # AKEData 全量 + baseline
PYTHONPATH=. .venv\Scripts\python.exe scripts/_dev_medal_repl.py 奖章         # F1 图（页脚 AKEData）
PYTHONPATH=. .venv\Scripts\python.exe scripts/_dev_medal_repl.py 奖章 缺章    # F2（交互选登录方式）
```

环境：Python ≥3.10（<3.14）。F2 需森空岛账号（手机号验证码登录）。token 缓存在 `data/_manual_test/.token_cache`（gitignore）。
**网络注意**：AKEData / `zonai.skland.com` 直连即可；`as.hypergryph.com`（发码/登录授权）若开了**美国代理**会不通——push 到 github 才需要代理，两者互斥，按需开关。

---

## 8. 相关文档

- `docs/bugfix_medal_investigator_max_tier.md`：本次根因 + 完整数据对比（**权威**）。
- `docs/handoff_grade_icon_and_guides.md`：上一会话（F1 等级图标 + AKEData 取数指南），其 F1 icon 待办仍有效。
- `docs/handoff_medal_version_diff.md` / `docs/handoff_akedata_migration.md`：版本对比 / 数据源迁移权威交接。
- `docs/akedata_data_access_guide.md`：AKEData 取数指南。
