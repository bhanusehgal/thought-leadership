from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from .artifacts import item_dir


class PublishError(RuntimeError):
    pass


async def _publish_async(article: dict[str, Any], dry_run: bool = False) -> tuple[str, Path]:
    screenshot_path = item_dir(article["id"]) / "published.png"
    if dry_run:
        screenshot_path.write_text("dry-run screenshot placeholder", encoding="utf-8")
        return (f"https://medium.com/@dry-run/{article['id']}", screenshot_path)

    session_cookie = os.getenv("MEDIUM_SESSION_COOKIE", "").strip()
    medium_email = os.getenv("MEDIUM_EMAIL", "").strip()
    medium_password = os.getenv("MEDIUM_PASSWORD", "").strip()

    if not session_cookie and not (medium_email and medium_password):
        raise PublishError(
            "Missing Medium credentials. Set MEDIUM_SESSION_COOKIE or MEDIUM_EMAIL + MEDIUM_PASSWORD."
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        if session_cookie:
            await context.add_cookies(
                [
                    {
                        "name": "sid",
                        "value": session_cookie,
                        "domain": ".medium.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                    }
                ]
            )
        else:
            await page.goto("https://medium.com/m/signin", wait_until="domcontentloaded")
            await page.fill('input[type="email"]', medium_email)
            await page.click('button:has-text("Continue")')
            await page.wait_for_timeout(1000)
            if await page.locator('input[type="password"]').count() > 0:
                await page.fill('input[type="password"]', medium_password)
                await page.click('button:has-text("Sign in")')
            await page.wait_for_timeout(4000)

        await page.goto("https://medium.com/new-story", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await page.keyboard.type(article["title"])
        await page.keyboard.press("Enter")
        await page.keyboard.press("Enter")
        await page.keyboard.type(article["body_markdown"])
        await page.wait_for_timeout(1000)

        publish_buttons = page.locator('button:has-text("Publish")')
        if await publish_buttons.count() == 0:
            raise PublishError("Medium publish button not found. UI selectors may need update.")
        await publish_buttons.first.click()
        await page.wait_for_timeout(1000)
        confirm = page.locator('button:has-text("Publish now"), button:has-text("Publish")')
        if await confirm.count() == 0:
            raise PublishError("Publish confirmation button not found.")
        await confirm.first.click()
        await page.wait_for_timeout(5000)
        url = page.url
        await page.screenshot(path=str(screenshot_path), full_page=True)
        await browser.close()

    return (url, screenshot_path)


def publish_to_medium(article: dict[str, Any], dry_run: bool = False) -> tuple[str, Path]:
    return asyncio.run(_publish_async(article, dry_run=dry_run))
