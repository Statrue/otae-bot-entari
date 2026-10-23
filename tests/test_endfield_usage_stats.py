"""群内关卡成员使用率:键归一、落库、聚合与批次。"""

from __future__ import annotations

import asyncio
import hashlib
import time

import pytest

from plugins.endfield.account.challenge.models import (
    ChallengeMember,
    ChallengeRecord,
    MonumentDungeon,
    MonumentGroup,
    MonumentPayload,
)
from plugins.endfield.account.store import (
    ChallengeRecordMember,
    ChallengeRecordRow,
    EndfieldRole,
    EndfieldStore,
    OperatorCatalogEntry,
)
from plugins.endfield.usage.models import (
    FAMILY_MONUMENT,
    FAMILY_WAR_ECHO,
    UsageOverviewReport,
    UsageStageReport,
)
from plugins.endfield.usage.service import (
    ENDMIN_OPERATOR_KEY,
    UsageResolutionError,
    UsageStatsService,
    UsageUnavailableError,
    build_challenge_records,
    operator_key_for,
)


def _role(
    role_id: str, *, server_id: str = "1", qq: str = "10001", server_name: str = ""
) -> EndfieldRole:
    return EndfieldRole(
        id=int(role_id.strip("r") or 1),
        credential_id=1,
        qq_user_id=qq,
        binding_uid="B" + role_id,
        role_id=role_id,
        server_id=server_id,
        nickname="",
        server_name=server_name,
        is_primary=True,
    )


def _catalog() -> list[OperatorCatalogEntry]:
    entries = [
        ("a" * 32, "chr_0002_endmin", "管理员的先锋", 5, "先锋", 1),
        ("b" * 32, "chr_0004_aglina", "安洁莉娜", 6, "术师", 2),
        ("c" * 32, "chr_0005_chen", "陈", 6, "近卫", 3),
        ("d" * 32, "chr_0006_wolf", "狼", 4, "重装", 4),
        (ENDMIN_OPERATOR_KEY, "chr_9000_endmin", "管理员", 6, "近卫", 0),
    ]
    return [
        OperatorCatalogEntry(
            operator_key=key,
            source_id=source,
            name=name,
            rarity=rarity,
            profession=profession,
            sort_order=order,
        )
        for key, source, name, rarity, profession, order in entries
    ]


def _monument_payload(
    *,
    activity_id: str = "g1",
    activity_name: str = "主题一",
    start: int = 0,
    end: int = 0,
    stages: tuple[tuple[str, str, str, tuple[tuple[str, int], ...], int], ...] = (),
) -> MonumentPayload:
    pairs = []
    for stage_id, stage_name, difficulty, members, pass_time in stages:
        dungeon = MonumentDungeon(
            id=stage_id,
            name=stage_name,
            difficulty=difficulty,
            passed=True,
            record=ChallengeRecord(
                members=tuple(
                    ChallengeMember(char_id=char_id) for char_id, _slot in members
                ),
                record_ts=1000 + pass_time,
                pass_time=pass_time,
            ),
        )
        other = MonumentDungeon(id=stage_id + "-n", name=stage_name, difficulty="normal")
        pairs.append((other, dungeon) if difficulty == "hard" else (dungeon, other))
    return MonumentPayload(
        (
            MonumentGroup(
                id=activity_id,
                name=activity_name,
                activity_name=activity_name,
                start_ts=start,
                end_ts=end,
                stages=tuple(pairs),
            ),
        )
    )


def _store(tmp_path) -> EndfieldStore:
    return EndfieldStore(tmp_path / "endfield.db")


def _seed(store: EndfieldStore) -> None:
    store.replace_operator_catalog(_catalog(), "1.5.3")


def _bind(store: EndfieldStore, role: EndfieldRole) -> None:
    """写入绑定行,避免快照被孤儿清理掉。"""
    import time as _time

    now = int(_time.time())
    with store._lock:  # noqa: SLF001 - 测试直接造绑定行,跳过加密流程
        store.conn.execute(
            "INSERT OR IGNORE INTO credentials("
            "id, qq_user_id, token_fingerprint, token_nonce, token_ciphertext,"
            " token_tag, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (role.credential_id, role.qq_user_id, "fp", b"", b"", b"", now, now),
        )
        store.conn.execute(
            "INSERT OR IGNORE INTO roles("
            "credential_id, qq_user_id, binding_uid, role_id, server_id,"
            " nickname, server_name, channel_name, is_primary, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, '', '', '', 1, ?, ?)",
            (
                role.credential_id,
                role.qq_user_id,
                role.binding_uid,
                role.role_id,
                role.server_id,
                now,
                now,
            ),
        )
        store.conn.commit()


def test_operator_key_for_covers_all_forms():
    catalog = {entry.operator_key: entry for entry in _catalog()}
    by_source = {entry.source_id.casefold(): entry for entry in catalog.values()}
    hex_key = "a" * 32
    assert operator_key_for(hex_key, catalog, by_source) == hex_key
    assert operator_key_for("chr_0004_aglina", catalog, by_source) == "b" * 32
    assert operator_key_for("chr_9999_unknown", catalog, by_source) == hashlib.md5(
        "chr_9999_unknown".encode()
    ).hexdigest()
    assert operator_key_for("chr_9000_endmin", catalog, by_source) == ENDMIN_OPERATOR_KEY
    digest = hashlib.md5("chr_9000_endmin".encode()).hexdigest()
    assert operator_key_for(digest, catalog, by_source) == ENDMIN_OPERATOR_KEY


def test_build_challenge_records_maps_members(tmp_path):
    payload = _monument_payload(
        stages=(
            ("s1", "关卡一", "hard", (("chr_0004_aglina", 0), ("chr_0005_chen", 1)), 120),
        )
    )
    rows = build_challenge_records(FAMILY_MONUMENT, payload, _catalog())
    hard = [row for row in rows if row.difficulty == "hard"]
    assert len(hard) == 1
    assert hard[0].stage_id == "s1"
    assert hard[0].pass_time == 120
    assert [member.operator_key for member in hard[0].members] == ["b" * 32, "c" * 32]


def test_build_challenge_records_war_echo_keeps_rotation(tmp_path):
    from plugins.endfield.account.challenge.parsing import parse_war_echoes

    raw = {
        "data": {
            "warEchoes": {
                "seasons": [
                    {
                        "id": "season-1",
                        "name": "错视赛季",
                        "startTs": 100,
                        "endTs": 200,
                        "weeks": [
                            {
                                "id": "week-1",
                                "name": "悲悯之塔",
                                "startTs": 120,
                                "endTs": 180,
                                "dungeonGroups": [
                                    {
                                        "name": "蚀骨回廊",
                                        "cruelDungeon": {
                                            "id": "d1",
                                            "name": "蚀骨回廊",
                                            "isPass": True,
                                            "bestRecord": {
                                                "chars": [{"charId": "chr_0005_chen"}],
                                                "ts": 150,
                                                "passTs": 200,
                                            },
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        }
    }
    rows = build_challenge_records(
        FAMILY_WAR_ECHO, parse_war_echoes(raw, None), _catalog()
    )
    cruel = [row for row in rows if row.difficulty == "cruel"]
    assert len(cruel) == 1
    assert (cruel[0].activity_id, cruel[0].scope_id, cruel[0].stage_id) == (
        "season-1",
        "week-1",
        "d1",
    )
    assert (cruel[0].activity_start_ts, cruel[0].scope_end_ts) == (100, 180)
    assert cruel[0].members[0].operator_key == "c" * 32


class _FakeLocale:
    """只实现使用率用到的两句:文本反查与关卡名。"""

    def text(self, value, default=""):
        return {
            "Cycle of Phantasia Ⅱ": "异想赛季",
            "Season of Phantasia": "异想轮换Ⅱ",
        }.get(str(value), str(value or default))

    def dungeon_text(self, dungeon_id, field_name, fallback=""):
        if str(dungeon_id) == "d1" and field_name == "name":
            return "长刃记录：应龙"
        return self.text(fallback)


def test_report_translates_stored_english_names(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    row = ChallengeRecordRow(
        activity_id="s1",
        activity_name="Cycle of Phantasia Ⅱ",
        scope_id="w1",
        scope_name="Season of Phantasia",
        stage_id="d1",
        stage_name="Glaiver File: Yinglung",
        difficulty="cruel",
        passed=True,
        record_ts=10,
        pass_time=200,
        members=(ChallengeRecordMember(0, "b" * 32),),
    )
    store.replace_challenge_snapshot("r1", "1", FAMILY_WAR_ECHO, (row,), fetched_at=1000)
    service = UsageStatsService(store, client=None)  # type: ignore[arg-type]
    roles = [_role("r1")]
    raw = service.build_report("group", roles, FAMILY_WAR_ECHO)
    assert raw.activity_name == "Cycle of Phantasia Ⅱ"
    localized = service.build_report(
        "group", roles, FAMILY_WAR_ECHO, locale=_FakeLocale()
    )
    assert localized.activity_name == "异想赛季"
    assert localized.scope_name == "异想轮换Ⅱ"
    assert localized.stages[0].stage_name == "长刃记录：应龙"


def test_asia_roles_are_excluded_from_usage_stats(tmp_path):
    from plugins.endfield.usage.service import _challenge_roles

    asia = _role("r9", server_name="asia", server_id="5")
    kept = _challenge_roles([_role("r1"), asia])
    assert [role.role_id for role in kept] == ["r1"]


def test_snapshot_write_is_stale_safe(tmp_path):
    store = _store(tmp_path)
    row = ChallengeRecordRow(
        activity_id="g1",
        activity_name="主题一",
        scope_id="",
        scope_name="",
        stage_id="s1",
        stage_name="关卡一",
        difficulty="hard",
        passed=True,
        record_ts=10,
        pass_time=100,
        members=(ChallengeRecordMember(0, "b" * 32),),
    )
    assert store.replace_challenge_snapshot("r1", "1", FAMILY_MONUMENT, [row], fetched_at=200)
    assert not store.replace_challenge_snapshot("r1", "1", FAMILY_MONUMENT, [row], fetched_at=100)
    state = store.list_challenge_snapshots([("r1", "1")], family=FAMILY_MONUMENT)
    assert state[0].fetched_at == 200
    assert len(store.list_challenge_member_rows(FAMILY_MONUMENT)) == 1


def test_stage_report_uses_recorded_samples_only(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    service = UsageStatsService(store, client=None)  # type: ignore[arg-type]
    roles = [_role("r1"), _role("r2", qq="10002"), _role("r3", qq="10003")]
    now = int(time.time())
    rows = [
        ChallengeRecordRow(
            activity_id="g1",
            activity_name="主题一",
            stage_id="s1",
            stage_name="关卡一",
            difficulty="hard",
            passed=True,
            record_ts=now,
            pass_time=120,
            activity_start_ts=now - 3600,
            activity_end_ts=now + 3600,
            members=(ChallengeRecordMember(0, "b" * 32), ChallengeRecordMember(1, "c" * 32)),
        ),
        ChallengeRecordRow(
            activity_id="g1",
            activity_name="主题一",
            stage_id="s1",
            stage_name="关卡一",
            difficulty="hard",
            passed=True,
            record_ts=now,
            pass_time=140,
            activity_start_ts=now - 3600,
            activity_end_ts=now + 3600,
            members=(ChallengeRecordMember(0, "b" * 32),),
        ),
    ]
    store.replace_challenge_snapshot("r1", "1", FAMILY_MONUMENT, [rows[0]], fetched_at=now)
    store.replace_challenge_snapshot("r2", "1", FAMILY_MONUMENT, [rows[1]], fetched_at=now)

    report = service.build_stage_report("group", roles, FAMILY_MONUMENT, now=now)
    assert report.sample_count == 2
    assert report.bound_role_count == 3
    assert report.coverage == pytest.approx(2 / 3)
    assert report.insufficient is True
    top = report.operators[0]
    assert top.operator_key == "b" * 32
    assert top.used_count == 2
    assert top.usage_rate == pytest.approx(1.0)
    assert report.teams[0].count == 1
    assert report.teams[0].avg_pass_time == 120
    assert report.teams[1].avg_pass_time == 140


def test_insufficient_threshold_and_empty_scope(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    service = UsageStatsService(store, client=None)  # type: ignore[arg-type]
    with pytest.raises(UsageUnavailableError):
        service.build_stage_report("group", [_role("r1")], FAMILY_MONUMENT)
    payload = _monument_payload(
        stages=(
            ("s1", "关卡一", "hard", (("chr_0004_aglina", 0),), 100),
        )
    )
    rows = build_challenge_records(FAMILY_MONUMENT, payload, _catalog())
    for role_id in ("r1", "r2", "r3"):
        store.replace_challenge_snapshot(role_id, "1", FAMILY_MONUMENT, rows, fetched_at=1000)
    report = service.build_stage_report("group", [_role(r) for r in ("r1", "r2", "r3")], FAMILY_MONUMENT)
    assert report.sample_count == 3
    assert report.insufficient is False


def test_difficulty_isolation_and_unknown_stage(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    service = UsageStatsService(store, client=None)  # type: ignore[arg-type]
    rows = [
        ChallengeRecordRow(
            activity_id="g1",
            activity_name="主题一",
            stage_id="s1",
            stage_name="关卡一",
            difficulty="hard",
            passed=True,
            record_ts=10,
            pass_time=100,
            members=(ChallengeRecordMember(0, "b" * 32),),
        ),
        ChallengeRecordRow(
            activity_id="g1",
            activity_name="主题一",
            stage_id="s1",
            stage_name="关卡一",
            difficulty="normal",
            passed=True,
            record_ts=10,
            pass_time=90,
            members=(ChallengeRecordMember(0, "c" * 32),),
        ),
    ]
    store.replace_challenge_snapshot("r1", "1", FAMILY_MONUMENT, rows, fetched_at=1000)
    roles = [_role("r1")]
    hard = service.build_stage_report("group", roles, FAMILY_MONUMENT)
    normal = service.build_stage_report("group", roles, FAMILY_MONUMENT, difficulty="normal")
    assert hard.operators[0].operator_key == "b" * 32
    assert normal.operators[0].operator_key == "c" * 32
    with pytest.raises(UsageResolutionError):
        service.build_stage_report("group", roles, FAMILY_MONUMENT, terms=("不存在的关卡",))


def test_parse_usage_commands():
    from plugins.endfield.catalog.commands import parse_command

    plain = parse_command("影拓 使用率")
    assert (plain.action, plain.challenge_kind, plain.challenge_view) == (
        "challenge",
        "monument",
        "usage",
    )
    assert plain.challenge_terms == ()
    assert plain.scope == "auto"

    detail = parse_command("回响 使用率 错视赛季 悲悯之塔 残酷 全局")
    assert detail.challenge_kind == "war_echo"
    assert detail.challenge_terms == ("错视赛季", "悲悯之塔")
    assert detail.challenge_difficulty == "cruel"
    assert detail.scope == "global"

    refresh = parse_command("影拓 使用率 刷新 本群")
    assert refresh.challenge_view == "usage_refresh"
    assert refresh.scope == "group"

    duplicate = parse_command("影拓 使用率 刷新 刷新")
    assert duplicate.error

    scoped = parse_command("影拓 使用率 群内 全局")
    assert scoped.error == "统计范围仅可指定一次。"


def test_build_report_routes_terms_to_stage_or_overview(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    service = UsageStatsService(store, client=None)  # type: ignore[arg-type]
    rows = [
        ChallengeRecordRow(
            activity_id="g1",
            activity_name="主题一",
            stage_id="s1",
            stage_name="关卡一",
            difficulty="hard",
            passed=True,
            record_ts=10,
            pass_time=100,
            members=(ChallengeRecordMember(0, "b" * 32),),
        ),
        ChallengeRecordRow(
            activity_id="g1",
            activity_name="主题一",
            stage_id="s2",
            stage_name="关卡二",
            difficulty="hard",
            passed=True,
            record_ts=10,
            pass_time=100,
            members=(ChallengeRecordMember(0, "c" * 32),),
        ),
    ]
    store.replace_challenge_snapshot("r1", "1", FAMILY_MONUMENT, rows, fetched_at=1000)
    roles = [_role("r1")]
    assert isinstance(service.build_report("group", roles, FAMILY_MONUMENT), UsageOverviewReport)
    by_activity = service.build_report("group", roles, FAMILY_MONUMENT, terms=("主题一",))
    assert isinstance(by_activity, UsageOverviewReport)
    by_stage = service.build_report("group", roles, FAMILY_MONUMENT, terms=("主题一", "关卡二"))
    assert isinstance(by_stage, UsageStageReport)
    assert by_stage.stage_name == "关卡二"


def test_overview_lists_each_stage(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    service = UsageStatsService(store, client=None)  # type: ignore[arg-type]
    rows = [
        ChallengeRecordRow(
            activity_id="g1",
            activity_name="主题一",
            stage_id="s1",
            stage_name="关卡一",
            difficulty="hard",
            passed=True,
            record_ts=10,
            pass_time=100,
            members=(ChallengeRecordMember(0, "b" * 32),),
        ),
        ChallengeRecordRow(
            activity_id="g1",
            activity_name="主题一",
            stage_id="s2",
            stage_name="关卡二",
            difficulty="hard",
            passed=True,
            record_ts=10,
            pass_time=100,
            members=(ChallengeRecordMember(0, "c" * 32),),
        ),
    ]
    store.replace_challenge_snapshot("r1", "1", FAMILY_MONUMENT, rows, fetched_at=1000)
    overview = service.build_overview_report("group", [_role("r1")], FAMILY_MONUMENT)
    assert [stage.stage_name for stage in overview.stages] == ["关卡一", "关卡二"]
    assert all(stage.insufficient for stage in overview.stages)


class _StubClient:
    def __init__(self, payload: dict, *, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls = 0

    async def indie_hard(self, token, role):
        self.calls += 1
        if self.error:
            raise self.error
        return self.payload

    async def war_echoes(self, token, role):
        self.calls += 1
        return {}


def test_refresh_writes_snapshot_and_records_failure(tmp_path):
    store = _store(tmp_path)
    _seed(store)
    raw = {
        "data": {
            "indieHard": {
                "indieHardGroups": [
                    {
                        "id": "g1",
                        "name": "主题一",
                        "activityName": "主题一",
                        "activityStartTs": 1,
                        "activityEndTs": 2,
                        "dungeonGroups": [
                            {
                                "normalDungeon": {"id": "s1", "name": "关卡一", "isPass": True},
                                "hardDungeon": {
                                    "id": "s1",
                                    "name": "关卡一",
                                    "isPass": True,
                                    "bestRecord": {
                                        "chars": [{"charId": "chr_0004_aglina"}],
                                        "ts": 1000,
                                        "passTs": 120,
                                    },
                                },
                            }
                        ],
                    }
                ]
            }
        }
    }
    _bind(store, _role("r1"))
    _bind(store, _role("r2", qq="10002"))
    service = UsageStatsService(store, _StubClient(raw), batch_size=4)
    store.decrypt_token = lambda role, cipher: "token"  # type: ignore[assignment]
    result = asyncio.run(
        service.refresh_roles([_role("r1")], cipher=None, force=True)  # type: ignore[arg-type]
    )
    assert result.succeeded == 2
    assert store.list_challenge_member_rows(FAMILY_MONUMENT)

    store.decrypt_token = lambda role, cipher: "token"  # type: ignore[assignment]
    from plugins.endfield.account.client import EndfieldAPIError

    failing = UsageStatsService(store, _StubClient({}, error=EndfieldAPIError("查询", code="405")))
    failed = asyncio.run(
        failing.refresh_roles([_role("r2", qq="10002")], cipher=None, force=True)  # type: ignore[arg-type]
    )
    # 影拓走 _StubClient.indie_hard(抛 405),战争回响仍返回空响应,所以一失败一成功。
    assert (failed.failed, failed.succeeded) == (1, 1)
    state = store.list_challenge_snapshots([("r2", "1")], family=FAMILY_MONUMENT)[0]
    assert state.failure_count == 1
    assert state.next_attempt_at > 0
