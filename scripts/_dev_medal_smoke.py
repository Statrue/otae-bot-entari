"""离线自测脚本：蚀刻章/奖章模块（F1 全量抓取+渲染 / F2 渲染）。

不依赖 QQ 协议端，复现 ``plugins/endfield/__init__.py`` 里 ``_handle_medal`` 与
``_handle_medal_missing`` 的核心数据/渲染路径，覆盖 ``docs/handoff_medal_module.md``
§5「未验证」中的「渲染输出」「F1 全量抓取」两项。F2 真实 SDK 调用需绑账号，留待 bot 自测。

用法（项目根目录）：
    .venv/Scripts/python.exe scripts/_dev_medal_smoke.py

产物：data/_smoke/medal_stats_p*.png、data/_smoke/medal_missing_p*.png
落盘快照：data/endfield/medal_snapshot.json
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.endfield.client import WarfarinClient
from plugins.endfield.draw import draw_medal_missing_card, draw_medal_stats_card
from plugins.endfield.medal_store import MedalSnapshotStore
from plugins.endfield.models import MedalSnapshotView
from plugins.endfield.service import EndfieldService
from utils.http_client import close_http_client
from utils.image_utils import close_browser

OUT = ROOT / "data" / "_smoke"
OUT.mkdir(parents=True, exist_ok=True)


async def smoke_f1(service: EndfieldService, store: MedalSnapshotStore) -> None:
    print("== F1：全量抓取 FZ 蚀刻章（roster + 全部单件详情）==")
    started = time.perf_counter()
    snapshot = await service.fetch_medal_snapshot_fz()
    elapsed = time.perf_counter() - started
    print(f"  总数      : {snapshot.total_count}")
    print(f"  等级分布  : {dict(sorted(snapshot.level_counts.items()))}")
    print(f"  可镀层    : {snapshot.platable_count}")
    print(f"  可升级    : {snapshot.upgradable_count}")
    print(f"  分类分布  : {snapshot.category_counts}")
    print(f"  版本标签  : {snapshot.version!r}")
    print(f"  耗时      : {elapsed:.1f}s")
    assert snapshot.total_count > 0, "FZ 抓取返回空快照"

    print("== 落盘快照（current/previous 双槽滚动）==")
    await store.replace_current(snapshot)
    current = store.load_current_view()
    previous = store.load_previous_view()
    print(f"  current   : {len(current.medals)} 枚")
    print(f"  previous  : {'（首次无）' if previous is None else previous.version}")

    print("== 渲染 F1 统计图（build_medal_diff + draw_medal_stats_card）==")
    diff = service.build_medal_diff(current, previous)
    print(f"  新增      : {len(diff.new_medals)} 枚（首次快照应为 0）")
    pngs = await draw_medal_stats_card(diff)
    for idx, png in enumerate(pngs, 1):
        path = OUT / f"medal_stats_p{idx}.png"
        path.write_bytes(png)
        print(f"  -> {path.name}  {len(png):,} bytes")
    print(f"  分页数    : {len(pngs)}")


def _mock_f2_progress(snapshot: MedalSnapshotView) -> dict:
    """构造 mock 森空岛 card/detail 响应：前 2/3 奖章标记为已获得、故意未满级且未镀层。

    由此触发「未获得」「未升满」「未镀层」三段，验证 draw_medal_missing_card 渲染与截断。
    """
    medals = [m for m in snapshot.medals if m.medal_id]
    owned = medals[: max(1, len(medals) * 2 // 3)]
    achieve_medals = [
        {"achievementData": {"id": m.medal_id}, "level": 1, "isPlated": False}
        for m in owned
    ]
    return {"data": {"detail": {"achieve": {"achieveMedals": achieve_medals}}}}


async def smoke_f2(service: EndfieldService, store: MedalSnapshotStore) -> None:
    print("== F2：缺章渲染（mock 进度，验证 draw_medal_missing_card）==")
    snapshot = store.load_current_view()
    if snapshot is None:
        print("  跳过：无快照")
        return
    raw_progress = _mock_f2_progress(snapshot)
    view = service.build_medal_missing_view(
        raw_progress, snapshot,
        nickname="自测账号", uid="***0000", server_name="测试服",
    )
    print(f"  未获得    : {len(view.not_obtained)}")
    print(f"  未升满    : {len(view.not_maxed)}")
    print(f"  未镀层    : {len(view.not_plated)}")
    print(f"  已获得/总 : {view.owned_count}/{view.total_count}")
    print(f"  截断      : {view.truncated}")
    pngs = await draw_medal_missing_card(view)
    for idx, png in enumerate(pngs, 1):
        path = OUT / f"medal_missing_p{idx}.png"
        path.write_bytes(png)
        print(f"  -> {path.name}  {len(png):,} bytes")


async def main() -> None:
    client = WarfarinClient()
    service = EndfieldService(client)
    store = MedalSnapshotStore()
    try:
        await smoke_f1(service, store)
        print()
        await smoke_f2(service, store)
        print("\n全部离线自测完成。图片见 data/_smoke/")
    finally:
        await close_http_client()
        await close_browser()


if __name__ == "__main__":
    asyncio.run(main())
