"""AKEData（终末地数据库 https://akedata.wiki ）奖章数据抓取。

AKEData 是基于游戏客户端 TableCfg 的数据站，CDN（data.akedata.wiki）稳定，作为
蚀刻章/奖章的权威主源，替代易超时的 FZ Wiki。

数据结构（2026-07-28 实测）：
- ``manifest.json`` → ``latest``（如 ``1.4.4@8764515-7``）→ ``versions[].tableCfgPath``
  （如 ``public/1.4.4/8764515-7/TableCfg``）。
- ``<tableCfgPath>/AchievementTable.json``：140 枚，按 ``achv_*`` id 索引；含
  ``canBeUpgraded``/``canBePlated``/``initLevel``/``levelInfos``/``order``/``groupId`` 等
  （名字/描述只有 text-id，``text`` 为空）。
- ``<tableCfgPath>/I18nTextTable_CN.json``：~13.8 万条，text-id → 中文文本。
- ``<tableCfgPath>/AchievementTypeTable.json``：8 个分类，含 ``categoryName``(text-id)、
  ``categoryPriority``、``achievementGroupData[]``(groupId + groupName text-id)。
- 图标：``<dataBase>/public/images/.../sprites/medaliconbig/<achvId>_lv<NN>.png``。

achv_id 与森空岛 ``achievementData.id`` 经 md5 一一对应（见 ``docs/skland_medal_id_mapping.md``）。
"""
from __future__ import annotations

from typing import Any

from utils.http_client import fetch_json

AKEDATA_DATA_BASE = "https://data.akedata.wiki"
AKEDATA_ICON_BASE = (
    f"{AKEDATA_DATA_BASE}/public/images/assets/beyond/dynamicassets/"
    "gameplay/ui/sprites/medaliconbig"
)
AKEDATA_HEADERS = {
    "User-Agent": "otae-bot-entari/1.0 (+https://github.com/otae-1204/otae-bot-entari)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://cf.akedata.top/",
}
# I18nTextTable_CN 约 18MB，超过 fetch_json 默认 10MB 上限。
_I18N_MAX_BYTES = 64 * 1024 * 1024


async def _get(path: str, *, max_bytes: int = 10 * 1024 * 1024) -> Any:
    return await fetch_json(
        f"{AKEDATA_DATA_BASE}{path}",
        namespace="akedata",
        headers=AKEDATA_HEADERS,
        timeout_seconds=30.0,
        max_bytes=max_bytes,
    )


async def fetch_akedata_manifest() -> dict[str, Any]:
    """``manifest.json`` → ``{latest, versions:[{id, tableCfgPath, ...}], sharedRevision}``。"""
    manifest = await _get("/manifest.json")
    if not isinstance(manifest, dict) or not manifest.get("latest"):
        raise RuntimeError("AKEData manifest 结构异常")
    return manifest


async def fetch_akedata_medal_tables() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    """返回 ``(AchievementTable, AchievementTypeTable, I18nTextTable_CN, version_id)``。"""
    manifest = await fetch_akedata_manifest()
    latest = manifest["latest"]
    entry = next((v for v in manifest.get("versions") or [] if v.get("id") == latest), None)
    if not entry or not entry.get("tableCfgPath"):
        raise RuntimeError(f"AKEData manifest 缺少版本 {latest} 的 tableCfgPath")
    table_cfg = str(entry["tableCfgPath"]).lstrip("/")
    achievement = await _get(f"/{table_cfg}/AchievementTable.json")
    type_table = await _get(f"/{table_cfg}/AchievementTypeTable.json")
    i18n = await _get(f"/{table_cfg}/I18nTextTable_CN.json", max_bytes=_I18N_MAX_BYTES)
    return achievement, type_table, i18n, latest
