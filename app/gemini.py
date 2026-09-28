from __future__ import annotations

import asyncio
import base64
import json

import httpx

from .config import settings
from .service import MediaBundle


class GeminiError(RuntimeError):
    pass


SYSTEM_PROMPT = """你正在分析中國大陸抖音短影片。目標不是完整解說影片，而是只找出對使用者實際有用、可直接採用的資訊。
不要花篇幅描述人物穿著、無關場景、完整逐字字幕或無關細節，除非它直接影響理解或使用。

優先找：
1. 影片核心在教什麼、介紹什麼、解決什麼問題。
2. 可以直接照做的方法、步驟、操作流程。
3. 提到的工具、網站、App、模型、程式、服務或功能。
4. 可延伸到網站、App、AI 工具、聊天功能、自動化、影片工具等實作點子。
5. 限制、風險、前置條件、費用、相容性或容易踩雷的地方。
6. 最值得採取的下一步。

請使用繁體中文，輸出純 JSON，欄位固定為：
core_value: string
actionable_steps: string[]
useful_tools: string[]
applicable_ideas: string[]
cautions: string[]
next_step: string

如果影片其實沒有明顯可用資訊，也要直接說明，不要硬湊內容。
"""


def _model_chain() -> list[str]:
    models = [settings.gemini_model.strip()]
    models.extend(
        m.strip()
        for m in settings.gemini_fallback_models.split(",")
        if m.strip()
    )
    # Preserve order while removing duplicates.
    seen: set[str] = set()
    return [m for m in models if m and not (m in seen or seen.add(m))]


async def _call_model(client: httpx.AsyncClient, model: str, key: str, payload: dict) -> dict:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )

    attempts = max(1, settings.gemini_max_retries)
    last_status = 0
    last_detail = ""

    for attempt in range(attempts):
        response = await client.post(
            url,
            headers={
                "x-goog-api-key": key,
                "content-type": "application/json",
            },
            json=payload,
        )

        if not response.is_error:
            return response.json()

        last_status = response.status_code
        last_detail = response.text[:800]

        # Transient capacity/rate failures: exponential backoff.
        if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
            await asyncio.sleep(2 ** attempt)
            continue

        break

    raise GeminiError(
        f"{model} 分析失敗：HTTP {last_status} - {last_detail}"
    )


async def analyze_bundle(bundle: MediaBundle, api_key: str) -> dict:
    key = (api_key or settings.gemini_api_key).strip()
    if not key:
        raise GeminiError("尚未設定 Gemini API Key")

    parts: list[dict] = [
        {
            "text": (
                SYSTEM_PROMPT
                + "\n影片標題："
                + (bundle.title or "未知")
                + "\n作者顯示名稱："
                + (bundle.author or "未知")
                + "\n請綜合後續所有畫面與音訊分析整支影片。"
            )
        }
    ]

    for frame in bundle.frames:
        parts.append(
            {
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": base64.b64encode(frame).decode("ascii"),
                }
            }
        )

    parts.append(
        {
            "inlineData": {
                "mimeType": "audio/mpeg",
                "data": base64.b64encode(bundle.audio).decode("ascii"),
            }
        }
    )

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }

    errors: list[str] = []
    async with httpx.AsyncClient(timeout=settings.gemini_request_timeout_seconds) as client:
        for model in _model_chain():
            try:
                body = await _call_model(client, model, key, payload)
                try:
                    text = body["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise GeminiError(f"{model} 沒有回傳可解析的分析內容") from exc

                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = {
                        "core_value": text,
                        "actionable_steps": [],
                        "useful_tools": [],
                        "applicable_ideas": [],
                        "cautions": [],
                        "next_step": text[:120],
                    }

                data["_model_used"] = model
                return data
            except GeminiError as exc:
                errors.append(str(exc))
                continue

    raise GeminiError("所有 Gemini 模型都暫時無法使用：" + " | ".join(errors))
