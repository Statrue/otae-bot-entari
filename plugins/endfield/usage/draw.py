"""群内关卡成员使用率统计展示层:把使用率报告渲染成 1080 宽长图。

只消费 ``UsageStageReport`` / ``UsageOverviewReport``:分母、排序与覆盖率
都由 service 给出,这里只负责版式。头像地址是 service 拼好的完整 URL,
下载失败或为空时退成名字首字方块,卡片上不会出现 operator_key 之类的内部标识。
"""

from __future__ import annotations

import time

from ..cold_start import REMOTE_ASSET_NAMESPACE, note_remote_assets
from ..rendering.cards import (
    ASSET_DIR,
    PreparedCardHtml,
    _draw_gallery_catalog,
    _local_image_data_url,
    _prepare_assets,
    esc,
    esc_attr,
    is_height_limit_error,
)
from .models import (
    DIFFICULTY_LABELS,
    UsageOperator,
    UsageOverviewReport,
    UsageStageReport,
    UsageStageSummary,
    UsageTeam,
)


USAGE_STATS_WIDTH = 1080
# 截整块 .page:30px 网格留白与圆角白卡一起出图,和其他终末地卡同一外壳。
_USAGE_SELECTOR = ".page"
_OVERFLOW_SELECTORS = (".card", ".rank", ".team", ".stage")
# 高度超限时排行按 8 → 6 收缩、概览按 5 → 4 关一页退让,都不静默裁行。
_STAGE_RANK_LIMITS = (8, 6)
_OVERVIEW_PAGE_SIZES = (5, 4)
_TEAM_LIMIT = 3
_RECORD_LIMIT = 5
# 少于该样本数不出排行,改出样本不足卡。
_MIN_SAMPLES = 3
# 最新记录超过该时长后,时效条把时间标成金色提示陈旧。
_STALE_SECONDS = 30 * 24 * 3600

_SCOPE_LABELS = {"global": "全局统计", "group": "群内统计"}
_REGION_LABELS = {"all": "总计", "cn": "国服", "asia": "亚服"}


async def draw_usage_stage(report: UsageStageReport) -> tuple[bytes, ...]:
    """单关卡使用率卡:Top8 排行 + Top3 队伍;样本不足时降级成状态面板。"""
    last_error: RuntimeError | None = None
    for rank_limit in _STAGE_RANK_LIMITS:
        try:
            return (await _draw_stage_page(report, rank_limit=rank_limit),)
        except RuntimeError as exc:
            if not is_height_limit_error(exc):
                raise
            last_error = exc
    raise last_error or RuntimeError("单关卡使用率卡渲染失败")


async def draw_usage_overview(report: UsageOverviewReport) -> tuple[bytes, ...]:
    """当期概览卡:每关一块 Top3;超过 5 关按页拆分,每页头部页脚齐全。"""
    last_error: RuntimeError | None = None
    for page_size in _OVERVIEW_PAGE_SIZES:
        pages = _chunk_stages(report.stages, page_size)
        try:
            return tuple(
                [
                    await _draw_overview_page(
                        report, page, number=index + 1, total=len(pages)
                    )
                    for index, page in enumerate(pages)
                ]
            )
        except RuntimeError as exc:
            if not is_height_limit_error(exc):
                raise
            last_error = exc
    raise last_error or RuntimeError("当期使用率概览卡渲染失败")


async def _draw_stage_page(report: UsageStageReport, *, rank_limit: int) -> bytes:
    ranked = () if report.insufficient else report.operators[:rank_limit]
    teams = () if report.insufficient else report.teams[:_TEAM_LIMIT]
    records = report.teams[:_RECORD_LIMIT] if report.insufficient else ()
    urls = _operator_urls(ranked) + _team_urls(teams) + _team_urls(records)
    await note_remote_assets(urls, namespace=REMOTE_ASSET_NAMESPACE)
    assets = await _prepare_assets(urls, inline=False)
    body = (
        _head(
            f"{report.family_label} · 使用率",
            "ENDFIELD / STAGE USAGE",
            _stage_subtitle(report),
            _SCOPE_LABELS.get(report.scope, report.scope or "群内统计"),
        )
        + _fresh_strip(report.latest_record_ts, report.snapshot_updated_at)
        + '<div class="wrap">'
        + _samples(_stage_sample_cells(report))
        + _stage_sections(report, assets.urls, ranked=ranked, teams=teams, records=records)
        + "</div>"
        + _footer(_footer_left(report.regions), "")
    )
    prepared = PreparedCardHtml(_page(body), assets.resources, USAGE_STATS_WIDTH)
    return await _draw_gallery_catalog(
        prepared, _USAGE_SELECTOR, _OVERFLOW_SELECTORS, "usage_stats"
    )


async def _draw_overview_page(
    report: UsageOverviewReport,
    stages: tuple[UsageStageSummary, ...],
    *,
    number: int,
    total: int,
) -> bytes:
    urls = [
        operator.avatar_url
        for stage in stages
        for operator in stage.leads
        if operator.avatar_url
    ]
    await note_remote_assets(urls, namespace=REMOTE_ASSET_NAMESPACE)
    assets = await _prepare_assets(urls, inline=False)
    page_note = f"第 {number} / {total} 页" if total > 1 else ""
    blocks = "".join(_stage_block(report, stage, assets.urls) for stage in stages)
    if not blocks:
        blocks = '<div class="thin">这一期还没有可统计的关卡</div>'
    body = (
        _head(
            f"{report.family_label} · 使用率总览",
            "ENDFIELD / SEASON OVERVIEW",
            _overview_subtitle(report),
            _SCOPE_LABELS.get(report.scope, report.scope or "群内统计"),
        )
        + _fresh_strip(
            report.latest_record_ts, report.snapshot_updated_at, tail="每关给 Top 3"
        )
        + '<div class="wrap">'
        + _samples(_overview_sample_cells(report))
        + _sect("本期关卡")
        + blocks
        + "</div>"
        + _footer(_footer_left(report.regions), page_note)
    )
    prepared = PreparedCardHtml(_page(body), assets.resources, USAGE_STATS_WIDTH)
    return await _draw_gallery_catalog(
        prepared, _USAGE_SELECTOR, _OVERFLOW_SELECTORS, "usage_stats"
    )


def _chunk_stages(
    stages: tuple[UsageStageSummary, ...], size: int
) -> list[tuple[UsageStageSummary, ...]]:
    if not stages:
        return [()]
    return [
        tuple(stages[index : index + size]) for index in range(0, len(stages), size)
    ]


def _operator_urls(operators: tuple[UsageOperator, ...]) -> list[str]:
    return [operator.avatar_url for operator in operators if operator.avatar_url]


def _team_urls(teams: tuple[UsageTeam, ...]) -> list[str]:
    return [
        member.avatar_url
        for team in teams
        for member in team.members
        if member.avatar_url
    ]


def _stage_subtitle(report: UsageStageReport) -> str:
    location = " / ".join(
        part for part in (report.scope_name, report.stage_name) if part
    )
    parts = [location, report.difficulty_label, report.activity_name]
    return " · ".join(part for part in parts if part)


def _overview_subtitle(report: UsageOverviewReport) -> str:
    parts = [report.scope_name, report.activity_name, report.difficulty_label]
    return " · ".join(part for part in parts if part)


def _stage_sample_cells(report: UsageStageReport) -> tuple[tuple[str, str, str], ...]:
    coverage = _coverage_text(
        report.coverage, report.sample_count, report.bound_role_count
    )
    return (
        ("有记录样本", str(report.sample_count), ""),
        ("绑定角色", str(report.bound_role_count), ""),
        ("覆盖率", coverage, ""),
        ("队伍组合", str(report.team_combo_total or len(report.teams)), ""),
    )


def _overview_sample_cells(
    report: UsageOverviewReport,
) -> tuple[tuple[str, str, str], ...]:
    statable = sum(1 for stage in report.stages if not stage.insufficient)
    return (
        ("有记录角色", str(report.recorded_role_count), ""),
        ("绑定角色", str(report.bound_role_count), ""),
        ("覆盖率", _overview_coverage(report), ""),
        ("可统计关卡", f"{statable} / {len(report.stages)}", ""),
    )


def _overview_coverage(report: UsageOverviewReport) -> str:
    """概览覆盖率:跨关去重的有记录角色 ÷ 绑定角色。"""
    bound = report.bound_role_count
    if bound <= 0:
        return "--"
    return _percent(min(1.0, report.recorded_role_count / bound))


def _stage_sections(
    report: UsageStageReport,
    icons: dict[str, str],
    *,
    ranked: tuple[UsageOperator, ...],
    teams: tuple[UsageTeam, ...],
    records: tuple[UsageTeam, ...],
) -> str:
    sections = [_sect("干员使用率")]
    if report.insufficient:
        sections.append(_insufficient_note(report))
        if records:
            sections.append(_sect(f"已有的 {len(records)} 条记录"))
            sections.append(_record_rows(records, icons))
        return "".join(sections)
    if ranked:
        sections.append(_rank_rows(ranked, icons))
        sections.append(_tail_line(report.operators[len(ranked) :]))
    else:
        sections.append('<div class="thin">这关还没有干员使用记录</div>')
    if teams:
        sections.append(_sect("常用队伍"))
        sections.append(_team_rows(teams, icons))
    return "".join(sections)


def _insufficient_note(report: UsageStageReport) -> str:
    heading, *hints = _insufficient_text(report)
    coverage = _coverage_text(
        report.coverage, report.sample_count, report.bound_role_count
    )
    paragraphs = "".join(f"<p>{esc(hint)}</p>" for hint in hints)
    return (
        '<div class="note">'
        f"<h3>{esc(heading)}</h3>"
        f"<p>本期有记录 <b>{report.sample_count}</b> / 群内绑定"
        f" <b>{report.bound_role_count}</b>"
        f" · 覆盖率 <b>{esc(coverage)}</b>。</p>"
        f"{paragraphs}"
        "</div>"
    )


def _insufficient_text(report: UsageStageReport) -> tuple[str, ...]:
    """(标题, 逐行说明);只说差多少、差在哪,不猜命令语法。"""
    if report.bound_role_count <= 0:
        return (
            "本群还没有绑定角色",
            "绑定游戏角色之后，这一关的使用率才会开始统计。",
        )
    if report.sample_count <= 0:
        return (
            "本群还没有人在这关留下记录",
            f"攒到 {_MIN_SAMPLES} 个角色的最佳记录才会出排行，现在是 0 / {_MIN_SAMPLES}。",
        )
    if report.sample_count < _MIN_SAMPLES:
        need = _MIN_SAMPLES - report.sample_count
        return (
            f"样本不足：{report.sample_count} / {_MIN_SAMPLES}",
            f"本群只有 {report.sample_count} 个角色在"
            f"「{report.stage_name} · {report.difficulty_label}」留下最佳记录，"
            "样本太少，排行会被 1 个人带偏。",
            f"再拉 {need} 人打一次这关就会出榜。",
        )
    return (
        "样本不足",
        f"这关目前只有 {report.sample_count} 条记录，还不足以给出稳定的使用率排行。",
    )


def _rank_rows(operators: tuple[UsageOperator, ...], icons: dict[str, str]) -> str:
    out: list[str] = []
    for index, operator in enumerate(operators, 1):
        share = 0.0 if operator.usage_rate is None else float(operator.usage_rate)
        share = max(0.0, min(1.0, share))
        css_class = (
            ("row gold", "row silver", "row bronze")[index - 1] if index <= 3 else "row"
        )
        out.append(
            f"""
<div class="{css_class}">
  <div class="track"></div>
  <div class="fill" style="width:{max(2.0, share * 100):.1f}%"></div>
  <div class="rank">{index:02d}</div>
  {_avatar(operator.avatar_url, operator.name, icons)}
  <div class="who"><b>{esc(operator.name)}</b><small>{esc(operator.profession or '未知职业')}{_stars(operator.rarity)}</small></div>
  <div class="val"><b>{_percent(operator.usage_rate)}</b><i>{operator.used_count} 人</i></div>
</div>"""
        )
    return '<div class="rows">' + "".join(out) + "</div>"


def _tail_line(rest: tuple[UsageOperator, ...]) -> str:
    if not rest:
        return ""
    ceiling = max(operator.used_count for operator in rest)
    return f'<div class="more">其余 {len(rest)} 名干员各被 {ceiling} 人以下使用</div>'


def _team_rows(teams: tuple[UsageTeam, ...], icons: dict[str, str]) -> str:
    out: list[str] = []
    for index, team in enumerate(teams, 1):
        out.append(
            f"""
<div class="team{' lead' if index == 1 else ''}">
  <div class="no">{index:02d}</div>
  <div class="squad">{_slots(team, icons)}</div>
  <div class="meta"><b>{_percent(team.rate)}</b>
    <i>平均用时 <b>{_fmt_pass_time(team.avg_pass_time)}</b> · {team.count} 次</i></div>
</div>"""
        )
    return '<div class="teams">' + "".join(out) + "</div>"


def _record_rows(teams: tuple[UsageTeam, ...], icons: dict[str, str]) -> str:
    """样本不足卡的「已有记录」:只给队伍与次数,不把 1 条记录写成 100%。"""
    out: list[str] = []
    for index, team in enumerate(teams, 1):
        out.append(
            f"""
<div class="team">
  <div class="no">{index:02d}</div>
  <div class="squad">{_slots(team, icons)}</div>
  <div class="meta"><b>{len(team.members)} 人记录</b>
    <i>{team.count} 次 · 平均用时 {_fmt_pass_time(team.avg_pass_time)}</i></div>
</div>"""
        )
    return '<div class="teams">' + "".join(out) + "</div>"


def _slots(team: UsageTeam, icons: dict[str, str]) -> str:
    members = team.members[:4]
    slots = "".join(
        _avatar(member.avatar_url, member.name, icons, "slot") for member in members
    )
    return slots + '<div class="slot empty"></div>' * (4 - len(members))


def _stage_block(
    report: UsageOverviewReport,
    stage: UsageStageSummary,
    icons: dict[str, str],
) -> str:
    difficulty = DIFFICULTY_LABELS.get(stage.difficulty, stage.difficulty)
    bound = stage.bound_role_count or report.bound_role_count
    coverage = _coverage_text(None, stage.sample_count, bound)
    if stage.leads:
        hits = "".join(
            f'<div class="hit{" lead" if index == 1 else ""}">'
            f"{_avatar(operator.avatar_url, operator.name, icons)}"
            f'<div class="nm"><b>{esc(operator.name)}</b>'
            f"<i>{_percent(operator.usage_rate)} · {operator.used_count} 人</i></div></div>"
            for index, operator in enumerate(stage.leads[:3], 1)
        )
        body = f'<div class="top3">{hits}</div>'
    else:
        body = f'<div class="thin">{esc(_stage_thin_hint(stage))}</div>'
    return f"""
<div class="stage">
  <div class="stage-head">
    <b>{esc(stage.stage_name)}</b>
    <span class="tag">{esc(difficulty)}</span>
    <span class="tag">样本 {stage.sample_count}</span>
    <span class="cov">覆盖率 {esc(coverage)}</span>
  </div>
  {body}
</div>"""


def _stage_thin_hint(stage: UsageStageSummary) -> str:
    if stage.sample_count <= 0:
        return "本群还没有人在这关留下记录"
    if stage.insufficient:
        need = max(1, _MIN_SAMPLES - stage.sample_count)
        return (
            f"样本不足：{stage.sample_count} / {_MIN_SAMPLES}"
            f" · 再拉 {need} 人打这关就能进榜"
        )
    return "这关还没有干员使用记录"


def _avatar(url: str, name: str, icons: dict[str, str], cls: str = "pic") -> str:
    """远程头像换成截图可达的资源;缺图只画名字首字,不印任何内部标识。"""
    src = icons.get(url, "") if url else ""
    if src:
        return f'<div class="{cls}"><img src="{esc_attr(src)}" alt=""></div>'
    return f'<div class="{cls}"><em>{esc((name or "?")[:1])}</em></div>'


def _stars(rarity: int) -> str:
    count = max(1, min(6, int(rarity or 0)))
    star = _local_image_data_url(ASSET_DIR / "rarity-star.png")
    if not star:
        return '<span class="stars-fallback">' + "★" * count + "</span>"
    img = f'<img class="rarity-star" src="{esc_attr(star)}" alt="star">'
    return f'<span class="stars">{img * count}</span>'


def _fmt_pass_time(seconds: int) -> str:
    total = int(seconds or 0)
    if total <= 0:
        return "—"
    minutes, rest = divmod(total, 60)
    return f"{minutes}:{rest:02d}"


def _percent(rate: float | None) -> str:
    if rate is None:
        return "--"
    return f"{max(0.0, min(1.0, float(rate))) * 100:.0f}%"


def _coverage_text(
    coverage: float | None, sample_count: int, bound_role_count: int
) -> str:
    if coverage is not None:
        return _percent(coverage)
    if bound_role_count > 0:
        return _percent(min(1.0, sample_count / bound_role_count))
    return "--"


def _relative_time(stamp: int, *, now: int | None = None) -> str:
    """「N 天前」;0 或缺失写成「时间未知」,不画出 1970。"""
    seconds = int(stamp or 0)
    if seconds <= 0:
        return "时间未知"
    delta = max(0, int(now if now is not None else time.time()) - seconds)
    if delta < 60:
        return "刚刚"
    if delta < 3600:
        return f"{delta // 60} 分钟前"
    if delta < 86400:
        return f"{delta // 3600} 小时前"
    return f"{delta // 86400} 天前"


def _is_stale(stamp: int) -> bool:
    seconds = int(stamp or 0)
    return seconds > 0 and time.time() - seconds > _STALE_SECONDS


def _footer_left(regions: tuple[str, ...]) -> str:
    parts = ["数据来源 <b>森空岛</b>", "统计范围 <b>本群已绑定角色</b>"]
    if regions:
        labels = " / ".join(
            _REGION_LABELS.get(region, region) for region in dict.fromkeys(regions)
        )
        parts.append(f"区域 <b>{esc(labels)}</b>")
    return " · ".join(parts)


def _head(title: str, kicker: str, sub: str, scope: str) -> str:
    return f"""
<div class="head">
  <div class="scope">{esc(scope)}</div>
  <div class="kicker">{esc(kicker)}</div>
  <h1 class="title">{esc(title)}</h1>
  <div class="sub">{esc(sub)}</div>
</div>"""


def _fresh_strip(record_ts: int, snapshot_ts: int, *, tail: str = "") -> str:
    record = esc(_relative_time(record_ts))
    if _is_stale(record_ts):
        record = f'<b style="color:#c9a227">{record}</b>'
    else:
        record = f"<b>{record}</b>"
    tail_html = f'<span class="tail">{esc(tail)}</span>' if tail else ""
    return (
        '<div class="fresh"><span class="dot"></span>'
        f"最佳记录口径 · 最新记录 {record} · 快照 <b>{esc(_relative_time(snapshot_ts))}</b>"
        f"{tail_html}</div>"
    )


def _samples(items: tuple[tuple[str, str, str], ...]) -> str:
    cells = "".join(
        f'<div class="sample"><span>{esc(label)}</span><b>{esc(value)}</b>'
        + (f"<i>{esc(note)}</i>" if note else "")
        + "</div>"
        for label, value, note in items
    )
    return f'<div class="samples">{cells}</div>'


def _sect(title: str, note: str = "") -> str:
    note_html = f"<em>{esc(note)}</em>" if note else ""
    return f'<div class="sect"><h2>{esc(title)}</h2>{note_html}</div>'


def _footer(left: str, right: str) -> str:
    tail = f'<span class="right">{esc(right)}</span>' if right else ""
    return f"<footer>{left}{tail}</footer>"


def _page(body: str) -> str:
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<style>{_css()}</style></head>"
        "<body><div class='page'><div class='card'>"
        + body
        + "</div></div></body></html>"
    )


def _css() -> str:
    width = USAGE_STATS_WIDTH
    return f"""
* {{ box-sizing:border-box; -webkit-font-smoothing:antialiased; }}
html,body {{ margin:0; width:{width}px; background:#eef1f2; color:#2b2f33;
  font-family:"Microsoft YaHei","PingFang SC","HarmonyOS Sans SC","Noto Sans SC",Arial,sans-serif; }}
.page {{ width:{width}px; padding:30px;
  background:
    linear-gradient(90deg,rgba(29,34,39,.065) 1px,transparent 1px) 0 0/40px 40px,
    linear-gradient(0deg,rgba(29,34,39,.065) 1px,transparent 1px) 0 0/40px 40px,
    linear-gradient(135deg,#f8f9f6,#e6eaeb); }}
.card {{ width:{width - 60}px; background:#fefefe; border-radius:18px; overflow:hidden;
  box-shadow:0 12px 30px rgba(23,27,31,.13), 0 0 0 1px rgba(23,27,31,.05); }}

/* ---------- 头部 ---------- */
.head {{ padding:44px 44px 38px; background:#292929; color:#fff; position:relative; }}
.kicker {{ font-size:20px; font-weight:600; letter-spacing:.34em; color:rgba(255,255,255,.46); }}
.title {{ margin:14px 0 0; font-size:56px; line-height:1.06; font-weight:800; letter-spacing:-.01em; }}
.sub {{ margin-top:14px; font-size:26px; font-weight:500; color:rgba(255,255,255,.6); }}
.scope {{ position:absolute; right:44px; top:48px; padding:8px 16px;
  border:1px solid rgba(248,213,46,.75); color:#f8d52e; font-size:20px; font-weight:700; letter-spacing:.12em; }}
.head::after {{ content:""; position:absolute; left:0; right:0; bottom:0; height:5px;
  background:#f8d52e; }}

/* ---------- 时效 ---------- */
.fresh {{ padding:22px 44px; display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  font-size:22px; font-weight:500; color:#7c848b; border-bottom:1px solid #eceff1; }}
.fresh .dot {{ width:9px; height:9px; background:#f8d52e; border-radius:50%; flex:none; }}
.fresh b {{ color:#2b2f33; font-weight:700; }}
.fresh .tail {{ margin-left:auto; color:#9aa1a7; }}

/* ---------- 样本 ---------- */
.wrap {{ padding:26px 44px 0; }}
.samples {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); padding:22px 8px;
  background:#f4f6f8; border-radius:16px; }}
.sample {{ padding:0 22px; }}
.sample + .sample {{ border-left:1px solid #e1e6ea; }}
.sample span {{ display:block; font-size:21px; font-weight:600; color:#8b9399; }}
.sample b {{ display:block; margin-top:8px; font-size:42px; line-height:1;
  font-weight:800; color:#282c30; letter-spacing:-.02em; }}
.sample i {{ display:block; margin-top:7px; font-size:19px; font-style:normal;
  font-weight:500; color:#a2a9ae; line-height:1.35; }}

/* ---------- 区块标题 ---------- */
.sect {{ margin-top:34px; display:flex; align-items:flex-end; gap:14px; }}
.sect::before {{ content:""; width:6px; height:26px; background:#f8d52e; border-radius:2px; }}
.sect h2 {{ margin:0; font-size:31px; font-weight:800; color:#24282c; letter-spacing:-.01em; }}
.sect em {{ margin-left:auto; padding-bottom:4px; font-size:20px; font-style:normal;
  font-weight:500; color:#9aa1a7; }}

/* ---------- 排行 ---------- */
.rows {{ margin-top:16px; }}
.row {{ position:relative; display:grid; grid-template-columns:40px 66px minmax(0,1fr) auto;
  align-items:center; gap:16px; padding:15px 24px 15px 16px; border-radius:12px; }}
.row + .row {{ margin-top:2px; }}
.row .track {{ position:absolute; inset:0; border-radius:12px; background:#f4f6f8; }}
.row .fill {{ position:absolute; inset:0 auto 0 0; border-radius:12px;
  background:linear-gradient(90deg,#e6ecf1,#eff3f6); }}

.row > * {{ position:relative; }}
.pic {{ width:66px; height:66px; border-radius:12px; overflow:hidden; display:grid;
  place-items:center; background:#e7ebee; }}
.pic img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.pic em {{ font-size:26px; font-weight:700; color:#9aa1a7; font-style:normal; }}
.who b {{ display:flex; align-items:center; gap:10px; font-size:36px; font-weight:700;
  color:#22262a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.rank {{ font-size:22px; font-weight:800; color:#b6bdc2; font-variant-numeric:tabular-nums; }}
.row.gold .fill {{ background:linear-gradient(90deg,rgba(240,200,28,.42),rgba(240,200,28,.12)); }}
.row.silver .fill {{ background:linear-gradient(90deg,rgba(178,190,201,.85),rgba(178,190,201,.35)); }}
.row.bronze .fill {{ background:linear-gradient(90deg,rgba(196,131,72,.42),rgba(196,131,72,.14)); }}
.row.gold .rank {{ color:#c9a227; }}
.row.silver .rank {{ color:#8b96a1; }}
.row.bronze .rank {{ color:#b06f33; }}
.who small {{ display:flex; align-items:center; gap:8px; margin-top:7px; font-size:23px;
  font-weight:600; color:#8f979d; }}
.who .stars {{ display:inline-flex; align-items:center; gap:4px; }}
.who .rarity-star {{ display:block; width:32px; height:32px; object-fit:contain;
  filter: drop-shadow(0 1px 0 rgba(255,255,255,.7)) drop-shadow(0 1px 2px rgba(23,27,31,.28)); }}
.val {{ text-align:right; }}
.val b {{ font-size:41px; font-weight:800; color:#22262a; font-variant-numeric:tabular-nums;
  letter-spacing:-.02em; }}
.val i {{ display:block; margin-top:3px; font-size:20px; font-style:normal;
  font-weight:500; color:#a2a9ae; }}
.more {{ margin-top:12px; padding:14px 18px; background:#f4f6f8; border-radius:12px;
  font-size:21px; font-weight:500; color:#8b9399; text-align:center; }}

/* ---------- 队伍 ---------- */
.teams {{ margin-top:16px; }}
.team {{ display:grid; grid-template-columns:44px 1fr auto; align-items:center; gap:16px;
  padding:14px 16px; border-radius:12px; background:#f4f6f8; }}
.team + .team {{ margin-top:8px; }}
.team.lead {{ background:linear-gradient(90deg,rgba(248,213,46,.2),#f4f6f8 62%); }}
.team .no {{ font-size:24px; font-weight:800; color:#b6bdc2; }}
.team.lead .no {{ color:#c9a227; }}
.squad {{ display:flex; gap:8px; }}
.slot {{ width:56px; height:56px; border-radius:10px; overflow:hidden; display:grid;
  place-items:center; background:#e2e7ea; }}
.slot img {{ width:100%; height:100%; object-fit:cover; display:block; }}
.slot em {{ font-size:22px; font-weight:700; color:#9aa1a7; font-style:normal; }}
.slot.empty {{ background:repeating-linear-gradient(45deg,#e4e9ec 0 6px,#dbe1e5 6px 12px); }}
.team .meta {{ text-align:right; }}
.team .meta b {{ font-size:30px; font-weight:800; color:#22262a; }}
.team .meta i {{ display:block; margin-top:5px; font-size:20px; font-style:normal;
  font-weight:500; color:#a2a9ae; font-variant-numeric:tabular-nums; }}
.team .meta i b {{ font-size:22px; font-weight:700; color:#6d757b; }}

/* ---------- 提示块 ---------- */
.note {{ margin-top:16px; padding:26px 28px; background:#f4f6f8; border-radius:16px; }}
.note h3 {{ margin:0 0 12px; font-size:33px; font-weight:800; color:#24282c; }}
.note p {{ margin:9px 0 0; font-size:24px; line-height:1.7; font-weight:500; color:#6f777d; }}
.note p b {{ color:#2b2f33; font-weight:700; }}
.note code {{ padding:4px 10px; border-radius:6px; background:#292929; color:#f8d52e;
  font-family:Consolas,monospace; font-size:22px; }}

/* ---------- 概览 ---------- */
.stage {{ padding:20px 22px; border-radius:16px; background:#f4f6f8; }}
.stage + .stage {{ margin-top:10px; }}
.stage-head {{ display:flex; align-items:center; gap:10px; }}
.stage-head b {{ font-size:29px; font-weight:800; color:#24282c; }}
.tag {{ padding:3px 10px; border-radius:6px; background:#e6ebee; color:#7c848b; font-size:19px;
  font-weight:700; }}
.tag.hot {{ background:#f8d52e; color:#3a3320; }}
.stage-head span.cov {{ margin-left:auto; font-size:20px; font-weight:600; color:#9aa1a7; }}
.top3 {{ display:flex; gap:14px; margin-top:14px; }}
.hit {{ display:flex; align-items:center; gap:10px; flex:1; min-width:0; }}
.hit .pic {{ width:46px; height:46px; border-radius:10px; }}
.hit .nm {{ min-width:0; }}
.hit .nm b {{ display:block; font-size:23px; font-weight:700; color:#2b2f33; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; }}
.hit .nm i {{ font-size:20px; font-style:normal; font-weight:600; color:#9aa1a7; }}
.hit.lead .nm i {{ color:#c9a227; }}
.thin {{ margin-top:12px; padding:12px 16px; border-radius:10px; background:#eef1f3;
  font-size:21px; font-weight:500; color:#8b9399; }}

/* ---------- 版式补充:长关卡名截断,不撑破 .stage ---------- */
.stage-head > b {{ flex:0 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }}
.stage-head > .tag, .stage-head > .cov {{ flex:none; white-space:nowrap; }}

/* ---------- 页脚 ---------- */
footer {{ margin-top:30px; padding:20px 44px 26px; display:flex; align-items:center;
  gap:12px; font-size:19px; font-weight:500; color:#a2a9ae; border-top:1px solid #eceff1; }}
footer b {{ color:#6f777d; font-weight:700; }}
footer .right {{ margin-left:auto; }}
"""
