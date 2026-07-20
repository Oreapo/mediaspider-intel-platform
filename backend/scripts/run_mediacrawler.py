from __future__ import annotations

import asyncio
import importlib
import re
import sys
from pathlib import Path


def _collapse_cjk_spaces(text: str) -> str:
    """Keyword <em> highlights split text nodes and leave stray spaces around
    the term; drop whitespace that sits between two adjacent CJK characters."""
    return re.sub(r"(?<=[一-鿿])\s+(?=[一-鿿])", "", text)


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


def _patch_tieba_search(platform: str) -> None:
    """Make anonymous tieba keyword search work again.

    Tieba's qrcode login DOM is broken upstream and its search/post pages are
    public, so collection runs on a guest session. Three things changed on
    Baidu's side that this repairs:

    * Login is forced whenever the cookie ``pong`` check fails — pin it to
      ``True`` so the guest session proceeds instead of hanging on login.
    * Search results now render into ``div.threadcardclass`` cards via JS; the
      bundled parser still looks for the retired ``div.s_post`` markup (0 posts).
      Give the SPA time to settle and parse the current card structure.
    * The full post body lives on each ``/p/<id>`` detail page, but the bundled
      detail parser targets retired markup and raises "list index out of range".
      Read the current OP container ourselves and merge the body into the
      search-level note so every record carries metadata *and* full text.
    * Comments reported 0 without ever loading a page: the bundled pager is
      gated on ``total_replay_page``, which nothing populates, and its parser
      targets the classic ``lzl_single_post`` markup. Parse today's
      ``pb-comment-item`` cards off the already-loaded detail HTML instead.

    Sub-comments (楼中楼) are not collected; the platform leaves them off by
    default.
    """
    if platform != "tieba":
        return

    # Guest session: report "logged in" so the broken login flow never runs.
    client_module = importlib.import_module("media_platform.tieba.client")

    async def _always_logged_in(self, *args, **kwargs) -> bool:
        return True

    client_module.BaiduTieBaClient.pong = _always_logged_in

    config = importlib.import_module("config")
    try:
        if int(getattr(config, "CRAWLER_MAX_SLEEP_SEC", 0)) < 12:
            config.CRAWLER_MAX_SLEEP_SEC = 12
    except Exception:
        pass

    help_module = importlib.import_module("media_platform.tieba.help")
    tieba_note_cls = importlib.import_module("model.m_baidu_tieba").TiebaNote

    def extract_search_note_list(page_content: str):
        from parsel import Selector

        selector = Selector(text=page_content)
        notes = []
        for card in selector.xpath("//div[contains(@class,'threadcardclass')]"):
            href = card.xpath(".//a/@href").get(default="")
            match = re.search(r"/p/(\d+)", href)
            if not match:
                continue
            note_id = match.group(1)

            def joined(xpath: str) -> str:
                text = " ".join(
                    part.strip() for part in card.xpath(xpath).getall() if part.strip()
                )
                return _collapse_cjk_spaces(text)

            # "<author> 发布于 <date>"
            top_title = joined(".//*[contains(@class,'top-title')]//text()")
            author, publish_time = "", ""
            head = re.match(r"^(.*?)\s*发布于\s*(.+)$", top_title)
            if head:
                author, publish_time = head.group(1).strip(), head.group(2).strip()

            title = joined(".//*[contains(@class,'title-content-wrap')]//text()")
            desc = joined(".//*[contains(@class,'thread-content-box')]//text()") or title
            forum = joined(".//*[contains(@class,'forum-name-text')]//text()")

            notes.append(
                tieba_note_cls(
                    note_id=note_id,
                    title=title or forum,
                    desc=desc,
                    note_url=f"https://tieba.baidu.com/p/{note_id}",
                    user_nickname=author,
                    user_link="",
                    tieba_name=forum,
                    tieba_link="",
                    publish_time=publish_time,
                )
            )
        return notes

    help_module.TieBaExtractor.extract_search_note_list = staticmethod(extract_search_note_list)

    # Search cards carry the metadata (title/forum/author/time) but only a
    # content preview; the full post body lives on the /p/<id> detail page,
    # whose bundled parser targets retired markup and raises "list index out of
    # range". Cache the search notes, then enrich each with the detail-page body
    # read from the current OP container (the single ``pb-content-wrap``),
    # falling back to the search-level note if the detail fetch fails.
    from parsel import Selector

    search_cache: dict[str, object] = {}
    # Detail HTML kept per note so the comment pass can reuse the page the body
    # pass already loaded instead of fetching each post a second time.
    detail_cache: dict[str, str] = {}
    original_get_notes = client_module.BaiduTieBaClient.get_notes_by_keyword

    async def get_notes_by_keyword(self, *args, **kwargs):
        notes = await original_get_notes(self, *args, **kwargs)
        for note in notes or []:
            search_cache[note.note_id] = note
        return notes

    client_module.BaiduTieBaClient.get_notes_by_keyword = get_notes_by_keyword

    async def get_note_by_id(self, note_id):
        note = search_cache.get(note_id)
        note_url = f"{self._host}/p/{note_id}"
        try:
            await self.playwright_page.goto(note_url, wait_until="domcontentloaded")
            try:
                await self.playwright_page.wait_for_selector(
                    ".pb-content-wrap, .pb-text-wrapper", timeout=15000
                )
            except Exception:
                pass
            page_html = await self.playwright_page.content()
            detail_cache[note_id] = page_html
            detail = Selector(text=page_html)
            body = _collapse_cjk_spaces(
                " ".join(
                    part.strip()
                    for part in detail.xpath(
                        "//*[contains(@class,'pb-content-wrap')]//text()"
                    ).getall()
                    if part.strip()
                )
            )
            raw_title = detail.xpath("//title/text()").get(default="").strip()
            title = re.sub(r"-百度贴吧\s*$", "", raw_title).strip()
            if note is None:
                note = tieba_note_cls(
                    note_id=note_id,
                    title=title,
                    desc=body,
                    note_url=note_url,
                    user_link="",
                    user_nickname="",
                    tieba_name="",
                    tieba_link="",
                    publish_time="",
                )
            else:
                if title:
                    note.title = title
                if body:
                    note.desc = body
            return note
        except Exception as exc:  # noqa: BLE001 - fall back to search-level data
            print(f"[tieba] detail fetch failed for {note_id}: {exc}", file=sys.stderr)
            if note is not None:
                return note
            raise

    client_module.BaiduTieBaClient.get_note_by_id = get_note_by_id

    # Comments render into `div.pb-comment-item` on the same post page, while
    # the bundled parser still targets the classic `lzl_single_post` markup and
    # its pager is gated on `total_replay_page`, which nothing populates — so
    # the crawler reported 0 comments without ever loading a page. Parse the
    # current markup off the cached detail HTML; sponsored blocks sit outside
    # `pb-comment-item`, so they are excluded for free.
    tieba_comment_cls = importlib.import_module("model.m_baidu_tieba").TiebaComment

    async def get_note_all_comments(
        self, note_detail, crawl_interval: float = 1.0, callback=None, max_count: int = 10
    ):
        note_url = f"{self._host}/p/{note_detail.note_id}"
        comments: list = []
        try:
            page_html = detail_cache.get(note_detail.note_id)
            if page_html is None:
                await self.playwright_page.goto(note_url, wait_until="domcontentloaded")
                try:
                    await self.playwright_page.wait_for_selector(
                        ".pb-comment-item", timeout=15000
                    )
                except Exception:
                    pass
                page_html = await self.playwright_page.content()

            def first(node, class_name: str, collapse: bool = True) -> str:
                found = node.xpath(f"(.//*[contains(@class,'{class_name}')])[1]")
                if not found:
                    return ""
                text = " ".join(
                    part.strip()
                    for part in found.xpath(".//text()").getall()
                    if part.strip()
                )
                # Collapsing is for highlight noise inside prose; the meta line
                # separates time from IP location with a space that must stay.
                return _collapse_cjk_spaces(text) if collapse else text

            for item in Selector(text=page_html).xpath(
                "//div[contains(@class,'pb-comment-item')]"
            ):
                if len(comments) >= max_count:
                    break
                content = first(item, "pb-rich-text")
                if not content:
                    continue
                # "第2楼 21小时前 浙江" -> floor, publish time, ip location
                publish_time, ip_location = "", ""
                desc = re.sub(
                    r"^第\d+楼\s*", "", first(item, "comment-desc-left", collapse=False)
                )
                parts = desc.split()
                if len(parts) >= 2:
                    publish_time, ip_location = " ".join(parts[:-1]), parts[-1]
                elif parts:
                    publish_time = parts[0]
                comments.append(
                    tieba_comment_cls(
                        comment_id=item.attrib.get("data-id", "")
                        or f"{note_detail.note_id}_{len(comments)}",
                        content=content,
                        user_nickname=first(item, "head-name"),
                        publish_time=publish_time,
                        ip_location=ip_location,
                        note_id=note_detail.note_id,
                        note_url=note_url,
                        tieba_id="",
                        tieba_name=note_detail.tieba_name,
                        tieba_link="",
                    )
                )
            if callback and comments:
                await callback(note_detail.note_id, comments)
        except Exception as exc:  # noqa: BLE001 - comments are best-effort
            print(
                f"[tieba] comment fetch failed for {note_detail.note_id}: {exc}",
                file=sys.stderr,
            )
        return comments

    client_module.BaiduTieBaClient.get_note_all_comments = get_note_all_comments


def main() -> int:
    crawler_root = Path.cwd()
    if str(crawler_root) not in sys.path:
        sys.path.insert(0, str(crawler_root))

    crawler_main = importlib.import_module("main")
    login_module = importlib.import_module("media_platform.xhs.login")
    login_module.XiaoHongShuLogin.quick_check_login_state = (
        _do_not_skip_failed_api_login_check
    )

    platform = _platform_arg()
    _patch_navigation_safety(platform)
    _patch_tieba_search(platform)

    return int(crawler_main.run_cli())


if __name__ == "__main__":
    raise SystemExit(main())
