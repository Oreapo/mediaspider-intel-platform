from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path


async def _do_not_skip_failed_api_login_check(self) -> bool:
    # MediaCrawler only constructs the login flow after its API pong check fails.
    # Public XHS pages also contain profile links, so UI-only checks are false positives.
    return False


def _platform_arg() -> str:
    try:
        return sys.argv[sys.argv.index("--platform") + 1]
    except (ValueError, IndexError):
        return ""


def _patch_douyin_navigation_safety() -> None:
    """Make Douyin client creation resilient to the homepage's post-goto navigation.

    Douyin's home page keeps navigating (SPA redirects) after ``goto`` returns,
    and ``create_douyin_client`` immediately does
    ``context_page.evaluate("() => navigator.userAgent")``. When the evaluate
    races the navigation, Playwright raises "Execution context was destroyed,
    most likely because of a navigation" and the run exits with code 1 — most
    visible in CDP mode. Wait for the page to settle and retry the (idempotent)
    client creation so the User-Agent read lands on a live context.
    """
    core = importlib.import_module("media_platform.douyin.core")
    crawler_cls = core.DouYinCrawler
    original_create = crawler_cls.create_douyin_client

    async def safe_create_douyin_client(self, httpx_proxy):
        try:
            await self.context_page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                return await original_create(self, httpx_proxy)
            except Exception as exc:  # noqa: BLE001 - narrow by message below
                last_error = exc
                message = str(exc).lower()
                if attempt < 3 and ("execution context was destroyed" in message or "navigation" in message):
                    await asyncio.sleep(1.5)
                    continue
                raise
        assert last_error is not None
        raise last_error

    crawler_cls.create_douyin_client = safe_create_douyin_client


def main() -> int:
    crawler_root = Path.cwd()
    if str(crawler_root) not in sys.path:
        sys.path.insert(0, str(crawler_root))

    crawler_main = importlib.import_module("main")
    login_module = importlib.import_module("media_platform.xhs.login")
    login_module.XiaoHongShuLogin.quick_check_login_state = (
        _do_not_skip_failed_api_login_check
    )

    if _platform_arg() == "dy":
        _patch_douyin_navigation_safety()

    return int(crawler_main.run_cli())


if __name__ == "__main__":
    raise SystemExit(main())
