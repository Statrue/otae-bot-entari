"""用系统 Edge 渲染 AKEData 奖章模块，抓真实图标/数据 URL，反推图标路径规则。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

SITE = "https://cf.akedata.top/"


async def main() -> None:
    png_urls: set[str] = set()
    data_urls: set[str] = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        def on_response(resp):
            url = resp.url
            if ".png" in url and "/public/" in url:
                png_urls.add(url)
            if "/achievement" in url and (".json" in url or "manifest" in url):
                data_urls.add(url)

        page.on("response", on_response)

        await page.goto(SITE, wait_until="domcontentloaded", timeout=60000)
        # 等 SPA + 数据加载
        await page.wait_for_timeout(15000)
        # 点奖章模块卡片（尝试多种选择器）
        clicked = False
        for sel in ["text=查看蚀刻章数据", "text=奖章", "text=🏅"]:
            try:
                await page.locator(sel).first.click(timeout=4000)
                clicked = True
                print("clicked:", sel)
                break
            except Exception:
                continue
        if not clicked:
            # 试试直接深链
            try:
                await page.goto(SITE + "#achievement", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
        await page.wait_for_timeout(15000)
        await browser.close()

    print("\n=== 抓到的 achievement 数据 URL ===")
    for u in sorted(data_urls):
        print(" ", u)
    print("\n=== 抓到的 png URL（含 achievement/medal）===")
    for u in sorted(png_urls):
        if "achievement" in u or "medal" in u:
            print(" ", u)
    print("\n=== 全部 png URL（前 20）===")
    for u in sorted(png_urls)[:20]:
        print(" ", u)


if __name__ == "__main__":
    asyncio.run(main())
