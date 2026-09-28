# 陸抖影片內容分析 Remote MCP

用途：**貼中國大陸抖音網址，讓 ChatGPT 直接分析影片內容。**

支援：
- `https://v.douyin.com/.../`
- `https://www.douyin.com/video/...`

不支援海外 TikTok。

## MCP

Endpoint：`/mcp`

工具：`analyze_douyin_video`

工具會：
1. 解析陸抖網址。
2. 暫存影片。
3. 用 FFmpeg 抽取最多 10 張畫面與壓縮音訊。
4. 將畫面與音訊直接回傳給 MCP client。
5. 由 ChatGPT 本身分析，不需要額外的 OpenAI API Key。

Railway health check：`GET /health`

## Railway

Analyzer 會透過私有網路連到 `douyin-parser` sidecar：

```env
DOUYIN_API_BASE=http://douyin-parser.railway.internal
MAX_VIDEO_MB=120
FRAME_INTERVAL_SECONDS=4
MAX_FRAMES=10
REQUEST_TIMEOUT_SECONDS=90
```

注意：陸抖本身有 Cookie / 風控機制；parser 若被風控，需要更新抖音 Cookie。
