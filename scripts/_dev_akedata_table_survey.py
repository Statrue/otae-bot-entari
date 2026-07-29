"""调研 akedata TableCfg 目录：尝试目录列表 + 探测一批候选表名，确定各模块表清单。"""
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


def get_json(path: str):
    req = urllib.request.Request(f"{B}{path}", headers=H)
    with urllib.request.urlopen(req, timeout=30) as x:
        return json.load(x)


def get_raw(path: str):
    req = urllib.request.Request(f"{B}{path}", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=20) as x:
            return x.read(), None
    except Exception as exc:
        return b"", exc


def head(path: str):
    req = urllib.request.Request(f"{B}{path}", method="HEAD", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=12) as x:
            return int(x.headers.get("Content-Length", 0) or 0)
    except Exception:
        return None


def main() -> None:
    m = get_json("/manifest.json")
    tc = [v for v in m["versions"] if v["id"] == m["latest"]][0]["tableCfgPath"].lstrip("/")
    base = f"/{tc}/"
    print(f"latest={m['latest']}  tableCfgPath={tc}\n")

    # 1) 目录列表（CDN 多不支持，试 S3-style 与默认）
    print("=== 目录列表尝试 ===")
    for q in ["", "?list-type=2", f"?list-type=2&prefix={urllib.request.quote(tc + '/')}"]:
        body, exc = get_raw(base + q)
        tag = q or "(default)"
        print(f"  GET {base}{tag}: {len(body)} bytes  err={exc}")
        if b"<ListBucketResult" in body or b"<Contents>" in body:
            print("  >>> 命中 S3 列表，前 3000 字符:")
            print(body[:3000].decode("utf-8", "replace"))
            return

    # 2) 候选表名探测
    print("\n=== 候选表名 HEAD 探测（存在则显示大小）===")
    candidates = [
        "CharacterTable", "CharacterLevelTable", "CharacterPotentialTable", "CharacterSkinTable",
        "SkillTable", "SkillLevelTable", "SkillUpLevelTable",
        "TalentTable", "TalentLevelTable",
        "PotentialTable",
        "WeaponTable", "WeaponLevelTable", "WeaponSkillTable", "WeaponPotentialTable",
        "EquipmentTable", "EquipmentLevelTable", "EquipmentSuitTable", "EquipmentPotentialTable",
        "EnemyTable", "EnemyLevelTable", "EnemyHandbookTable", "EnemyWaveTable", "EnemyGroupTable",
        "AchievementTable", "AchievementTypeTable",
        "HandbookTable", "HandbookCharacterTable", "HandbookStageTable",
        "ItemTable", "MaterialTable", "CurrencyTable", "ItemUseTable",
        "StageTable", "StageLevelTable", "LevelTable", "CampaignTable", "ZoneTable",
        "MissionTable", "QuestTable", "DailyTable",
        "BuildingTable", "FacilityTable", "ConstructionTable", "BuildTable",
        "ShopTable", "StoreTable", "ExchangeTable",
        "GachaTable", "GachaPoolTable",
        "BuffTable", "StatusTable", "AttributeTable", "AttributeTagTable",
        "ActivityTable", "ActivityMissionTable",
        "BpTable", "BattlePassTable",
        "ProfessionTable", "ProfessionLevelTable",
        "RarityTable",
        "I18nTextTable_CN", "I18nTextTable_EN",
    ]
    found = []
    for name in candidates:
        size = head(f"{base}{name}.json")
        if size:
            found.append((name, size))
            print(f"  ✓ {name:32} {size/1024:9.1f} KB")
        # 不打印不存在的，避免噪声
    print(f"\n命中 {len(found)} / {len(candidates)} 候选表")


if __name__ == "__main__":
    main()
