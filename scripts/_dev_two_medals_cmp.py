"""对比「苏醒」「谷地调查者奖章」在森空岛 dump 与 FZ 的原始数据。"""
from __future__ import annotations

import asyncio
import glob
import json
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from plugins.endfield.client import WarfarinClient
from plugins.endfield.service import _fz_medal_entry_attrs, _fz_overview_entries, _first_text

WANT = ["苏醒", "谷地调查者奖章"]


async def main() -> None:
    # 1) 森空岛 dump（本地）
    raw = json.load(open(sorted(glob.glob(str(ROOT / "data/_manual_test/card_detail_raw_*.json")))[-1], encoding="utf-8"))
    medals = raw["data"]["detail"]["achieve"]["achieveMedals"]
    sk = { (m.get("achievementData") or {}).get("name"): m for m in medals }

    # 2) FZ（联网，慢则重试）
    client = WarfarinClient(timeout=30.0)
    roster = await client.fz_article_by_title("蚀刻章")
    title_of = {}
    for e in _fz_overview_entries(roster):
        nm = _first_text(e, "name")
        if nm in WANT:
            title_of[nm] = _first_text(e, "title")
    fz_entries = {}
    for nm in WANT:
        t = title_of.get(nm)
        if not t:
            continue
        for _ in range(3):
            try:
                fz_entries[nm] = (_fz_medal_entry_attrs(await client.fz_article_by_title(t)).get("entry")) or {}
                break
            except Exception as exc:
                print(f"# FZ {nm} 重试: {exc!r}")

    for nm in WANT:
        print("\n" + "=" * 70)
        print(f"【{nm}】")
        print("=" * 70)
        print("\n--- 森空岛 card/detail 原始 JSON ---")
        m = sk.get(nm)
        if m:
            print(json.dumps(m, ensure_ascii=False, indent=2))
        else:
            print("（dump 中未找到）")
        print("\n--- FZ 单件 entry ---")
        e = fz_entries.get(nm)
        if e:
            print(f"  id        : {e.get('id')}")
            print(f"  initLevel : {e.get('initLevel')}")
            print(f"  canBePlated: {e.get('canBePlated')}")
            print(f"  levels    : {json.dumps(e.get('levels'), ensure_ascii=False)}")
        else:
            print("  （FZ 抓取失败/未取到）")


if __name__ == "__main__":
    asyncio.run(main())
