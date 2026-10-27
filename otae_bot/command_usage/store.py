"""SQLite storage for command calls and the aggregates the stats and status cards read.

One row per matched command. Only the command head and a sub-command word the owning
plugin registered are stored, never the user's arguments, so tokens, questions and phone
numbers typed after a command never reach this database.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_PATH = Path("data") / "command_usage" / "usage.sqlite3"
#: Raw rows older than this are pruned; the cards never look further back.
RETENTION_DAYS = 90

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    day TEXT NOT NULL,
    hour INTEGER NOT NULL,
    weekday INTEGER NOT NULL,
    platform TEXT NOT NULL,
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    plugin TEXT NOT NULL,
    command TEXT NOT NULL,
    sub TEXT NOT NULL,
    elapsed_ms INTEGER NOT NULL,
    ok INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS calls_ts ON calls (ts);
CREATE INDEX IF NOT EXISTS calls_group_ts ON calls (platform, group_id, ts);
CREATE TABLE IF NOT EXISTS names (
    platform TEXT NOT NULL,
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    updated REAL NOT NULL,
    PRIMARY KEY (platform, group_id, user_id)
);
CREATE TABLE IF NOT EXISTS users (
    platform TEXT NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    updated REAL NOT NULL,
    PRIMARY KEY (platform, user_id)
);
"""


@dataclass(frozen=True)
class CallRecord:
    ts: float
    platform: str
    group_id: str
    user_id: str
    plugin: str
    command: str
    sub: str
    elapsed_ms: int
    ok: bool
    #: 群名片，本群排行用。
    name: str = ""
    #: QQ 昵称，全局排行用。
    nickname: str = ""

    def row(self) -> tuple:
        moment = datetime.fromtimestamp(self.ts)
        return (
            self.ts,
            moment.strftime("%Y-%m-%d"),
            moment.hour,
            moment.weekday(),
            self.platform,
            self.group_id,
            self.user_id,
            self.plugin,
            self.command,
            self.sub,
            self.elapsed_ms,
            1 if self.ok else 0,
        )


@dataclass(frozen=True)
class Scope:
    """``group_id`` empty means every group and private chat (global); ``plugin`` narrows to one plugin."""

    platform: str = ""
    group_id: str = ""
    plugin: str = ""

    @property
    def is_global(self) -> bool:
        return not self.group_id


@dataclass(frozen=True)
class CommandRow:
    command: str
    sub: str
    plugin: str
    count: int
    avg_ms: float
    previous: int

    @property
    def label(self) -> str:
        return f"{self.command} {self.sub}" if self.sub else self.command


@dataclass(frozen=True)
class UserRow:
    user_id: str
    name: str
    count: int


@dataclass
class UsageReport:
    scope: Scope
    start: datetime
    end: datetime
    total: int = 0
    previous_total: int = 0
    users: int = 0
    new_users: int = 0
    failures: int = 0
    avg_ms: float = 0.0
    days: list[tuple[str, int]] = field(default_factory=list)
    commands: list[CommandRow] = field(default_factory=list)
    plugins: list[tuple[str, int]] = field(default_factory=list)
    heat: list[list[int]] = field(default_factory=list)  # [weekday][hour]
    top_users: list[UserRow] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return (self.total - self.failures) / self.total * 100 if self.total else 100.0


@dataclass
class TodaySummary:
    total: int = 0
    yesterday: int = 0
    failures: int = 0
    avg_ms: float = 0.0
    hours: list[int] = field(default_factory=lambda: [0] * 24)
    top: list[tuple[str, int]] = field(default_factory=list)


class UsageStore:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            self._conn = conn
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # -- writes ---------------------------------------------------------------

    def insert_many(self, records: Sequence[CallRecord]) -> None:
        if not records:
            return
        with self._lock:
            conn = self._connect()
            with conn:
                conn.executemany(
                    "INSERT INTO calls (ts, day, hour, weekday, platform, group_id, user_id, plugin, "
                    "command, sub, elapsed_ms, ok) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [record.row() for record in records],
                )
                conn.executemany(
                    "INSERT INTO names (platform, group_id, user_id, name, updated) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT (platform, group_id, user_id) DO UPDATE SET name = excluded.name, "
                    "updated = excluded.updated WHERE excluded.updated >= names.updated",
                    [
                        (r.platform, r.group_id, r.user_id, r.name, r.ts)
                        for r in records
                        if r.name and r.group_id
                    ],
                )
                conn.executemany(
                    "INSERT INTO users (platform, user_id, name, updated) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT (platform, user_id) DO UPDATE SET name = excluded.name, "
                    "updated = excluded.updated WHERE excluded.updated >= users.updated",
                    [(r.platform, r.user_id, r.nickname, r.ts) for r in records if r.nickname],
                )

    def prune(self, now: datetime | None = None, days: int = RETENTION_DAYS) -> int:
        cutoff = ((now or datetime.now()) - timedelta(days=days)).timestamp()
        with self._lock:
            conn = self._connect()
            with conn:
                return conn.execute("DELETE FROM calls WHERE ts < ?", (cutoff,)).rowcount

    # -- reads ----------------------------------------------------------------

    def _where(self, scope: Scope, start: float, end: float, prefix: str = "") -> tuple[str, list]:
        clause, params = f"{prefix}ts >= ? AND {prefix}ts < ?", [start, end]
        if not scope.is_global:
            clause += f" AND {prefix}platform = ? AND {prefix}group_id = ?"
            params += [scope.platform, scope.group_id]
        if scope.plugin:
            clause += f" AND {prefix}plugin = ?"
            params.append(scope.plugin)
        return clause, params

    def _rows(self, sql: str, params: Iterable) -> list[tuple]:
        with self._lock:
            return self._connect().execute(sql, list(params)).fetchall()

    def report(self, scope: Scope, days: int, now: datetime | None = None, *, top: int = 10, users: int = 6) -> UsageReport:
        now = now or datetime.now()
        end_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        start_day = end_day - timedelta(days=days)
        start, end = start_day.timestamp(), end_day.timestamp()
        prev_start = (start_day - timedelta(days=days)).timestamp()
        where, params = self._where(scope, start, end)
        prev_where, prev_params = self._where(scope, prev_start, start)
        report = UsageReport(scope, start_day, end_day - timedelta(seconds=1))

        total, users_count, failures, avg_ms = self._rows(
            f"SELECT COUNT(*), COUNT(DISTINCT user_id), SUM(1 - ok), AVG(elapsed_ms) FROM calls WHERE {where}", params
        )[0]
        report.total, report.users = total or 0, users_count or 0
        report.failures, report.avg_ms = failures or 0, avg_ms or 0.0
        report.previous_total = self._rows(f"SELECT COUNT(*) FROM calls WHERE {prev_where}", prev_params)[0][0]

        first_seen_where, first_params = self._where(scope, 0, end)
        report.new_users = self._rows(
            f"SELECT COUNT(*) FROM (SELECT user_id, MIN(ts) AS first FROM calls WHERE {first_seen_where} "
            "GROUP BY user_id) WHERE first >= ?",
            [*first_params, start],
        )[0][0]

        per_day = dict(self._rows(f"SELECT day, COUNT(*) FROM calls WHERE {where} GROUP BY day", params))
        report.days = [
            (day, per_day.get(day, 0))
            for day in ((start_day + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days))
        ]

        previous = {
            (command, sub): count
            for command, sub, count in self._rows(
                f"SELECT command, sub, COUNT(*) FROM calls WHERE {prev_where} GROUP BY command, sub", prev_params
            )
        }
        report.commands = [
            CommandRow(command, sub, plugin, count, avg or 0.0, previous.get((command, sub), 0))
            for command, sub, plugin, count, avg in self._rows(
                f"SELECT command, sub, MAX(plugin), COUNT(*) AS n, AVG(elapsed_ms) FROM calls WHERE {where} "
                "GROUP BY command, sub ORDER BY n DESC, command, sub LIMIT ?",
                [*params, top],
            )
        ]
        report.plugins = [
            (plugin, count)
            for plugin, count in self._rows(
                f"SELECT plugin, COUNT(*) AS n FROM calls WHERE {where} GROUP BY plugin ORDER BY n DESC, plugin", params
            )
        ]
        report.heat = [[0] * 24 for _ in range(7)]
        for weekday, hour, count in self._rows(
            f"SELECT weekday, hour, COUNT(*) FROM calls WHERE {where} GROUP BY weekday, hour", params
        ):
            report.heat[weekday][hour] = count
        joined, joined_params = self._where(scope, start, end, prefix="c.")
        if scope.is_global:
            # 全局：按用户合计，显示 QQ 昵称（不用某个群的名片）。
            sql = (
                "SELECT c.user_id, u.name, COUNT(*) AS cnt FROM calls c LEFT JOIN users u "
                "ON u.platform = c.platform AND u.user_id = c.user_id "
                f"WHERE {joined} GROUP BY c.platform, c.user_id ORDER BY cnt DESC, c.user_id LIMIT ?"
            )
        else:
            sql = (
                "SELECT c.user_id, n.name, COUNT(*) AS cnt FROM calls c LEFT JOIN names n "
                "ON n.platform = c.platform AND n.group_id = c.group_id AND n.user_id = c.user_id "
                f"WHERE {joined} GROUP BY c.user_id ORDER BY cnt DESC, c.user_id LIMIT ?"
            )
        report.top_users = [
            UserRow(user_id, name or user_id, count) for user_id, name, count in self._rows(sql, [*joined_params, users])
        ]
        return report

    def today(self, now: datetime | None = None, *, top: int = 4) -> TodaySummary:
        """Bot-wide numbers for the status card."""
        now = now or datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start, end = midnight.timestamp(), (midnight + timedelta(days=1)).timestamp()
        summary = TodaySummary()
        total, failures, avg_ms = self._rows(
            "SELECT COUNT(*), SUM(1 - ok), AVG(elapsed_ms) FROM calls WHERE ts >= ? AND ts < ?", (start, end)
        )[0]
        summary.total, summary.failures, summary.avg_ms = total or 0, failures or 0, avg_ms or 0.0
        summary.yesterday = self._rows(
            "SELECT COUNT(*) FROM calls WHERE ts >= ? AND ts < ?",
            ((midnight - timedelta(days=1)).timestamp(), (now - timedelta(days=1)).timestamp()),
        )[0][0]
        for hour, count in self._rows(
            "SELECT hour, COUNT(*) FROM calls WHERE ts >= ? AND ts < ? GROUP BY hour", (start, end)
        ):
            summary.hours[hour] = count
        summary.top = [
            (f"{command} {sub}" if sub else command, count)
            for command, sub, count in self._rows(
                "SELECT command, sub, COUNT(*) AS n FROM calls WHERE ts >= ? AND ts < ? "
                "GROUP BY command, sub ORDER BY n DESC, command LIMIT ?",
                (start, end, top),
            )
        ]
        return summary


__all__ = [
    "DEFAULT_PATH",
    "RETENTION_DAYS",
    "CallRecord",
    "CommandRow",
    "Scope",
    "TodaySummary",
    "UsageReport",
    "UsageStore",
    "UserRow",
]
