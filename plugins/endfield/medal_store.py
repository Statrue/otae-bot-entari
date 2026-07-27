"""蚀刻章/奖章全量快照存储。

既作版本对比基线（current / previous 两槽，手动刷新时滚动），也作命令读取的
性能缓存（避免每次 `奖章` 命令都实时抓取 140 个 FZ 详情页）。

底层用 ``utils.json_store.JsonStore``（文件 JSON，每次 set 全量重写）。写盘放线程池、
模块级 ``asyncio.Lock`` 串行化，避免并发刷新互相覆盖。
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Any

from utils.json_store import JsonStore

from .models import MedalItemView, MedalSnapshotView

_DEFAULT_PATH = str(Path("data") / "endfield" / "medal_snapshot.json")

# 仅取已知字段，容忍磁盘上多余/缺失键（手动编辑或未来字段增删）
_MEDAL_ITEM_FIELDS = frozenset(MedalItemView.__dataclass_fields__)


class MedalSnapshotStore:
    """奖章全量快照：current/previous 两槽，手动刷新时滚动。"""

    def __init__(self, file_path: str = _DEFAULT_PATH) -> None:
        self._store = JsonStore(file_path)
        self._lock = asyncio.Lock()

    async def replace_current(self, snapshot: MedalSnapshotView) -> None:
        """新快照写入 current，原 current 移到 previous。串行 + 写盘放线程池。"""
        current_dict = _snapshot_to_dict(snapshot)
        async with self._lock:
            previous_dict = self._store.get("current")
            await asyncio.to_thread(self._persist, previous_dict, current_dict)

    def _persist(self, previous_dict: dict[str, Any] | None, current_dict: dict[str, Any]) -> None:
        # 直接改底层 _data 再一次 _save，避免 set() 两次全量写盘
        self._store._data["previous"] = previous_dict
        self._store._data["current"] = current_dict
        self._store._save()

    def load_current_view(self) -> MedalSnapshotView | None:
        data = self._store.get("current")
        return _dict_to_snapshot(data) if isinstance(data, dict) else None

    def load_previous_view(self) -> MedalSnapshotView | None:
        data = self._store.get("previous")
        return _dict_to_snapshot(data) if isinstance(data, dict) else None


def _snapshot_to_dict(snapshot: MedalSnapshotView) -> dict[str, Any]:
    """View → 可 JSON 序列化的 dict（level_counts 的 int 键转 str 以便 JSON 存储）。"""
    return {
        "version": snapshot.version,
        "fetched_at": snapshot.fetched_at,
        "source": snapshot.source,
        "total_count": snapshot.total_count,
        "level_counts": {str(k): v for k, v in snapshot.level_counts.items()},
        "platable_count": snapshot.platable_count,
        "upgradable_count": snapshot.upgradable_count,
        "category_counts": dict(snapshot.category_counts),
        "medals": [asdict(m) for m in snapshot.medals],
    }


def _dict_to_snapshot(data: dict[str, Any]) -> MedalSnapshotView:
    medals: list[MedalItemView] = []
    for raw in data.get("medals") or []:
        if isinstance(raw, dict):
            medals.append(
                MedalItemView(**{k: v for k, v in raw.items() if k in _MEDAL_ITEM_FIELDS})
            )
    level_raw = data.get("level_counts")
    level_counts = (
        {int(k): int(v) for k, v in level_raw.items()}
        if isinstance(level_raw, dict)
        else {}
    )
    category_raw = data.get("category_counts")
    category_counts = (
        {str(k): int(v) for k, v in category_raw.items()}
        if isinstance(category_raw, dict)
        else {}
    )
    return MedalSnapshotView(
        medals=medals,
        version=str(data.get("version") or ""),
        fetched_at=int(data.get("fetched_at") or 0),
        source=str(data.get("source") or "fz"),
        total_count=int(data.get("total_count") or len(medals)),
        level_counts=level_counts,
        platable_count=int(data.get("platable_count") or 0),
        upgradable_count=int(data.get("upgradable_count") or 0),
        category_counts=category_counts,
    )
