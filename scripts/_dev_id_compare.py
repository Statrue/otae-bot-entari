"""临时调研脚本：对比同一枚奖章在 FZ Wiki / Warfarin Wiki 的 id。

实证 FZ 与 Warfarin 共享游戏客户端的 `achv_*` id 命名空间。
森空岛 achievementData.id 是 hex 哈希、属另一命名空间（需登录抓 card/detail，本机无 dump，
仅据既有结论与文档说明；这里用真实请求证 FZ↔Warfarin 同 id，并打印 FZ 单件 entry 全字段）。

用法：PYTHONPATH=. .venv/Scripts/python.exe scripts/_dev_id_compare.py
"""
from __future__ import annotations

import asyncio

from plugins.endfield.client import WarfarinClient
from plugins.endfield.service import _fz_medal_entry_attrs, _fz_overview_entries, _first_text


async def main() -> None:
    client = WarfarinClient(timeout=30.0)
    roster = await client.fz_article_by_title("蚀刻章")
    titles = [t for t in (_first_text(e, "title") for e in _fz_overview_entries(roster)) if t]
    print(f"FZ roster: {len(titles)} 枚。取若干枚 + 武陵调度系列做对照。\n")

    highlight = [t for t in titles if "武陵调度" in t]
    sample = (highlight + [t for t in titles if t not in highlight])[:6]

    fz_rows: list[tuple[str, str, dict]] = []  # (name, id, entry)
    for t in sample:
        try:
            raw = await client.fz_article_by_title(t)
        except Exception as exc:
            print(f"  [skip] {t}: {exc!r}")
            continue
        attrs = _fz_medal_entry_attrs(raw)
        entry = attrs.get("entry") if isinstance(attrs.get("entry"), dict) else {}
        name = _first_text(entry, "name") or t
        mid = _first_text(entry, "id", "medalId", "achvId")
        fz_rows.append((name, mid, entry))

    # Warfarin /cn/medals（全量扁平，含 achv_ id）
    warfarin_ids: dict[str, str] = {}
    try:
        data = await client._get_json(f"{client.BASE_URL}/cn/medals")
        for item in (data.get("data") or []):
            n = _first_text(item, "name")
            if n:
                warfarin_ids[n] = str(item.get("id") or "")
        print(f"Warfarin /cn/medals: {len(warfarin_ids)} 枚。\n")
    except Exception as exc:
        print(f"Warfarin /cn/medals 获取失败: {exc!r}\n")

    print(f"{'奖章名':<20} {'FZ id':<34} {'Warfarin id':<34} 同id?")
    print("-" * 104)
    for name, fz_id, _entry in fz_rows:
        w_id = warfarin_ids.get(name, "<未匹配>")
        flag = "✓同" if fz_id and w_id == fz_id else ("—" if w_id == "<未匹配>" else "✗异")
        print(f"{name:<20} {fz_id:<34} {w_id:<34} {flag}")

    print("\n=== FZ 单件 entry 全字段（最后一枚）===")
    last_entry = fz_rows[-1][2] if fz_rows else {}
    for k, v in last_entry.items():
        print(f"  {k}: {repr(v)[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
