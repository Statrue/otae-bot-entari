"""验证：AKEData manifest 保留多版本，直接对比 latest 与上一版本 AchievementTable
的 achv_id 集合，证明「版本新增蚀刻章」可从历史版本数据精确算出。

纯 urllib，不依赖项目内部模块，便于独立运行。
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = "https://data.akedata.wiki"
HEADERS = {
    "User-Agent": "otae-bot-entari/1.0 (+research)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://cf.akedata.top/",
}


def get(path: str):
    req = urllib.request.Request(f"{BASE}{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def achv_ids(table_cfg: str) -> set[str]:
    tbl = get(f"/{table_cfg}/AchievementTable.json")
    if not isinstance(tbl, dict):
        return set()
    return {k for k, v in tbl.items() if isinstance(v, dict)}


def main() -> None:
    manifest = get("/manifest.json")
    versions = manifest.get("versions") or []
    print(f"latest = {manifest.get('latest')}")
    print(f"versions[] 共 {len(versions)} 个:")
    for v in versions:
        print(f"  - {v.get('id'):>22}  tableCfgPath={v.get('tableCfgPath')}")

    if len(versions) < 2:
        print("历史版本不足 2 个，无法对比")
        return

    latest = versions[0]
    prev = versions[1]
    print(f"\n对比: latest={latest['id']}  vs  previous={prev['id']}")

    cur_ids = achv_ids(str(latest["tableCfgPath"]).lstrip("/"))
    prev_ids = achv_ids(str(prev["tableCfgPath"]).lstrip("/"))
    print(f"latest  id 数 = {len(cur_ids)}")
    print(f"previous id 数 = {len(prev_ids)}")

    added = sorted(cur_ids - prev_ids)
    removed = sorted(prev_ids - cur_ids)
    print(f"\n新增 achv_id（latest 有、previous 无）= {len(added)}")
    for i in added:
        print(f"  + {i}")
    print(f"\n移除 achv_id（previous 有、latest 无）= {len(removed)}")
    for i in removed:
        print(f"  - {i}")

    # 顺带：把 latest 与最早版本对比，看累计跨度
    oldest = versions[-1]
    old_ids = achv_ids(str(oldest["tableCfgPath"]).lstrip("/"))
    print(f"\n累计跨度 latest vs 最早版本 {oldest['id']}: 新增 {len(cur_ids - old_ids)} 枚")


if __name__ == "__main__":
    main()
