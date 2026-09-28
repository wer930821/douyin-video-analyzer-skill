# 陸抖影片內容分析 Remote MCP

只做一件事：貼中國大陸抖音網址，回傳影片內容分析。

## 支援

- `https://v.douyin.com/.../`
- `https://www.douyin.com/video/...`

不支援海外 TikTok。

## MCP

部署後的 MCP endpoint：`/mcp`

工具：`analyze_douyin_video`

參數：

```json
{"url":"https://v.douyin.com/xxxxx/"}
```

回傳人物/場景、動作、語音內容、畫面字幕、事件流程與一句話總結。

## Railway

健康檢查：`GET /health`

Remote MCP：`POST /mcp`

注意：分析服務仍需要可用的陸抖解析服務；陸抖風控可能要求有效 Cookie / identity pool。
