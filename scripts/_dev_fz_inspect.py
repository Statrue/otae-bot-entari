"""诊断3：查 FZ 蚀刻章单件 entry 有没有 hex id 字段（用于 achv_↔hex 映射根治）。"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.endfield.client import WarfarinClient
from plugins.endfield.service import _fz_medal_entry_attrs, _fz_overview_entries, _first_text
from utils.http_client import close_http_client


async def main() -> None:
    client = WarfarinClient()
    roster = await client.fz_article_by_title("蚀刻章")
    entries = _fz_overview_entries(roster)
    titles = [_first_text(e, "title") for e in entries if _first_text(e, "title")]
    wuling = [t for t in titles if "武陵调度" in t]
    print("武陵调度 titles:", wuling)
    target = next((t for t in wuling if "Ⅴ" in t or t.endswith("V")), wuling[0] if wuling else None)
    if not target:
        print("未找到武陵调度奖章")
        await close_http_client()
        return
    print(f"\n抓取单件: {target}")
    detail = await client.fz_article_by_title(target)
    attrs = _fz_medal_entry_attrs(detail)
    entry = attrs.get("entry") if isinstance(attrs.get("entry"), dict) else {}
    print(f"\n单件 entry 字段 ({len(entry)} 个): {list(entry.keys())}")
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    # roster entry 字段（可能也带 hex）
    for e in entries:
        if _first_text(e, "title") == target:
            print(f"\nroster entry 字段 ({len(e)} 个): {list(e.keys())}")
            print(json.dumps(e, ensure_ascii=False, indent=2)[:1500])
            break
    await close_http_client()


if __name__ == "__main__":
    asyncio.run(main())
