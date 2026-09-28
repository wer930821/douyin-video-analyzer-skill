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


def _pick_video_url(data: dict) -> str | None:
    # Evil0ctal v4 shape
    video_obj = data.get("video") or {}
    for key in ("play_addr", "play_addr_h264", "download_addr"):
        urls = ((video_obj.get(key) or {}).get("url_list") or [])
        if urls:
            return urls[0].replace("playwm", "play")

    # Compatibility with normalized or older responses
    media = data.get("media") or {}
    video = media.get("video") or {}
    if isinstance(video.get("url"), str):
        return video["url"]

    for key in ("nwm_video_url_HQ", "nwm_video_url"):
        if isinstance(data.get(key), str) and data[key]:
            return data[key]
    return None


async def resolve_video(url: str) -> ResolvedVideo:
    url = validate_douyin_url(url)
    headers = {}
    if settings.douyin_api_key:
        headers["token"] = settings.douyin_api_key

    base = settings.douyin_api_base.rstrip("/")
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
    ) as client:
        # v4 parser used by the Railway sidecar.
        response = await client.get(
            f"{base}/api/hybrid/video_data",
            params={"url": url, "minimal": "false"},
            headers=headers,
        )

    if response.is_error:
        raise DouyinError(f"抖音解析失敗：HTTP {response.status_code}")

    body = response.json()
    if body.get("code") not in (None, 200):
        raise DouyinError(body.get("message") or body.get("msg") or "抖音解析失敗")

    data = body.get("data") or body
    video_url = _pick_video_url(data)
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
