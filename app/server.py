from __future__ import annotations

import base64
import json
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer
from mcp.types import AudioContent, ImageContent, TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .service import EXPECTED_ERRORS, prepare_douyin_media


mcp = MCPServer(
    "douyin-video-analyzer",
    title="陸抖影片內容分析",
    description="讀取中國大陸抖音影片，將實際畫面與音訊交給 ChatGPT 分析。",
    instructions=(
        "Use analyze_douyin_video only for mainland-China Douyin URLs. "
        "After the tool returns, inspect every returned image and the audio, "
        "then answer the user in Traditional Chinese with a factual summary of "
        "what happens in the video. Do not infer identities that are not visible."
    ),
)


@mcp.tool(structured_output=False)
async def analyze_douyin_video(url: str):
    """讀取中國大陸抖音影片，回傳影片畫面與音訊供模型直接分析。"""
    try:
        bundle = await prepare_douyin_media(url)
    except EXPECTED_ERRORS as exc:
        return [TextContent(type="text", text=f"無法取得抖音影片：{exc}")]
    except Exception as exc:
        return [TextContent(type="text", text=f"處理影片失敗：{exc}")]

    metadata = {
        "source_url": bundle.source_url,
        "title": bundle.title,
        "author": bundle.author,
        "frame_count": len(bundle.frames),
        "instructions": (
            "請直接分析後續所有畫面與音訊，整理：主要內容、人物/場景、"
            "發生的動作、說話重點、畫面文字、事件順序、一句話總結。"
        ),
    }

    content = [
        TextContent(
            type="text",
            text="陸抖影片素材已取得。\n" + json.dumps(metadata, ensure_ascii=False),
        )
    ]
    content.extend(
        ImageContent(
            type="image",
            data=base64.b64encode(frame).decode("ascii"),
            mime_type="image/jpeg",
        )
        for frame in bundle.frames
    )
    content.append(
        AudioContent(
            type="audio",
            data=base64.b64encode(bundle.audio).decode("ascii"),
            mime_type="audio/mpeg",
        )
    )
    return content


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "douyin-video-analyzer", "version": "0.3.1"})


mcp_app = mcp.streamable_http_app(
    host="0.0.0.0",
    stateless_http=True,
    json_response=True,
)


@asynccontextmanager
async def lifespan(_: Starlette):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Mount("/", app=mcp_app),
    ],
    lifespan=lifespan,
)
