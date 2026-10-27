"""更新日志卡片：套用 help 同款外框与插画图库，复用 ``art_card`` 的随机插画渲染。

外框（横幅、虚化底、磨砂面板、立牌）、主题、图库、选图与渲染都在
``otae_bot/infrastructure/rendering/art_frame.py`` / ``art_card.py``，与 help 和其他同模板卡片
共用一份；这里只提供面板内容的样式。
"""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path

from otae_bot.infrastructure.rendering import art_card, art_frame

from .presentation import ChangelogPage

CARD_WIDTH = art_card.CARD_WIDTH
CARD_MAX_HEIGHT = art_card.CARD_MAX_HEIGHT
DEVICE_SCALE_FACTOR = art_card.DEVICE_SCALE_FACTOR
MIN_CARD_HEIGHT = art_card.DEFAULT_MIN_CARD_HEIGHT
CSP = art_card.CSP
FOOTNOTE = "每个版本改了什么，都在这里"
ASSETS = Path(__file__).parent / "assets"


@lru_cache(maxsize=1)
def _styles() -> str:
    return (ASSETS / "card.css").read_text(encoding="utf-8")


def to_card(page: ChangelogPage) -> art_card.ArtCard:
    return art_card.ArtCard(
        title=page.title,
        subtitle=page.subtitle,
        panel_html=f'<article>{page.body}</article><p class="cl-foot">{FOOTNOTE}</p>',
        css=_styles(),
        min_card_height=MIN_CARD_HEIGHT,
        document_title=f"{page.title} · {page.section}",
    )


def page_html(page: ChangelogPage, art: art_frame.Artwork | None = None) -> str:
    """把一张卡片渲染成完整的离线 HTML 文档。不给插画时用图库的默认插画。"""
    return art_card.card_html(to_card(page), art)


async def render_page(page: ChangelogPage, *, rng: random.Random | None = None) -> bytes:
    """渲染单张卡片为 PNG，插画与 help 一样随机。"""
    return await art_card.render_card(to_card(page), rng=rng)


__all__ = [
    "CARD_MAX_HEIGHT",
    "CARD_WIDTH",
    "DEVICE_SCALE_FACTOR",
    "MIN_CARD_HEIGHT",
    "page_html",
    "render_page",
    "to_card",
]
