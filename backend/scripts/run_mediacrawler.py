from __future__ import annotations

import importlib
import sys
from pathlib import Path


async def _do_not_skip_failed_api_login_check(self) -> bool:
    # MediaCrawler only constructs the login flow after its API pong check fails.
    # Public XHS pages also contain profile links, so UI-only checks are false positives.
    return False


def main() -> int:
    crawler_root = Path.cwd()
    if str(crawler_root) not in sys.path:
        sys.path.insert(0, str(crawler_root))

    crawler_main = importlib.import_module("main")
    login_module = importlib.import_module("media_platform.xhs.login")
    login_module.XiaoHongShuLogin.quick_check_login_state = (
        _do_not_skip_failed_api_login_check
    )
    return int(crawler_main.run_cli())


if __name__ == "__main__":
    raise SystemExit(main())
