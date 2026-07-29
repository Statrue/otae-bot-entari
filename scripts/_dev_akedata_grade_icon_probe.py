"""探测 akedata 是否有「通用三档蚀刻章图标」，以及 _lvNN 的真实含义。

1) v3-table-data.js / ake-data-source.js 里奖章图标拼接规则
2) medaliconbig 目录下是否存在通用档位图标（lv01.png / grade_1.png 等候选）
3) 单档章(maxLevel=1) 与 3 档章(maxLevel=3) 各自的 _lv01/_lv02/_lv03 是否都存在
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

B = "https://data.akedata.wiki"
SITE = "https://www.akedata.wiki"
H = {"User-Agent": "otae-probe/1.0", "Referer": "https://cf.akedata.top/"}
ICON = "/public/images/assets/beyond/dynamicassets/gameplay/ui/sprites/medaliconbig"


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


def maxlv(entry):
    li = entry.get("levelInfos") or {}
    lvs = []
    for v in li.values():
        if isinstance(v, dict):
            try:
                a = int(v.get("achieveLevel", 0))
                if a > 0:
                    lvs.append(a)
            except Exception:
                pass
    lvs = sorted(lvs)
    ml = max(lvs) if lvs else (int(entry.get("initLevel", 0) or 1))
    return ml, lvs


def main() -> None:
    m = get_json("/manifest.json")
    tc = next(v["tableCfgPath"].lstrip("/") for v in m["versions"] if v["id"] == m["latest"])

    # 1) 站点 JS 里的奖章图标规则
    print("=== 站点 JS 奖章图标相关片段 ===")
    for jsurl in (f"{SITE}/plugin/js/v3-table-data.js", f"{SITE}/plugin/js/ake-data-source.js"):
        try:
            js = fetch_text(jsurl)
        except Exception:
            continue
        for kw in ("medal", "achv", "medalicon", "achievementicon", "lv", "grade"):
            for s in sorted(set(re.findall(rf"[\"'`]([^\"'`]*{kw}[^\"'`]*?)[\"'`]", js))):
                if re.search(r"icon|\.png|sprite|/|medal|achv", s, re.I) and len(s) < 90:
                    print(f"  [{jsurl.rsplit('/',1)[-1]}][{kw}] {s}")

    # 2) 通用档位图标候选
    print("\n=== medaliconbig/ 通用档位图标候选 ===")
    cands = ["lv01", "lv02", "lv03", "lv1", "lv2", "lv3", "level1", "level_1",
             "grade_1", "grade1", "medal_1", "medal_lv01", "icon_lv01", "1", "default"]
    any_hit = False
    for c in cands:
        s = head(f"{ICON}/{c}.png")
        if s:
            print(f"  ✓ {c}.png  {s} B")
            any_hit = True
    if not any_hit:
        print("  （无通用档位图标候选命中）")

    # 3) 单档章 vs 3 档章的 _lvNN
    print("\n=== 具体奖章的 _lv01/_lv02/_lv03 ===")
    achv = get_json(f"/{tc}/AchievementTable.json")
    single = multi = None
    for aid, e in achv.items():
        if not isinstance(e, dict):
            continue
        ml, lvs = maxlv(e)
        if ml == 1 and single is None:
            single = aid
        if ml == 3 and len(lvs) >= 3 and multi is None:
            multi = aid
        if single and multi:
            break
    # 兜底：若没有 1/2/3 三档的章，退而取 maxLevel=3 的
    if multi is None:
        for aid, e in achv.items():
            if isinstance(e, dict) and maxlv(e)[0] == 3:
                multi = aid
                break

    for aid in (single, multi):
        if not aid:
            continue
        e = achv[aid]
        ml, lvs = maxlv(e)
        print(f"  {aid}  maxLevel={ml}  levelInfos 档位={lvs}")
        for lv in ("01", "02", "03"):
            s = head(f"{ICON}/{aid}_lv{lv}.png")
            print(f"     _lv{lv}.png → {('✓ '+str(s)+' B') if s else '无(404)'}")


if __name__ == "__main__":
    main()
