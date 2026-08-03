from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

from .akedata_client import _get, fetch_akedata_manifest


_TABLE_MAX_BYTES = 24 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class AccountDetailNameMap:
    """Chinese names resolved from the current AKEData TableCfg snapshot."""

    character_names: Mapping[str, str] = field(default_factory=dict)
    weapon_names: Mapping[str, str] = field(default_factory=dict)
    skill_names: Mapping[str, str] = field(default_factory=dict)
    item_names: Mapping[str, str] = field(default_factory=dict)
    suit_names: Mapping[str, str] = field(default_factory=dict)
    version: str = ""


_name_map_cache: AccountDetailNameMap | None = None
_name_map_lock = asyncio.Lock()


async def fetch_account_detail_name_map() -> AccountDetailNameMap:
    """Load the small set of AKEData tables needed by the account detail card.

    AKEData keeps names as text ids, so the I18n table is loaded alongside the
    entity tables. The parsed map is retained in memory for the current AKE
    version; the shared HTTP cache also prevents duplicate downloads.
    """
    global _name_map_cache

    manifest = await fetch_akedata_manifest()
    latest = str(manifest.get("latest") or "")
    if not latest:
        raise RuntimeError("AKEData manifest has no latest version")
    if _name_map_cache is not None and _name_map_cache.version == latest:
        return _name_map_cache

    async with _name_map_lock:
        if _name_map_cache is not None and _name_map_cache.version == latest:
            return _name_map_cache
        version = next(
            (
                item
                for item in manifest.get("versions") or ()
                if isinstance(item, Mapping) and str(item.get("id") or "") == latest
            ),
            None,
        )
        table_cfg = str((version or {}).get("tableCfgPath") or "").strip("/")
        if not table_cfg:
            raise RuntimeError(f"AKEData version has no TableCfg path: {latest}")

        character_table, growth_table, weapon_table, item_table, suit_table, i18n = await asyncio.gather(
            _get(f"/{table_cfg}/CharacterTable.json", max_bytes=_TABLE_MAX_BYTES),
            _get(f"/{table_cfg}/CharGrowthTable.json", max_bytes=_TABLE_MAX_BYTES),
            _get(f"/{table_cfg}/WeaponBasicTable.json", max_bytes=_TABLE_MAX_BYTES),
            _get(f"/{table_cfg}/ItemTable.json", max_bytes=_TABLE_MAX_BYTES),
            _get(f"/{table_cfg}/EquipSuitTable.json", max_bytes=_TABLE_MAX_BYTES),
            _get(f"/{table_cfg}/I18nTextTable_CN.json", max_bytes=64 * 1024 * 1024),
        )
        _name_map_cache = build_account_detail_name_map(
            character_table,
            growth_table,
            weapon_table,
            item_table,
            suit_table,
            i18n,
            version=latest,
        )
        return _name_map_cache


def build_account_detail_name_map(
    character_table: Any,
    growth_table: Any,
    weapon_table: Any,
    item_table: Any,
    suit_table: Any,
    i18n: Any,
    *,
    version: str = "",
) -> AccountDetailNameMap:
    """Build an account-detail name map from AKEData table payloads."""
    translations = i18n if isinstance(i18n, Mapping) else {}
    character_names: dict[str, str] = {}
    weapon_names: dict[str, str] = {}
    skill_names: dict[str, str] = {}
    item_names: dict[str, str] = {}
    suit_names: dict[str, str] = {}

    item_rows = _rows(item_table)
    for key, row in item_rows:
        item_id = _field_text(row.get("id")) or key
        _put(item_names, item_id, _i18n_text(translations, row.get("name")))

    for key, row in _rows(character_table):
        char_id = _field_text(row.get("charId")) or key
        _put(character_names, char_id, _i18n_text(translations, row.get("name")))

    for key, row in _rows(weapon_table):
        weapon_id = _field_text(row.get("weaponId")) or key
        # ItemTable carries the CN display name; WeaponBasicTable.engName is
        # intentionally the English-facing name used by the game data.
        name = item_names.get(weapon_id, "") or _i18n_text(translations, row.get("engName"))
        _put(weapon_names, weapon_id, name)

    for key, row in _rows(growth_table):
        _ = key
        groups = row.get("skillGroupMap")
        if not isinstance(groups, Mapping):
            continue
        for group_key, group in groups.items():
            if not isinstance(group, Mapping):
                continue
            name = _i18n_text(translations, group.get("name"))
            if not name:
                continue
            _put(skill_names, _field_text(group.get("skillGroupId")) or str(group_key), name)
            for skill_id in group.get("skillIdList") or ():
                _put(skill_names, _field_text(skill_id), name)

    for key, row in _rows(suit_table):
        suit_id = _field_text(row.get("suitID")) or key
        entries = row.get("list")
        if not isinstance(entries, (list, tuple)):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            name = _i18n_text(translations, entry.get("suitName"))
            if name:
                _put(suit_names, suit_id, name)
                break

    return AccountDetailNameMap(
        character_names=character_names,
        weapon_names=weapon_names,
        skill_names=skill_names,
        item_names=item_names,
        suit_names=suit_names,
        version=version,
    )


def _rows(value: Any) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    if not isinstance(value, Mapping):
        return ()
    return tuple(
        (str(key), row)
        for key, row in value.items()
        if isinstance(row, Mapping)
    )


def _i18n_text(i18n: Mapping[str, Any], value: Any) -> str:
    if not isinstance(value, Mapping):
        return _field_text(value)
    text_id = value.get("id")
    if text_id is not None:
        translated = _field_text(i18n.get(str(text_id)))
        if translated:
            return translated
    return _field_text(value.get("text"))


def _put(target: dict[str, str], key: str, value: str) -> None:
    normalized_key = str(key or "").strip()
    normalized_value = str(value or "").strip()
    if normalized_key and normalized_value:
        target[normalized_key] = normalized_value
        target.setdefault(
            hashlib.md5(normalized_key.encode("utf-8")).hexdigest(),
            normalized_value,
        )


def _field_text(value: Any) -> str:
    if value is None or isinstance(value, (dict, list, tuple)):
        return ""
    return str(value).strip()
