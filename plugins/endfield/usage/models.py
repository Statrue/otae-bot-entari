"""群内关卡成员使用率报告对象。

只读视图：不出现 QQ、游戏 UID、昵称、`role_id` 或样本级列表，
渲染层只消费这里的字段。
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)
from time import (
    time,
)

FAMILY_MONUMENT = "monument"
FAMILY_WAR_ECHO = "war_echo"

FAMILY_LABELS = {
    FAMILY_MONUMENT: "影拓丰碑",
    FAMILY_WAR_ECHO: "战争回响",
}

DIFFICULTY_LABELS = {
    "normal": "普通",
    "hard": "困难",
    "cruel": "残酷",
}


@dataclass(frozen=True, slots=True)
class UsageStageKey:
    """一个可统计的关卡变体。"""

    family: str
    activity_id: str
    scope_id: str
    stage_id: str
    difficulty: str

    @property
    def identity(self) -> tuple[str, str, str, str, str]:
        return (
            self.family,
            self.activity_id,
            self.scope_id,
            self.stage_id,
            self.difficulty,
        )


@dataclass(frozen=True, slots=True)
class UsageOperator:
    operator_key: str
    name: str
    rarity: int
    profession: str
    sort_order: int
    avatar_url: str
    used_count: int
    sample_count: int
    usage_rate: float | None


@dataclass(frozen=True, slots=True)
class UsageTeamMember:
    operator_key: str
    name: str
    rarity: int
    avatar_url: str


@dataclass(frozen=True, slots=True)
class UsageTeam:
    members: tuple[UsageTeamMember, ...]
    count: int
    rate: float
    latest_ts: int = 0
    avg_pass_time: int = 0


@dataclass(frozen=True, slots=True)
class UsageStageReport:
    key: UsageStageKey
    stage_name: str
    activity_name: str
    scope_name: str
    difficulty: str
    scope: str
    sample_count: int
    bound_role_count: int
    coverage: float | None
    insufficient: bool
    operators: tuple[UsageOperator, ...] = ()
    teams: tuple[UsageTeam, ...] = ()
    team_combo_total: int = 0
    latest_record_ts: int = 0
    regions: tuple[str, ...] = ()
    generated_at: int = field(default_factory=lambda: int(time()))
    snapshot_updated_at: int = 0

    @property
    def family_label(self) -> str:
        return FAMILY_LABELS.get(self.key.family, self.key.family)

    @property
    def difficulty_label(self) -> str:
        return DIFFICULTY_LABELS.get(self.difficulty, self.difficulty)


@dataclass(frozen=True, slots=True)
class UsageStageSummary:
    """概览卡里的一关：Top3 干员 + 样本数。"""

    stage_name: str
    stage_id: str
    difficulty: str
    sample_count: int
    insufficient: bool
    leads: tuple[UsageOperator, ...] = ()
    bound_role_count: int = 0


@dataclass(frozen=True, slots=True)
class UsageOverviewReport:
    family: str
    activity_name: str
    scope_name: str
    difficulty: str
    scope: str
    bound_role_count: int
    stages: tuple[UsageStageSummary, ...] = ()
    recorded_role_count: int = 0
    regions: tuple[str, ...] = ()
    generated_at: int = field(default_factory=lambda: int(time()))
    snapshot_updated_at: int = 0
    latest_record_ts: int = 0

    @property
    def family_label(self) -> str:
        return FAMILY_LABELS.get(self.family, self.family)

    @property
    def difficulty_label(self) -> str:
        return DIFFICULTY_LABELS.get(self.difficulty, self.difficulty)
