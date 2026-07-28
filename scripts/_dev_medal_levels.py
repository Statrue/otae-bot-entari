"""临时调研：看「谷地调查者奖章」与同系列「谷地储藏家奖章」的 FZ 原始 levels[] 结构，
判断 max_level 推导是否正确、玩家是否真的未升满。"""
from __future__ import annotations

import asyncio

from plugins.endfield.client import WarfarinClient
from plugins.endfield.service import _fz_medal_entry_attrs, _fz_overview_entries, _first_text

WANT = {"谷地调查者奖章", "谷地储藏家奖章", "谷地调度专家奖章", "谷地工业先驱奖章"}


async def main() -> None:
    client = WarfarinClient(timeout=30.0)
    roster = await client.fz_article_by_title("蚀刻章")
    title_of = {}
    for e in _fz_overview_entries(roster):
        nm = _first_text(e, "name")
        if nm in WANT:
            title_of[nm] = _first_text(e, "title")

    for nm in sorted(WANT):
        title = title_of.get(nm)
        print(f"\n=== {nm} ===  title={title}")
        if not title:
            print("  (roster 未找到标题)")
            continue
        for _ in range(3):
            try:
                raw = await client.fz_article_by_title(title)
                break
            except Exception as exc:
                print(f"  重试: {exc!r}")
        else:
            print("  抓取失败")
            continue
        entry = (_fz_medal_entry_attrs(raw).get("entry")) or {}
        print(f"  entry.id={entry.get('id')}")
        print(f"  entry.initLevel={entry.get('initLevel')}  entry.level={entry.get('level')}")
        levels = entry.get("levels")
        print(f"  entry.levels 类型={type(levels).__name__} 原始={levels!r}")


if __name__ == "__main__":
    asyncio.run(main())
