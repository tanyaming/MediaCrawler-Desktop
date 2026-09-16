# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/main.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

"""
MediaCrawler WebUI API Server
Start command: uvicorn api.main:app --port 8080 --reload
Or: python -m api.main
"""
import asyncio
import os
import sys
import subprocess
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .routers import crawler_router, data_router, websocket_router


class SafeJSONResponse(JSONResponse):
    """JSON 响应类：对 NaN / Infinity 做防御性处理。

    背景：FastAPI 默认用 json.dumps(allow_nan=False) 序列化响应，只要响应体里
    带有 NaN / Infinity（例如 pandas 读 Excel 时空数值列产生的 float('nan')），
    就会报 “ValueError: Out of range float values are not JSON compliant” 并返回 500。

    这里重写 render：先尝试标准序列化，失败则递归把非法的 float 转成 None 后再序列化，
    从全局层面避免此类崩溃。
    """

    def render(self, content) -> bytes:
        import math

        def _sanitize(value):
            if isinstance(value, float):
                if math.isnan(value) or math.isinf(value):
                    return None
                return value
            if isinstance(value, dict):
                return {k: _sanitize(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [_sanitize(v) for v in value]
            return value

        try:
            return super().render(content)
        except ValueError:
            safe_content = _sanitize(content)
            return super().render(safe_content)

# Project root directory (used for running subprocesses like uv run main.py)
PROJECT_ROOT = Path(__file__).parent.parent

# ---- 桌面版：统一路径重定向（打包 -> %APPDATA%）----
try:
    from desktop import paths as desktop_paths  # type: ignore
    desktop_paths.ensure_runtime_dirs()
    # 桌面版（无论是否打包）都走内置环境检测，不依赖 uv
    IS_FROZEN = True
except Exception:  # pragma: no cover
    desktop_paths = None
    IS_FROZEN = False

app = FastAPI(
    title="MediaCrawler WebUI API",
    description="API for controlling MediaCrawler from WebUI",
    version="1.0.0",
    default_response_class=SafeJSONResponse,
)

# Get webui static files directory
if desktop_paths is not None:
    WEBUI_DIR = str(desktop_paths.webui_dir())
else:
    WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui")

# CORS configuration - allow frontend dev server access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Backup port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(crawler_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.include_router(websocket_router, prefix="/api")


@app.get("/")
async def serve_frontend():
    """Return frontend page"""
    index_path = os.path.join(WEBUI_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": "MediaCrawler WebUI API",
        "version": "1.0.0",
        "docs": "/docs",
        "note": "WebUI not found, please build it first: cd webui && npm run build"
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/env/check")
async def check_environment():
    """Check if MediaCrawler environment is configured correctly"""
    if IS_FROZEN:
        return _check_environment_frozen()
    try:
        # Run uv run main.py --help command to check environment
        # Use PROJECT_ROOT so it works regardless of where uvicorn was started
        if sys.platform == "win32":
            loop = asyncio.get_running_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["uv", "run", "main.py", "--help"],
                    capture_output=True,
                    timeout=30.0,
                    cwd=str(PROJECT_ROOT)
                )
            )
            stdout, stderr = process.stdout, process.stderr  # bytes
        else:
            process = await asyncio.create_subprocess_exec(
                "uv", "run", "main.py", "--help",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(PROJECT_ROOT)  # Project root directory
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0  # 30 seconds timeout
            )
        if process.returncode == 0:
            return {
                "success": True,
                "message": "MediaCrawler environment configured correctly",
                "output": stdout.decode("utf-8", errors="ignore")[:500]  # Truncate to first 500 characters
            }
        else:
            error_msg = stderr.decode("utf-8", errors="ignore") or stdout.decode("utf-8", errors="ignore")
            return {
                "success": False,
                "message": "Environment check failed",
                "error": error_msg[:500]
            }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "message": "Environment check timeout",
            "error": "Command execution exceeded 30 seconds"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "message": "uv command not found",
            "error": "Please ensure uv is installed and configured in system PATH"
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Environment check error",
            "error": f"{type(e).__name__}: {str(e) or 'Unknown'}"
        }


def _check_environment_frozen():
    """打包态环境检测：不依赖 uv/python，检查浏览器与运行目录。"""
    import shutil
    checks = []

    # 数据目录可写
    try:
        test_file = Path(WEBUI_DIR).parent / ".write_test"
        data_dir = desktop_paths.user_data_root() if desktop_paths else Path.cwd()
        probe = data_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append({"name": "数据目录", "ok": True, "detail": str(data_dir)})
    except Exception as e:
        checks.append({"name": "数据目录", "ok": False, "detail": str(e)})

    # Chrome / Edge
    candidates = []
    if os.name == "nt":
        for env_key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env_key)
            if not base:
                continue
            candidates += [
                Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            ]
    found_browser = next((str(c) for c in candidates if c.exists()), None)
    if not found_browser:
        found_browser = shutil.which("chrome") or shutil.which("msedge")
    checks.append({
        "name": "浏览器 (Chrome/Edge)",
        "ok": bool(found_browser),
        "detail": found_browser or "未检测到 Chrome/Edge，请先安装",
    })

    ok = all(c["ok"] for c in checks)
    return {
        "success": ok,
        "message": "环境检测通过" if ok else "存在问题，请查看详情",
        "checks": checks,
        "output": "; ".join(f"{c['name']}: {'OK' if c['ok'] else 'FAIL'}" for c in checks),
    }


@app.get("/api/config/settings")
async def get_settings():
    """读取外置 settings.json（GUI 表单）"""
    try:
        from desktop import settings as _s
        return _s.load_settings()
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/config/settings")
async def update_settings(payload: dict):
    """写入外置 settings.json"""
    try:
        from desktop import settings as _s
        return _s.save_settings(payload or {})
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/config/platforms")
async def get_platforms():
    """Get list of supported platforms"""
    return {
        "platforms": [
            {"value": "xhs", "label": "小红书", "icon": "book-open"},
            {"value": "dy", "label": "抖音", "icon": "music"},
            {"value": "ks", "label": "快手", "icon": "video"},
            {"value": "bili", "label": "哔哩哔哩", "icon": "tv"},
            {"value": "wb", "label": "微博", "icon": "message-circle"},
            {"value": "tieba", "label": "百度贴吧", "icon": "messages-square"},
            {"value": "zhihu", "label": "知乎", "icon": "help-circle"},
        ]
    }


@app.get("/api/config/options")
async def get_config_options():
    """Get all configuration options"""
    return {
        "login_types": [
            {"value": "qrcode", "label": "扫码登录"},
            {"value": "cookie", "label": "Cookie 登录"},
        ],
        "crawler_types": [
            {"value": "search", "label": "搜索模式"},
            {"value": "detail", "label": "指定内容"},
            {"value": "creator", "label": "创作者主页"},
        ],
        "save_options": [
            {"value": "excel", "label": "Excel"},
        ],
    }


# Mount static resources - must be placed after all routes
if os.path.exists(WEBUI_DIR):
    assets_dir = os.path.join(WEBUI_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    # Mount logos directory
    logos_dir = os.path.join(WEBUI_DIR, "logos")
    if os.path.exists(logos_dir):
        app.mount("/logos", StaticFiles(directory=logos_dir), name="logos")
    # Mount other static files (e.g., vite.svg)
    app.mount("/static", StaticFiles(directory=WEBUI_DIR), name="webui-static")


if __name__ == "__main__":
    port = int(os.environ.get("MEDIACRAWLER_PORT", "8080"))
    uvicorn.run(app, host="127.0.0.1", port=port)
