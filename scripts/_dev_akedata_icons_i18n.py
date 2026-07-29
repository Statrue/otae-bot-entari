"""确认 akedata 图标路径规则（从 v3-table-data.js）+ 验证 text-id 经 I18nTextTable_CN 解析为中文。"""
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
H = {"User-Agent": "otae-survey/1.0", "Referer": "https://cf.akedata.top/"}
TC = "public/1.4.4/8764515-7/TableCfg"


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=30) as x:
        return x.read().decode("utf-8", "replace")


def get_json(path: str):
    req = urllib.request.Request(f"{B}{path}", headers=H)
    with urllib.request.urlopen(req, timeout=60) as x:
        return json.load(x)


def lookup(i18n: dict, text_id) -> str:
    """text-id 可能是 int/负数/str；I18n 的 key 形态待确认，多试几种。"""
    for key in (text_id, str(text_id)):
        if key in i18n:
            return str(i18n[key])
    return "<未命中>"


def main() -> None:
    # 1) 图标路径规则：从 v3-table-data.js 提取含图标关键词的片段
    js = fetch_text(f"{SITE}/plugin/js/v3-table-data.js")
    print("=== v3-table-data.js 图标/路径相关片段 ===")
    seen = set()
    for m in re.finditer(r"[\"'`]([^\"'`]{4,120})[\"'`]", js):
        s = m.group(1)
        if re.search(r"icon|sprite|\.png|\.jpg|medaliconbig|charpotr|portrait|/images/", s, re.I):
            if s not in seen:
                seen.add(s)
                print(f"  {s}")
    print()

    # 2) text-id → I18n 中文解析验证
    print("=== text-id → I18nTextTable_CN 解析验证 ===")
    i18n = get_json(f"/{TC}/I18nTextTable_CN.json")
    print(f"I18n 共 {len(i18n)} 条; key 样例: {list(i18n.keys())[:3]}")

    char = get_json(f"/{TC}/CharacterTable.json")
    c0 = char["chr_0002_endminm"]
    print(f"角色 chr_0002_endminm: name.id={c0['name']['id']} → {lookup(i18n, c0['name']['id'])!r}")

    disp = get_json(f"/{TC}/EnemyTemplateDisplayInfoTable.json")
    d0 = disp["eny_0007_mimicw"]
    print(f"敌人 eny_0007_mimicw: name.id={d0['name']['id']} → {lookup(i18n, d0['name']['id'])!r}; nickname.id → {lookup(i18n, d0['nickname']['id'])!r}")

    achv = get_json(f"/{TC}/AchievementTable.json")
    a0 = next(iter(achv.values()))
    print(f"奖章 {next(iter(achv))}: name.id={a0['name']['id']} → {lookup(i18n, a0['name']['id'])!r}")

    wpn = get_json(f"/{TC}/WeaponBasicTable.json")
    w0 = next(iter(wpn.values()))
    print(f"武器 {next(iter(wpn))}: engName.id={w0['engName']['id']} → {lookup(i18n, w0['engName']['id'])!r}")

    item = get_json(f"/{TC}/ItemTable.json")
    i0 = item["achv_adv_tundra_box_1"]
    print(f"物品 achv_adv_tundra_box_1: name.id={i0['name']['id']} → {lookup(i18n, i0['name']['id'])!r}; iconId={i0.get('iconId')!r}")


if __name__ == "__main__":
    main()
