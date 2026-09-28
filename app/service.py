from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from .analyzer import AnalyzeError, analyze_frames_and_transcript, transcribe
from .douyin import DouyinError, resolve_video
from .media import MediaError, download_video, extract_audio, extract_frames
from .models import AnalyzeResult


async def analyze_douyin_url(url: str) -> AnalyzeResult:
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
        frames = sorted(frames_dir.glob("frame_*.jpg"))
        transcript = await asyncio.to_thread(transcribe, audio)
        analysis = await asyncio.to_thread(
            analyze_frames_and_transcript,
            frames,
            transcript,
            resolved.title,
        )

    return AnalyzeResult(
        title=resolved.title,
        author=resolved.author,
        source_url=resolved.source_url,
        transcript=transcript,
        frame_count=len(frames),
        **analysis,
    )


EXPECTED_ERRORS = (DouyinError, MediaError, AnalyzeError)
