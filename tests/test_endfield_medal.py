from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from plugins.endfield.medal_store import (
    MedalSnapshotStore,
    _dict_to_snapshot,
    _snapshot_to_dict,
)
from plugins.endfield.models import MedalDiffView, MedalItemView, MedalSnapshotView
from plugins.endfield.service import EndfieldService


def _make_medal(medal_id: str, *, name: str = "", max_level: int = 1, **kw) -> MedalItemView:
    return MedalItemView(medal_id=medal_id, name=name or medal_id, max_level=max_level, **kw)


def _make_snapshot(ids: list[str], *, version: str = "v") -> MedalSnapshotView:
    medals = [_make_medal(i, max_level=1 if i.endswith("1") else 3) for i in ids]
    snap = MedalSnapshotView(medals=medals, version=version, total_count=len(medals))
    snap.level_counts = {1: sum(1 for m in medals if m.max_level == 1),
                         3: sum(1 for m in medals if m.max_level == 3)}
    snap.category_counts = {"地区奖章": len(medals)}
    snap.platable_count = 0
    snap.upgradable_count = sum(1 for m in medals if m.max_level > 1)
    return snap


class MedalStoreRoundTripTest(unittest.TestCase):
    def test_level_counts_int_keys_survive_json(self):
        # JSON 会把 int 键转成 str；转换层必须还原
        snap = MedalSnapshotView(level_counts={1: 24, 2: 58, 3: 58}, total_count=140)
        d = _snapshot_to_dict(snap)
        self.assertEqual(d["level_counts"], {"1": 24, "2": 58, "3": 58})
        back = _dict_to_snapshot(d)
        self.assertEqual(back.level_counts, {1: 24, 2: 58, 3: 58})

    def test_field_filtering_ignores_unknown_keys(self):
        raw = {"medals": [{"medal_id": "a", "name": "A", "future_field": "x"}],
               "version": "v", "total_count": 1, "level_counts": {"2": 1}}
        snap = _dict_to_snapshot(raw)
        self.assertEqual(len(snap.medals), 1)
        self.assertEqual(snap.medals[0].medal_id, "a")
        self.assertEqual(snap.medals[0].name, "A")
        self.assertEqual(snap.level_counts, {2: 1})

    def test_empty_and_partial_dict(self):
        snap = _dict_to_snapshot({})
        self.assertEqual(snap.medals, [])
        self.assertEqual(snap.version, "")
        self.assertEqual(snap.level_counts, {})


class MedalSnapshotStoreTest(unittest.IsolatedAsyncioTestCase):
    async def test_replace_current_rolls_previous(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "snap.json")
            store = MedalSnapshotStore(path)
            self.assertIsNone(store.load_current_view())
            self.assertIsNone(store.load_previous_view())

            await store.replace_current(_make_snapshot(["a", "b"], version="2026-07-01"))
            cur = store.load_current_view()
            self.assertIsNotNone(cur)
            self.assertEqual(cur.version, "2026-07-01")
            self.assertEqual({m.medal_id for m in cur.medals}, {"a", "b"})
            self.assertIsNone(store.load_previous_view())  # 首次无 previous

            await store.replace_current(_make_snapshot(["a", "b", "c"], version="2026-07-27"))
            cur2 = store.load_current_view()
            self.assertEqual(cur2.version, "2026-07-27")
            self.assertEqual({m.medal_id for m in cur2.medals}, {"a", "b", "c"})
            prev = store.load_previous_view()
            self.assertEqual(prev.version, "2026-07-01")
            self.assertEqual({m.medal_id for m in prev.medals}, {"a", "b"})

    async def test_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "snap.json")
            await MedalSnapshotStore(path).replace_current(
                _make_snapshot(["x"], version="restart-test")
            )
            reopened = MedalSnapshotStore(path)  # 模拟进程重启重新 _load
            cur = reopened.load_current_view()
            self.assertEqual(cur.version, "restart-test")
            self.assertEqual([m.medal_id for m in cur.medals], ["x"])


class MedalDiffTest(unittest.TestCase):
    def test_diff_finds_only_new_ids(self):
        service = EndfieldService.__new__(EndfieldService)  # 不触发 __init__ 的依赖
        current = _make_snapshot(["a", "b", "c", "d"], version="new")
        previous = _make_snapshot(["a", "b"], version="old")
        diff: MedalDiffView = service.build_medal_diff(current, previous)
        self.assertEqual({m.medal_id for m in diff.new_medals}, {"c", "d"})
        self.assertEqual(diff.previous_version, "old")

    def test_diff_against_none_is_empty(self):
        # 首次快照无对比基线 → new_medals 为空（只展示总数统计）
        service = EndfieldService.__new__(EndfieldService)
        current = _make_snapshot(["a", "b"], version="new")
        diff = service.build_medal_diff(current, None)
        self.assertEqual(diff.new_medals, [])
        self.assertEqual(diff.previous_version, "")

    def test_diff_against_self_is_empty(self):
        service = EndfieldService.__new__(EndfieldService)
        current = _make_snapshot(["a", "b", "c"], version="v")
        diff = service.build_medal_diff(current, current)
        self.assertEqual(diff.new_medals, [])


class MedalMissingTest(unittest.TestCase):
    def _snapshot(self, medals):
        return MedalSnapshotView(medals=medals, total_count=len(medals))

    def test_cross_reference_categories(self):
        service = EndfieldService.__new__(EndfieldService)
        snapshot = self._snapshot([
            MedalItemView(medal_id="a", name="A", max_level=1),                       # 已集齐
            MedalItemView(medal_id="b", name="B", max_level=3, can_be_upgraded=True),  # 未升满
            MedalItemView(medal_id="c", name="C", max_level=1, can_be_plated=True),    # 未镀层
            MedalItemView(medal_id="d", name="D"),                                     # 未获得
        ])
        raw_progress = {"data": {"detail": {"achieve": {"achieveMedals": [
            {"achievementData": {"id": "a"}, "level": 1, "isPlated": True},
            {"achievementData": {"id": "b"}, "level": 1, "isPlated": False},
            {"achievementData": {"id": "c"}, "level": 1, "isPlated": False},
        ]}}}}
        view = service.build_medal_missing_view(
            raw_progress, snapshot, nickname="测试", uid="***1234", server_name="测试服"
        )
        self.assertEqual([m.medal_id for m in view.not_obtained], ["d"])
        self.assertEqual([m.medal_id for m in view.not_maxed], ["b"])
        self.assertEqual([m.medal_id for m in view.not_plated], ["c"])
        self.assertEqual(view.owned_count, 3)
        self.assertFalse(view.truncated)

    def test_truncation_when_too_many(self):
        service = EndfieldService.__new__(EndfieldService)
        snapshot = self._snapshot([MedalItemView(medal_id=f"m{i}", name=f"M{i}") for i in range(40)])
        view = service.build_medal_missing_view(
            {}, snapshot, nickname="x", uid="y", server_name="z", limit=30
        )
        self.assertTrue(view.truncated)
        self.assertLessEqual(len(view.not_obtained), 10)  # limit // 3


if __name__ == "__main__":
    unittest.main()
