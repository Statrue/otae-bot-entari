"""抽样 akedata 关键表，打印顶层结构 + entry 字段 + text-id 引用方式，为写取数指南准备。"""
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

B = "https://data.akedata.wiki"
H = {"User-Agent": "otae-survey/1.0", "Referer": "https://cf.akedata.top/"}

TABLES = [
    "CharacterTable", "CharacterPotentialTable", "CharProfessionTable", "CharGrowthTable",
    "EnemyTable", "EnemyAttributeTemplateTable", "EnemyAbilityDescTable", "DisplayEnemyTypeTable",
    "WeaponBasicTable", "WeaponTalentTemplateTable", "WeaponBreakThroughTemplateTable",
    "EquipTable", "EquipItemTable", "EquipSuitTable", "EquipEnhanceCostTable",
    "ItemTable", "ItemTypeTable", "ItemShowingTypeTable", "UseItemTable", "ItemIconCompositeTable",
    "DungeonTable", "DungeonSeriesTable",
    "ActivityTable", "ActivityTagTable",
    "ShopTable", "ShopGoodsTable",
    "SkillPatchTable", "PotentialTalentEffectTable", "RewardTable",
    "FactoryBuildingTable", "SpaceshipSkillTable", "ContingencyContractTable",
    "AchievementTable", "AchievementTypeTable",
]


def get_json(path: str):
    req = urllib.request.Request(f"{B}{path}", headers=H)
    with urllib.request.urlopen(req, timeout=40) as x:
        return json.load(x)


def summarize(name: str, data) -> None:
    if isinstance(data, dict):
        keys = list(data.keys())
        print(f"\n【{name}】dict · {len(keys)} 条 · 前3 key: {keys[:3]}")
        sample = next((v for v in data.values() if isinstance(v, dict)), None)
        if sample:
            text_fields = [
                k for k, v in sample.items()
                if isinstance(v, dict) and ("id" in v and "text" in v)
            ]
            scalar = {k: type(v).__name__ for k, v in sample.items() if not isinstance(v, (dict, list))}
            print(f"  entry 字段({len(sample)}): {list(sample.keys())}")
            if text_fields:
                print(f"  text-id 字段(需 I18n 解析): {text_fields}")
            print(f"  标量字段类型: {scalar}")
    elif isinstance(data, list):
        print(f"\n【{name}】list · {len(data)} 项")
        if data and isinstance(data[0], dict):
            print(f"  item 字段: {list(data[0].keys())}")
    else:
        print(f"\n【{name}】{type(data).__name__}")


def main() -> None:
    m = get_json("/manifest.json")
    tc = [v for v in m["versions"] if v["id"] == m["latest"]][0]["tableCfgPath"].lstrip("/")
    print(f"tableCfgPath = {tc}")
    for name in TABLES:
        try:
            data = get_json(f"/{tc}/{name}.json")
            summarize(name, data)
        except Exception as exc:
            print(f"\n【{name}】抓取失败: {exc}")


if __name__ == "__main__":
    main()
