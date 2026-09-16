# -*- coding: utf-8 -*-
"""
统一路径管理 —— 打包(frozen)与开发态自动切换。

打包后程序目录（Program Files）只读，所有可写数据必须重定向到 %APPDATA%/%LOCALAPPDATA%。
开发态保持原有相对目录行为，零破坏。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "MediaCrawler"


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包环境。"""
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    """只读资源根：打包后为 _MEIPASS，开发态为项目根目录。"""
    if is_frozen():
        # PyInstaller onedir: sys._MEIPASS 指向解包目录
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # desktop/paths.py -> 项目根
    return Path(__file__).resolve().parent.parent


def program_root() -> Path:
    """可执行文件所在目录（打包后即安装目录）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _appdata_base() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Roaming"


def _localappdata_base() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Local"


def user_data_root() -> Path:
    """用户可写数据根。打包后 %APPDATA%\\MediaCrawler，开发态项目 ./data。"""
    if is_frozen():
        root = _appdata_base() / APP_NAME
    else:
        root = resource_root() / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def logs_dir() -> Path:
    """日志目录。"""
    if is_frozen():
        root = user_data_root() / "logs"
    else:
        root = resource_root() / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def browser_data_root() -> Path:
    """浏览器用户数据目录根（每个平台一个子目录）。"""
    if is_frozen():
        root = _localappdata_base() / APP_NAME / "browser"
    else:
        root = resource_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def settings_file() -> Path:
    """GUI 可编辑的 settings.json 路径。"""
    return user_data_root() / "settings.json"


def webui_dir() -> Path:
    """编译后的 webui 静态资源目录。"""
    candidates = [
        resource_root() / "api" / "webui",
        resource_root() / "webui_dist",
        program_root() / "api" / "webui",
    ]
    for c in candidates:
        if (c / "index.html").exists():
            return c
    return candidates[0]


def resource_path(rel: str) -> str:
    """返回只读资源文件的绝对路径（打包/开发态通用）。

    打包后资源位于 sys._MEIPASS（PyInstaller 解包目录），
    开发态位于项目根目录。解决代码里用相对路径 'libs/xxx.js' 读取文件时
    因工作目录不同而找不到的问题。"""
    rel = rel.replace("/", os.sep).lstrip(os.sep)
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return str(base / rel)


def ensure_runtime_dirs() -> None:
    """启动时创建所有必要的可写目录。"""
    user_data_root()
    logs_dir()
    browser_data_root()
    # 数据导出子目录
    (user_data_root() / "data").mkdir(parents=True, exist_ok=True)


def apply_config_paths() -> None:
    """把重定向后的路径注入 config 模块（在 import config 之后调用）。"""
    try:
        import config
    except Exception:
        return

    data_root = user_data_root()

    # 数据保存路径
    if not getattr(config, "SAVE_DATA_PATH", ""):
        config.SAVE_DATA_PATH = str(data_root)

    # 用户数据目录（浏览器登录态）
    browser_root = browser_data_root()
    config.USER_DATA_DIR = str(browser_root / "%s_user_data_dir")

    # 停止词文件：打包后从资源根读取
    sw = resource_root() / "docs" / "hit_stopwords.txt"
    if sw.exists():
        config.STOP_WORDS_FILE = str(sw)
