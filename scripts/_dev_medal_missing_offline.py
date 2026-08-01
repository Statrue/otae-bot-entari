"""离线渲染 F2 缺章卡（不依赖 QQ / 森空岛 token / 网络）。

读 ``data/_manual_test/`` 下最新的 ``card_detail_raw_*.json``（由
``_dev_medal_repl.py`` 的「手机登录 / 重查」dump 出）+ 当前 AKEData 快照，
调 ``build_medal_missing_view`` + ``draw_medal_missing_card``，输出 PNG。

用途：纯排版验证——改了 ``draw.py`` 的 F2 渲染后，无需登录即可看效果。

用法：
  PYTHONPATH=. .venv\\Scripts\\python.exe scripts\\_dev_medal_missing_offline.py
  PYTHONPATH=. .venv\\Scripts\\python.exe scripts\\_dev_medal_missing_offline.py path/to/card_detail_raw.json
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "_manual_test"

from plugins.endfield.client import WarfarinClient
from plugins.endfield.medal_store import MedalSnapshotStore
from plugins.endfield.service import EndfieldService
from plugins.endfield.draw import draw_medal_missing_card
from utils.http_client import close_http_client
from utils.image_utils import close_browser


def _latest_dump() -> Path | None:
    dumps = sorted(OUT.glob("card_detail_raw_*.json"))
    return dumps[-1] if dumps else None


async def main() -> None:
    dump_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _latest_dump()
    if dump_path is None:
        print("未找到 data/_manual_test/card_detail_raw_*.json；"
              "先用 _dev_medal_repl.py 的「手机登录 / 重查」生成 dump。")
        return
    store = MedalSnapshotStore()
    current = store.load_current_view()
    if current is None:
        print("暂无快照，请先执行：_dev_medal_repl.py 奖章 刷新")
        return
    raw = json.loads(dump_path.read_text(encoding="utf-8"))
    view = EndfieldService(WarfarinClient(timeout=30.0)).build_medal_missing_view(
        raw, current, nickname="离线样本", uid="***0000", server_name="China"
    )
    print(
        f"dump: {dump_path.name} · 未获得 {len(view.not_obtained)} · 未升满 {len(view.not_maxed)}"
        f" · 未镀层 {len(view.not_plated)} · 已获得 {view.owned_count}/{view.total_count}"
        f" · 截断 {view.truncated}"
    )
    pngs = await draw_medal_missing_card(view)
    out = OUT / "medal_missing_offline.png"
    out.write_bytes(pngs[0])
    print(f"图片已保存: {out}")
    await close_http_client()
    await close_browser()


if __name__ == "__main__":
    asyncio.run(main())
