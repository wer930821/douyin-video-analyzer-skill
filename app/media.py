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


async def download_video(video_url: str, output: Path) -> None:
    max_bytes = settings.max_video_mb * 1024 * 1024
    total = 0
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=True) as client:
        async with client.stream("GET", video_url, headers={"User-Agent": "Mozilla/5.0"}) as r:
            r.raise_for_status()
            with output.open("wb") as f:
                async for chunk in r.aiter_bytes(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise MediaError(f"影片超過 {settings.max_video_mb} MB 上限")
                    f.write(chunk)


def _run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise MediaError(f"FFmpeg 執行失敗：{proc.stderr[-1200:]}")


async def extract_audio(video: Path, audio: Path) -> None:
    await asyncio.to_thread(
        _run_ffmpeg,
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(audio)],
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
