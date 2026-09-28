from __future__ import annotations

import json
from pathlib import Path

from openai import OpenAI

from .config import settings
from .media import image_data_url


class AnalyzeError(RuntimeError):
    pass


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise AnalyzeError("尚未設定 OPENAI_API_KEY")
    return OpenAI(api_key=settings.openai_api_key)


def transcribe(audio_path: Path) -> str:
    client = _client()
    with audio_path.open("rb") as f:
        result = client.audio.transcriptions.create(
            model=settings.transcribe_model,
            file=f,
        )
    return getattr(result, "text", "") or ""


def analyze_frames_and_transcript(frames: list[Path], transcript: str, title: str | None) -> dict:
    client = _client()
    content: list[dict] = [{
        "type": "input_text",
        "text": (
            "你正在分析中國大陸抖音短影片。請只描述影片實際可觀察內容，不猜測人物身分。"
            "整合畫面與語音，輸出純 JSON，欄位固定為：summary, people_and_scene, actions, "
            "spoken_content, on_screen_text, event_flow, one_line_summary。event_flow 必須是字串陣列。"
            "如果字幕看不清楚就明確寫『無法確認』。\n\n"
            f"影片標題：{title or '未知'}\n"
            f"語音轉寫：{transcript or '（沒有可辨識語音）'}"
        ),
    }]
    for frame in frames:
        content.append({"type": "input_image", "image_url": image_data_url(frame), "detail": "low"})

    response = client.responses.create(
        model=settings.vision_model,
        input=[{"role": "user", "content": content}],
    )
    text = response.output_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].lstrip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnalyzeError(f"AI 回傳的分析不是有效 JSON：{text[:500]}") from exc

    required = {
        "summary", "people_and_scene", "actions", "spoken_content",
        "on_screen_text", "event_flow", "one_line_summary",
    }
    missing = required.difference(data)
    if missing:
        raise AnalyzeError(f"AI 分析缺少欄位：{', '.join(sorted(missing))}")
    return data
