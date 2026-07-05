from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MediaCrawlerPlatform = Literal["xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"]
MediaCrawlerLoginType = Literal["qrcode", "phone", "cookie"]
MediaCrawlerType = Literal["search", "detail", "creator"]
MediaCrawlerSaveOption = Literal["jsonl", "json", "csv"]


class CrawlerStartRequest(BaseModel):
    platform: MediaCrawlerPlatform
    login_type: MediaCrawlerLoginType = "qrcode"
    crawler_type: MediaCrawlerType = "search"
    keywords: str = ""
    specified_ids: str = ""
    creator_ids: str = ""
    start_page: int = Field(default=1, ge=1)
    enable_comments: bool = True
    enable_sub_comments: bool = False
    save_option: MediaCrawlerSaveOption = "jsonl"
    cookies: str = ""
    headless: bool = False
    max_comments_count_singlenotes: int = Field(default=10, ge=0)
    max_concurrency_num: int = Field(default=1, ge=1)


class CrawlerStatusResponse(BaseModel):
    status: Literal["idle", "running", "stopping", "error"]
    platform: str | None = None
    crawler_type: str | None = None
    started_at: str | None = None
    error_message: str | None = None
    task_id: str | None = None
    run_id: str | None = None


class CrawlerLogEntry(BaseModel):
    id: int
    timestamp: str
    level: Literal["info", "warning", "error", "success", "debug"]
    message: str
