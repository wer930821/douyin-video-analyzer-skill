from __future__ import annotations

import asyncio
import base64
import mimetypes
import subprocess
from pathlib import Path

import httpx

from .config import settings


class MediaError(RuntimeError):
    pass


async def download_douyin_video(source_url: str, output: Path) -> None:
    """Ask the Douyin parser to download the video with platform-aware headers.

    Direct douyinvod.com URLs often return 403 when fetched by a separate service.
    The parser's /api/download endpoint reuses Douyin crawler headers/cookies and
    is specifically designed to avoid that direct-CDN failure.
    """
    max_bytes = settings.max_video_mb * 1024 * 1024
    total = 0
    endpoint = f"{settings.douyin_api_base.rstrip('/')}/api/download"

    async with httpx.AsyncClient(
        timeout=max(settings.request_timeout_seconds, 180),
        follow_redirects=True,
    ) as client:
        async with client.stream(
            "GET",
            endpoint,
            params={
                "url": source_url,
                "prefix": "false",
                "with_watermark": "false",
            },
            headers={"Accept": "video/mp4,application/octet-stream;q=0.9,*/*;q=0.8"},
        ) as r:
            if r.status_code >= 400:
                body = await r.aread()
                detail = body.decode("utf-8", errors="ignore")[:800]
                raise MediaError(
                    f"抖音影片下載失敗：HTTP {r.status_code}"
                    + (f" - {detail}" if detail else "")
                )

            content_type = (r.headers.get("content-type") or "").lower()
            if "json" in content_type:
                body = await r.aread()
                detail = body.decode("utf-8", errors="ignore")[:1200]
                raise MediaError(f"抖音下載服務未回傳影片：{detail}")

            with output.open("wb") as f:
                async for chunk in r.aiter_bytes(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise MediaError(f"影片超過 {settings.max_video_mb} MB 上限")
                    f.write(chunk)

    if total == 0:
        raise MediaError("抖音下載服務回傳空影片")


def _run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise MediaError(f"FFmpeg 執行失敗：{proc.stderr[-1200:]}")


async def extract_audio(video: Path, audio: Path) -> None:
    await asyncio.to_thread(
        _run_ffmpeg,
        ["ffmpeg", "-y", "-i", str(video), "-t", str(settings.max_audio_seconds), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(audio)],
    )


async def extract_frames(video: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%03d.jpg"
    interval = max(1, settings.frame_interval_seconds)
    await asyncio.to_thread(
        _run_ffmpeg,
        [
            "ffmpeg", "-y", "-i", str(video),
            "-vf", f"fps=1/{interval},scale='min(960,iw)':-2",
            "-frames:v", str(settings.max_frames),
            "-q:v", "4", str(pattern),
        ],
    )
    return sorted(out_dir.glob("frame_*.jpg"))[: settings.max_frames]


def image_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"
