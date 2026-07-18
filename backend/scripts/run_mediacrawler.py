from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path


async def _do_not_skip_failed_api_login_check(self) -> bool:
    # MediaCrawler only constructs the login flow after its API pong check fails.
    # Public XHS pages also contain profile links, so UI-only checks are false positives.
    return False


# Platforms whose create_*_client reads navigator.userAgent off the live page.
# The homepage can still be navigating right after goto() (SPA redirects), which
# destroys the JS execution context and crashes the run with exit 1 — most
# visible in CDP mode. Map each to (module, crawler class, create-method).
_NAV_SENSITIVE_CLIENTS = {
    "dy": ("media_platform.douyin.core", "DouYinCrawler", "create_douyin_client"),
    "tieba": ("media_platform.tieba.core", "TieBaCrawler", "create_tieba_client"),
}


def _platform_arg() -> str:
    try:
        return sys.argv[sys.argv.index("--platform") + 1]
    except (ValueError, IndexError):
        return ""


def _patch_navigation_safety(platform: str) -> None:
    """Wait for the page to settle and retry client creation so the
    ``navigator.userAgent`` read doesn't race a homepage navigation."""
    target = _NAV_SENSITIVE_CLIENTS.get(platform)
    if target is None:
        return
    module_name, class_name, method_name = target
    module = importlib.import_module(module_name)
    crawler_cls = getattr(module, class_name)
    original_create = getattr(crawler_cls, method_name)

    async def safe_create_client(self, *args, **kwargs):
        try:
            await self.context_page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                return await original_create(self, *args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - narrowed by message below
                last_error = exc
                message = str(exc).lower()
                if attempt < 3 and ("execution context was destroyed" in message or "navigation" in message):
                    await asyncio.sleep(1.5)
                    continue
                raise
        assert last_error is not None
        raise last_error

    setattr(crawler_cls, method_name, safe_create_client)


def main() -> int:
    crawler_root = Path.cwd()
    if str(crawler_root) not in sys.path:
        sys.path.insert(0, str(crawler_root))

    crawler_main = importlib.import_module("main")
    login_module = importlib.import_module("media_platform.xhs.login")
    login_module.XiaoHongShuLogin.quick_check_login_state = (
        _do_not_skip_failed_api_login_check
    )

    _patch_navigation_safety(_platform_arg())

    return int(crawler_main.run_cli())


if __name__ == "__main__":
    raise SystemExit(main())
