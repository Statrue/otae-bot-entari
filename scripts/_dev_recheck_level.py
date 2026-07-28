"""临时：用缓存 token 重新查 card/detail，看「谷地调查者奖章」现在的 level。"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from plugins.endfield.account_client import EndfieldOfficialClient

TOKEN = (ROOT / "data/_manual_test/.token_cache").read_text(encoding="utf-8").strip()
TARGETS = {
    hashlib.md5(b"achv_adv_tundra_documents").hexdigest(): "谷地调查者奖章",
    hashlib.md5(b"achv_adv_tundra_box").hexdigest(): "谷地储藏家奖章(对照)",
    hashlib.md5(b"achv_fac_coupon_tundra").hexdigest(): "谷地调度专家奖章(对照)",
}


async def main() -> None:
    official = EndfieldOfficialClient()
    roles = await official.discover_roles(TOKEN)
    role = roles[0]
    print(f"角色: {role.nickname}")
    raw = await official.endfield_card_detail(TOKEN, role)
    medals = raw["data"]["detail"]["achieve"]["achieveMedals"]
    print(f"achieveMedals 总数: {len(medals)}")
    print()
    for m in medals:
        ad = m.get("achievementData") or {}
        if ad.get("id") in TARGETS:
            print(f"{TARGETS[ad['id']]}:")
            print(f"   level={m.get('level')}  isPlated={m.get('isPlated')}  obtainTs={m.get('obtainTs')}")
            print(f"   initLevel={ad.get('initLevel')}  reforge2Icon={'有' if ad.get('reforge2Icon') else '空'}  reforge3Icon={'有' if ad.get('reforge3Icon') else '空'}")


if __name__ == "__main__":
    asyncio.run(main())
