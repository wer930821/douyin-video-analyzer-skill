from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .config import settings


ALLOWED_HOSTS = {
    "v.douyin.com",
    "www.douyin.com",
    "douyin.com",
    "iesdouyin.com",
    "www.iesdouyin.com",
}


class DouyinError(RuntimeError):
    pass


@dataclass
class ResolvedVideo:
    source_url: str
    video_url: str
    title: str | None = None
    author: str | None = None


def validate_douyin_url(url: str) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise DouyinError("只支援 http/https 抖音網址")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise DouyinError("目前只支援中國大陸抖音網址（douyin.com / v.douyin.com）")
    return value


async def resolve_video(url: str) -> ResolvedVideo:
    url = validate_douyin_url(url)
    headers = {}
    if settings.douyin_api_key:
        headers["X-API-Key"] = settings.douyin_api_key

    endpoint = f"{settings.douyin_api_base.rstrip('/')}/api/v1/parse"
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
        response = await client.post(endpoint, json={"url": url}, headers=headers)

    if response.status_code == 202:
        body = response.json()
        task_id = ((body.get("meta") or {}).get("task_id"))
        if not task_id:
            raise DouyinError("抖音解析服務正在處理，但沒有回傳 task_id")
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(
                f"{settings.douyin_api_base.rstrip('/')}/api/v1/tasks/{task_id}",
                headers=headers,
            )

    if response.is_error:
        raise DouyinError(f"抖音解析失敗：HTTP {response.status_code}")

    body = response.json()
    if not body.get("success", True):
        err = body.get("error") or {}
        raise DouyinError(err.get("message") or "抖音解析失敗")

    data = body.get("data") or body
    media = data.get("media") or {}
    video = media.get("video") or {}
    video_url = video.get("url")
    if not video_url:
        video_obj = data.get("video") or {}
        for key in ("play_addr_h264", "play_addr", "download_addr"):
            urls = ((video_obj.get(key) or {}).get("url_list") or [])
            if urls:
                video_url = urls[0]
                break
    if not video_url:
        raise DouyinError("解析成功，但找不到影片來源；可能是圖集或抖音風控阻擋")

    author_obj = data.get("author") or {}
    author = author_obj.get("nickname") if isinstance(author_obj, dict) else None
    return ResolvedVideo(
        source_url=url,
        video_url=video_url,
        title=data.get("title") or data.get("desc"),
        author=author,
    )
