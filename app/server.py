from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .service import EXPECTED_ERRORS, analyze_douyin_url


mcp = MCPServer(
    "douyin-video-analyzer",
    title="陸抖影片內容分析",
    description="分析中國大陸抖音影片內容，只接受 douyin.com / v.douyin.com 網址。",
    instructions=(
        "Use analyze_douyin_video only for mainland-China Douyin URLs "
        "(douyin.com or v.douyin.com). Return a concise Traditional Chinese "
        "summary of the actual video content."
    ),
)


@mcp.tool()
async def analyze_douyin_video(url: str) -> dict:
    """分析中國大陸抖音影片的實際內容。"""
    try:
        result = await analyze_douyin_url(url)
        return {"ok": True, **result.model_dump()}
    except EXPECTED_ERRORS as exc:
        return {"ok": False, "error": str(exc), "url": url}
    except Exception as exc:
        return {"ok": False, "error": f"分析失敗：{exc}", "url": url}


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "douyin-video-analyzer", "version": "0.2.1"})


app = mcp.streamable_http_app(
    host="0.0.0.0",
    stateless_http=True,
    json_response=True,
    custom_starlette_routes=[Route("/health", health, methods=["GET"])],
)
