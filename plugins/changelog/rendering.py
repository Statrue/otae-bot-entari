"""离线 HTML/CSS 卡片：套用 help 卡片的外框与插画图库，复用项目共享的浏览器渲染器。

外框（横幅、虚化底、磨砂面板、立牌）、主题、图库和选图规则都来自
``otae_bot.infrastructure.rendering.art_frame``，与 help 共用同一份，这里只写面板内容。

插画和 help 一样每次随机挑。立牌能露出多少主体取决于卡片高度，而高度要渲染完
才知道，所以先随机挑一张出图，量出高度后如果这张在立牌里露得太少，就从合适的
插画里重挑一张再出一次。量到的高度按页面内容记下来，同一张卡片下次直接按它挑。
"""

from __future__ import annotations

import hashlib
import io
import random
import tempfile
from functools import lru_cache
from html import escape
from pathlib import Path

from otae_bot.infrastructure.rendering import art_frame
from otae_bot.infrastructure.rendering.browser import screenshot_web_element

from .presentation import ChangelogPage

THEME = art_frame.HelpTheme()
#: 与 help 卡片同宽，按 1x 渲染（help 也是 1x）。
CARD_WIDTH = THEME.page_width
CARD_MAX_HEIGHT = 6000
DEVICE_SCALE_FACTOR = 1
#: help 卡片的最小高度是给整页命令表定的；更新日志内容短的页面用不着那么高。
MIN_CARD_HEIGHT = 460
FOOTNOTE = "每个版本改了什么，都在这里"
ASSETS = Path(__file__).parent / "assets"

#: 字体和插画都是仓库里的本地文件，浏览器直接按 file:// 读取，全程不联网。
#: 不走 BrowserResource 拦截：两份 8 MB 字体每次经拦截传给浏览器，单张要多花约 0.6 秒。
CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; font-src file:; "
    "img-src file:; base-uri 'none'; form-action 'none'"
)

_HEIGHT_MEMORY = 256
_heights: dict[str, int] = {}


@lru_cache(maxsize=1)
def _styles() -> str:
    """面板内容的样式。主题色取自 HelpTheme，help 改配色时这里跟着变。"""
    variables = (
        f":root{{--accent:{THEME.accent};--accent-soft:{THEME.accent_soft};"
        f"--heading:{THEME.heading_color};--body:{THEME.body_color}}}"
    )
    return variables + (ASSETS / "card.css").read_text(encoding="utf-8")


def page_html(page: ChangelogPage, art: art_frame.Artwork | None = None) -> str:
    """把一张卡片渲染成完整的离线 HTML 文档。不给插画时用图库的默认插画。"""
    art = art or art_frame.shared_gallery().default_artwork()
    panel = f'<article>{page.body}</article><p class="cl-foot">{FOOTNOTE}</p>'
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        f"<title>{escape(page.title)} · {escape(page.section)}</title><style>\n"
        f"{art_frame.font_face_css(THEME)}\n"
        f"{art_frame.frame_css(THEME, art, min_card_height=MIN_CARD_HEIGHT)}\n"
        f"{_styles()}</style></head>"
        + art_frame.frame_body(page.title, art_frame.subtitle_html(page.subtitle), art, panel, THEME)
    )


def _candidates(height: int | None) -> tuple[art_frame.Artwork, ...]:
    """这个高度下立牌还能露出主体的插画；高度未知时给全部。规则与 help 相同。"""
    return art_frame.candidates(height, art_frame.shared_gallery(), THEME)


def _page_key(page: ChangelogPage) -> str:
    return hashlib.sha1(f"{page.title}\0{page.subtitle}\0{page.body}".encode()).hexdigest()


def _remember(key: str, height: int) -> None:
    if len(_heights) >= _HEIGHT_MEMORY and key not in _heights:
        _heights.clear()
    _heights[key] = height


async def _shoot(page: ChangelogPage, art: art_frame.Artwork) -> bytes:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", encoding="utf-8", delete=False
    ) as file:
        file.write(page_html(page, art))
        path = Path(file.name)
    try:
        return await screenshot_web_element(
            path.as_uri(),
            ".page",
            viewport=(CARD_WIDTH, 900),
            max_height=CARD_MAX_HEIGHT,
            device_scale_factor=DEVICE_SCALE_FACTOR,
            strict_max_height=True,
            wait_for_images=True,
            wait_for_fonts=True,
            settle_ms=0,
        )
    finally:
        path.unlink(missing_ok=True)


def _png_height(png: bytes) -> int:
    from PIL import Image

    with Image.open(io.BytesIO(png)) as image:
        return image.height


async def render_page(page: ChangelogPage, *, rng: random.Random | None = None) -> bytes:
    """渲染单张卡片为 PNG，插画随机。"""
    rng = rng or random
    key = _page_key(page)
    art = rng.choice(_candidates(_heights.get(key)))
    png = await _shoot(page, art)
    height = _png_height(png)
    _remember(key, height)
    fitting = _candidates(height)
    if art not in fitting:
        png = await _shoot(page, rng.choice(fitting))
    return png


__all__ = [
    "CARD_MAX_HEIGHT",
    "CARD_WIDTH",
    "DEVICE_SCALE_FACTOR",
    "MIN_CARD_HEIGHT",
    "page_html",
    "render_page",
]
