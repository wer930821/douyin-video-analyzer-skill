from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from .gemini import GeminiError, analyze_bundle
from .service import EXPECTED_ERRORS, prepare_douyin_media


PAGE = "<!doctype html>\n<html lang=\"zh-Hant\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n<title>陸抖影片內容分析</title>\n<style>\n:root{color-scheme:dark;font-family:system-ui,-apple-system,BlinkMacSystemFont,\"Noto Sans TC\",sans-serif}\n*{box-sizing:border-box} body{margin:0;background:#0c0d10;color:#f5f6f8;min-height:100vh}\n.wrap{max-width:680px;margin:auto;padding:24px 16px 64px}\nh1{font-size:28px;margin:14px 0 8px}.sub{color:#a7acb8;line-height:1.6;margin:0 0 24px}\n.card{background:#17191f;border:1px solid #292d36;border-radius:18px;padding:16px;margin:14px 0}\nlabel{display:block;font-size:13px;color:#b8bdc8;margin-bottom:8px}\ninput{width:100%;border:1px solid #343946;border-radius:14px;background:#0f1116;color:white;padding:15px;font-size:16px;outline:none}\ninput:focus{border-color:#777f91} button{width:100%;margin-top:12px;border:0;border-radius:14px;padding:15px;font-size:16px;font-weight:700;background:white;color:#111;cursor:pointer}\nbutton:disabled{opacity:.45}.small{font-size:12px;color:#838996;line-height:1.5;margin-top:8px}\n#status{padding:13px 0;color:#c7ccd5;min-height:44px}.result{display:none}\n.row h3{font-size:14px;color:#9ea5b2;margin:0 0 6px}.row p,.row ol{margin:0;line-height:1.7;white-space:pre-wrap}\n.row{padding:14px 0;border-bottom:1px solid #292d36}.row:last-child{border-bottom:0}\n.settings{margin-top:10px}.settings summary{color:#aeb4c0;cursor:pointer}.bad{color:#ff8d8d}.good{color:#96e6b3}\n.loader{display:inline-block;width:14px;height:14px;border:2px solid #666;border-top-color:white;border-radius:50%;animation:s .8s linear infinite;vertical-align:-2px;margin-right:8px}\n@keyframes s{to{transform:rotate(360deg)}}\n</style>\n</head>\n<body>\n<div class=\"wrap\">\n  <h1>陸抖影片內容分析</h1>\n  <p class=\"sub\">貼中國大陸抖音網址，直接分析影片在演什麼、說什麼、字幕與事件流程。</p>\n  <div class=\"card\">\n    <label>抖音網址</label>\n    <input id=\"url\" placeholder=\"https://v.douyin.com/...\" autocomplete=\"off\">\n    <button id=\"go\">開始分析</button>\n    <div id=\"status\"></div>\n    <details class=\"settings\">\n      <summary>第一次使用：設定 Gemini API Key</summary>\n      <div style=\"height:12px\"></div>\n      <label>Gemini API Key</label>\n      <input id=\"key\" type=\"password\" placeholder=\"AIza...\">\n      <button id=\"save\" type=\"button\">儲存在這支手機</button>\n      <div class=\"small\">API Key 只儲存在這個瀏覽器。分析時透過 HTTPS 送到你的 Railway 後端，再由後端呼叫 Google Gemini API；不寫入資料庫。</div>\n    </details>\n  </div>\n  <div class=\"card result\" id=\"result\">\n    <div class=\"row\"><h3>一句話總結</h3><p id=\"one\"></p></div>\n    <div class=\"row\"><h3>影片主要內容</h3><p id=\"summary\"></p></div>\n    <div class=\"row\"><h3>人物與場景</h3><p id=\"scene\"></p></div>\n    <div class=\"row\"><h3>人物動作</h3><p id=\"actions\"></p></div>\n    <div class=\"row\"><h3>說話內容</h3><p id=\"spoken\"></p></div>\n    <div class=\"row\"><h3>畫面字幕</h3><p id=\"text\"></p></div>\n    <div class=\"row\"><h3>事件流程</h3><ol id=\"flow\"></ol></div>\n  </div>\n</div>\n<script>\nconst el=id=>document.getElementById(id);\nconst keyName=\"douyinGeminiKey\";\nel(\"key\").value=localStorage.getItem(keyName)||\"\";\nel(\"save\").onclick=()=>{\n  const v=el(\"key\").value.trim();\n  if(!v){localStorage.removeItem(keyName);el(\"status\").innerHTML='<span class=\"bad\">已清除 API Key</span>';return}\n  localStorage.setItem(keyName,v);\n  el(\"status\").innerHTML='<span class=\"good\">已儲存在這支手機</span>';\n};\nfunction show(data){\n  el(\"one\").textContent=data.one_line_summary||\"\";\n  el(\"summary\").textContent=data.summary||\"\";\n  el(\"scene\").textContent=data.people_and_scene||\"\";\n  el(\"actions\").textContent=data.actions||\"\";\n  el(\"spoken\").textContent=data.spoken_content||\"\";\n  el(\"text\").textContent=data.on_screen_text||\"\";\n  el(\"flow\").innerHTML=\"\";\n  (data.event_flow||[]).forEach(x=>{const li=document.createElement(\"li\");li.textContent=x;el(\"flow\").appendChild(li)});\n  el(\"result\").style.display=\"block\";\n}\nel(\"go\").onclick=async()=>{\n  const url=el(\"url\").value.trim();\n  const apiKey=localStorage.getItem(keyName)||el(\"key\").value.trim();\n  if(!url){el(\"status\").innerHTML='<span class=\"bad\">先貼抖音網址</span>';return}\n  if(!apiKey){el(\"status\").innerHTML='<span class=\"bad\">第一次使用要先設定 Gemini API Key</span>';return}\n  el(\"go\").disabled=true; el(\"result\").style.display=\"none\";\n  el(\"status\").innerHTML='<span class=\"loader\"></span>正在取得陸抖影片並分析內容…';\n  try{\n    const r=await fetch(\"/api/web-analyze\",{method:\"POST\",headers:{\"content-type\":\"application/json\"},body:JSON.stringify({url:url,api_key:apiKey})});\n    const data=await r.json();\n    if(!r.ok||!data.ok) throw new Error(data.error||\"無法建立分析任務\");\n    const jobId=data.job_id;\n    let done=false;\n    for(let i=0;i<90;i++){\n      await new Promise(res=>setTimeout(res,2000));\n      const s=await fetch(\"/api/web-analyze/\"+encodeURIComponent(jobId),{cache:\"no-store\"});\n      const st=await s.json();\n      if(!s.ok) throw new Error(st.error||\"查詢分析結果失敗\");\n      if(st.status===\"done\"){\n        show(st.result);\n        el(\"status\").innerHTML='<span class=\"good\">分析完成</span>';\n        done=true;\n        break;\n      }\n      if(st.status===\"error\") throw new Error(st.error||\"分析失敗\");\n      el(\"status\").innerHTML='<span class=\"loader\"></span>正在分析影片內容…';\n    }\n    if(!done) throw new Error(\"分析時間過長，請再試一次\");\n  }catch(e){el(\"status\").innerHTML='<span class=\"bad\">'+String(e.message||e)+'</span>'}\n  finally{el(\"go\").disabled=false}\n};\n</script>\n</body></html>"

DB_PATH = Path("/data/jobs.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            result_json TEXT,
            error TEXT
        )
        """
    )
    return conn


def _put_job(job_id: str, status: str, *, result: dict | None = None, error: str | None = None) -> None:
    now = time.time()
    payload = json.dumps(result, ensure_ascii=False) if result is not None else None
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, status, created_at, updated_at, result_json, error)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              status=excluded.status,
              updated_at=excluded.updated_at,
              result_json=excluded.result_json,
              error=excluded.error
            """,
            (job_id, status, now, now, payload, error),
        )


def _get_job(job_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, status, created_at, updated_at, result_json, error FROM jobs WHERE id=?",
            (job_id,),
        ).fetchone()

    if not row:
        return None

    result = json.loads(row[4]) if row[4] else None
    payload = {
        "job_id": row[0],
        "status": row[1],
        "created_at": row[2],
        "updated_at": row[3],
    }
    if result is not None:
        payload["result"] = result
    if row[5]:
        payload["error"] = row[5]
    return payload


def _cleanup_jobs() -> None:
    cutoff = time.time() - 86400
    with _connect() as conn:
        conn.execute("DELETE FROM jobs WHERE updated_at < ?", (cutoff,))


async def home(_: Request) -> HTMLResponse:
    return HTMLResponse(PAGE)


async def _run_job(job_id: str, url: str, api_key: str) -> None:
    try:
        _put_job(job_id, "working")
        bundle = await prepare_douyin_media(url)
        result = await analyze_bundle(bundle, api_key)
        _put_job(job_id, "done", result=result)
    except EXPECTED_ERRORS as exc:
        _put_job(job_id, "error", error=str(exc))
    except GeminiError as exc:
        _put_job(job_id, "error", error=str(exc))
    except Exception as exc:
        _put_job(job_id, "error", error=f"分析失敗：{exc}")


async def web_analyze(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        url = str(body.get("url") or "").strip()
        api_key = str(body.get("api_key") or "").strip()

        if not url:
            return JSONResponse({"ok": False, "error": "請先貼抖音網址"}, status_code=400)
        if not api_key:
            return JSONResponse({"ok": False, "error": "請先設定 Gemini API Key"}, status_code=400)

        _cleanup_jobs()
        job_id = uuid.uuid4().hex
        _put_job(job_id, "queued")
        asyncio.create_task(_run_job(job_id, url, api_key))
        return JSONResponse({"ok": True, "job_id": job_id}, status_code=202)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"建立分析任務失敗：{exc}"}, status_code=500)


async def web_analyze_status(request: Request) -> JSONResponse:
    _cleanup_jobs()
    job_id = request.path_params["job_id"]
    job = _get_job(job_id)
    if not job:
        return JSONResponse({"error": "找不到分析任務，可能已過期"}, status_code=404)
    return JSONResponse(job)
