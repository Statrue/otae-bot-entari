"""按「通用奖章 icon 不在奖章数据里」的思路重新找。

1) 全面提取站点 JS 里所有 sprites/ 子目录（之前只覆盖了 6 个，可能有通用 UI 目录）
2) 物品侧：奖章作为 ItemTable 条目时的通用 iconId（item_achievement_icon）及其档位变体
3) AchievementTypeTable 完整字段（分类/组是否带 iconId）
4) 通用奖章图标的档位/等级变体候选
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

B = "https://data.akedata.wiki"
SITE = "https://www.akedata.wiki"
H = {"User-Agent": "otae-probe/1.0", "Referer": "https://cf.akedata.top/"}
SPRITES = "/public/images/assets/beyond/dynamicassets/gameplay/ui/sprites"
TABLE_CFG = "public/1.4.4/8764515-7/TableCfg"


def get_json(path: str):
    req = urllib.request.Request(f"{B}{path}", headers=H)
    with urllib.request.urlopen(req, timeout=30) as x:
        return json.load(x)


def head(path: str):
    req = urllib.request.Request(f"{B}{path}", method="HEAD", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=12) as x:
            return int(x.headers.get("Content-Length", 0) or 0)
    except Exception:
        return None


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=30) as x:
        return x.read().decode("utf-8", "replace")


def main() -> None:
    # 1) 所有 sprites 子目录
    print("=== 站点 JS 引用过的 sprites/ 子目录 ===")
    dirs: set[str] = set()
    for js in ("index-app.js", "v3-table-data.js", "ake-data-source.js", "index-parse-fallback.js"):
        try:
            text = fetch_text(f"{SITE}/plugin/js/{js}")
        except Exception:
            continue
        for d in re.findall(r"sprites/([a-z0-9_]+)/", text):
            dirs.add(d)
    for d in sorted(dirs):
        print(f"  sprites/{d}/")

    # 2) 物品侧通用奖章图标 item_achievement_icon + 档位变体
    print("\n=== itemiconbig/item_achievement_icon 系列 ===")
    for name in ("item_achievement_icon",
                 "item_achievement_icon_lv01", "item_achievement_icon_lv02", "item_achievement_icon_lv03",
                 "item_achievement_icon_1", "item_achievement_icon_2", "item_achievement_icon_3",
                 "achievement_icon", "medal_icon", "icon_achievement"):
        s = head(f"{SPRITES}/itemiconbig/{name}.png")
        if s:
            print(f"  ✓ itemiconbig/{name}.png  {s} B")

    # 3) AchievementTypeTable 完整字段（看分类/组有没有 iconId）
    print("\n=== AchievementTypeTable 字段 ===")
    tt = get_json(f"/{TABLE_CFG}/AchievementTypeTable.json")
    k0 = next(iter(tt))
    e0 = tt[k0]
    print(f"  共 {len(tt)} 条; entry 字段: {list(e0.keys())}")
    print(f"  第一条: {json.dumps(e0, ensure_ascii=False)[:400]}")

    # 4) 通用奖章图标的档位变体（medaliconbig 下非 achv_ 的成就类通用图）
    print("\n=== medaliconbig/ 下通用成就图变体候选 ===")
    for name in ("achievement", "medal", "achv", "achievement_default",
                 "achv_1", "achv_2", "achv_3", "achv_lv01", "medal_default"):
        s = head(f"{SPRITES}/medaliconbig/{name}.png")
        if s:
            print(f"  ✓ medaliconbig/{name}.png  {s} B")


if __name__ == "__main__":
    main()
