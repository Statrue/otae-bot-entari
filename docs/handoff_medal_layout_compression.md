# 交接文档：F1/F2 蚀刻章卡排版优化（六边形档位 icon + 双列压缩）

> 用途：供下一个对话（新设备、零上下文）接手。本文自包含。
> 生成时间：2026-07-31　·　分支：`dev`
> 续 `docs/handoff_medal_level_offset_fix.md`（F2 level 偏移修复）与 `docs/handoff_grade_icon_and_guides.md`（等级图标）。本文聚焦本次会话：F1 等级横条接入三档六边形 PNG、F1/F2 列表条件双列 + 整体紧凑化。

---

## 0. 一句话现状

F1 统计卡 / F2 缺章卡的「等级横条」已从「FZ 剪影 + CSS mask 改色」换成**三档六边形 PNG**（对齐游戏「光荣之路」档位图标，素材 `assets/image/endfield/medal_grade_{1,2,3}.png`）；两张卡的条目列表改为「条目 ≥6 自动双列」+ 整体紧凑（icon 72→60、padding/字号下调、desc 2 行截断）。**F1 高度 5798→3214（-45%）、F2 5448→3596（-34%）**。测试全绿（奖章 18 + endfield 125 passed）。改动已落本地，待 push。

---

## 1. 本次已完成

| 项 | 内容 |
|---|---|
| 等级横条换六边形 icon | `_medal_grade_icon` 从「FZ 剪影 + CSS mask 改色」改为按 level 加载 `assets/image/endfield/medal_grade_{level}.png`（inline `<img>`）；缺图降级到原 mask 版；超出 1/2/3 兜底第 3 档。**解决** `handoff_grade_icon_and_guides.md` §2 / `handoff_medal_level_offset_fix.md` §6-3 的「等用户 icon」待办。 |
| 三档 PNG 入库 | `参考图/medal_grade_{1,2,3}.png`（`scripts/_process_medal_icon.py` 产物）复制到 `assets/image/endfield/`（生产目录，代码引用）。 |
| 双列压缩 | 新增 `.medal-list--double`（`repeat(2,minmax(0,1fr))`）+ 常量 `MEDAL_DOUBLE_COLUMN_MIN=6`；F1 新增列表、F2 各缺章分组在条目 ≥6 时自动双列，少则单列（避免右侧留白）。 |
| 整体紧凑 | `.medal-item` icon 72→60、padding 10→8/10、`strong` 17→16px、`.medal-desc` 加 2 行 `-webkit-line-clamp` 截断、`.grade-icon` 加 `object-fit:contain`。F1/F2 共享。 |
| F2 离线渲染工具 | 新增 `scripts/_dev_medal_missing_offline.py`：读历史 `card_detail_raw_*.json` + 快照离线渲染 F2，**不依赖 token/网络**。 |
| 测试 | `pytest tests/test_endfield_medal.py` → **18 passed**；`test_endfield_visual.py`+`test_endfield.py`+`test_endfield_potential_icon.py` → **125 passed, 3 skipped**。 |

---

## 2. 关键决策（已敲定）

- **icon 优先 PNG，mask 作 fallback**：`_medal_grade_icon` 先试 `ASSET_DIR/medal_grade_{level}.png`，缺失（`_local_image_data_url` 返回 `""`）才回退到 FZ 剪影 mask 改色。两套都保留，鲁棒。
- **双列条件触发（阈值 6）**：条目少时（如只缺 1~2 枚）保持单列不留白；条目多时自动双列压缩高度。F1 新增列表、F2 各分组按各自条目数独立判断。
- **F1 与 F2 共用 `.medal-item` 紧凑样式**：单列/双列都受益；F2 不再单独微调。
- **生产 icon 用 `assets/` 副本**：代码引用 `ASSET_DIR/medal_grade_{n}.png`；`参考图/` 保留为源（脚本产物 + 用户素材）。

---

## 3. 改动文件清单

| 文件 | 改动 |
|---|---|
| `plugins/endfield/draw.py` | 新增常量 `MEDAL_DOUBLE_COLUMN_MIN=6`；`MEDAL_CARD_CSS`：加 `.medal-list--double`、收紧 `.medal-item/.medal-icon/.medal-info/.medal-desc`、`.grade-icon` 加 `object-fit:contain`；`_medal_grade_icon` 改 PNG 优先 + mask 兜底 + 超档兜底第 3 档；`_draw_medal_stats_page` / `_medal_section_html` 列表 class 条件双列。 |
| `assets/image/endfield/medal_grade_{1,2,3}.png`（新） | 从 `参考图/` 复制；三档六边形档位图标（深灰 / 银白 / 金）。 |
| `scripts/_dev_medal_missing_offline.py`（新） | F2 离线渲染（读 dump + 快照）。 |
| `docs/handoff_medal_layout_compression.md`（本文） | 本次交接。 |

> `参考图/medal_grade_{1,2,3}.png` 仍在（脚本源）；生产代码只引用 `assets/` 副本。

---

## 4. 验证（本次会话已做）

- **F1**（snapshot 140 枚，等级 {1:24, 2:58, 3:58}）：`data/_manual_test/medal_view_1785507150_1.png`，**2560×3214**（原 5798，-45%）。等级横条三档六边形 icon（金 58 / 银 58 / 灰 24）清晰可辨。
- **F2**（离线 dump `card_detail_raw_1785342767.json`，信翼 75/140，截断）：`data/_manual_test/medal_missing_offline.png`，**2560×3596**（原 5448，-34%）。双列缺章列表完整可读、对齐一致、无溢出。
- **测试**：奖章 18 passed；endfield visual+core+potential 125 passed, 3 skipped。

---

## 5. 已知问题 / 待办

1. **未 push**：本次改动（含新增 PNG）需 `git add assets/image/endfield/medal_grade_*.png scripts/_dev_medal_missing_offline.py docs/handoff_medal_layout_compression.md` 后 `git push origin dev`。
2. **未在真实 QQ/bot 环境跑通**：仅命令行验证。接手后首要在 bot 里 `/zmd 奖章` + `/zmd 奖章 缺章` 验一遍。
3. **双列阈值可调**：`MEDAL_DOUBLE_COLUMN_MIN=6` 是经验值。想在某档条目数下切换单/双列，改常量即可。
4. **F1 icon 仍可换最终版**：当前用脚本生成的三档 PNG。用户若日后提供「最终版」icon，直接替换 `assets/image/endfield/medal_grade_{1,2,3}.png`，代码无需改。
5. **F1 分页 budget 未动**：`MEDAL_PAGE_BUDGETS=(56,40,28,18)` 是单列时代的值。双列后单页容量翻倍，若新增章极多（>56）触发分页，可上调 budget。当前 23 条不触发。
6. **upstream 未同步**（沿用上次，与本次无关）：`upstream/main` 有 25 个未同步提交（日历 / 心情 / 账号卡等）。本次未处理。

---

## 6. 如何接手（新设备，零上下文）

```bash
git pull origin dev          # 拿到本次提交
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
.venv\Scripts\python.exe -m pip install pytest pytest-asyncio

pytest tests/test_endfield_medal.py                              # 应 18 passed
pytest tests/test_endfield_visual.py tests/test_endfield.py      # 应 125 passed, 3 skipped

# F1（读快照，秒回；首次需「奖章 刷新」建快照）
PYTHONPATH=. .venv\Scripts\python.exe scripts\_dev_medal_repl.py 奖章

# F2 离线（不依赖 token/网络，用历史 dump）
PYTHONPATH=. .venv\Scripts\python.exe scripts\_dev_medal_missing_offline.py
# F2 在线（需森空岛 token；token 缓存于 data/_manual_test/.token_cache）
PYTHONPATH=. .venv\Scripts\python.exe scripts\_dev_medal_repl.py 重查
```

环境：Python ≥3.10（<3.14）。F1 需 AKEData 快照（`奖章 刷新`，直连 `zonai.skland.com` 即可）；F2 在线需森空岛账号（`as.hypergryph.com` 发码，开**美国代理**会不通——push 到 github 才需代理，两者互斥）。

---

## 7. 相关文档

- `docs/handoff_grade_icon_and_guides.md`：其 §2「F1 横条接入三档 / 新 icon」待办——**本次已完成**。
- `docs/handoff_medal_level_offset_fix.md`：其 §6-3「F1 等级横条 icon 接入仍等用户」——**本次已完成**。
- `docs/handoff_akedata_migration.md` / `docs/handoff_medal_version_diff.md`：数据源迁移 / 版本对比权威交接。
- `docs/akedata_data_access_guide.md`：AKEData 取数指南。
