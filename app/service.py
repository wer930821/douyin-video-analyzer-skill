from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .douyin import DouyinError, resolve_video
from .media import MediaError, download_video, extract_audio, extract_frames


@dataclass
class MediaBundle:
    title: str | None
    author: str | None
    source_url: str
    audio: bytes
    frames: list[bytes]


async def prepare_douyin_media(url: str) -> MediaBundle:
    resolved = await resolve_video(url)
    with tempfile.TemporaryDirectory(prefix="douyin_analyze_") as td:
        root = Path(td)
        video = root / "video.mp4"
        audio = root / "audio.mp3"
        frames_dir = root / "frames"

        await download_video(resolved.video_url, video)
        await asyncio.gather(
            extract_audio(video, audio),
            extract_frames(video, frames_dir),
        )
        frame_paths = sorted(frames_dir.glob("frame_*.jpg"))
        return MediaBundle(
            title=resolved.title,
            author=resolved.author,
            source_url=resolved.source_url,
            audio=audio.read_bytes(),
            frames=[p.read_bytes() for p in frame_paths],
        )


EXPECTED_ERRORS = (DouyinError, MediaError)
