# -*- coding: utf-8 -*-
"""
外置配置（settings.json）——GUI 与命令行参数之间的桥梁。

产品化后客户不修改 config/*.py，而是通过 GUI 表单写 settings.json，
再由这里转换成 crawler worker 的命令行参数。
"""
from __future__ import annotations

import json
from typing import Any, Dict

from . import paths

DEFAULT_SETTINGS: Dict[str, Any] = {
    "platform": "xhs",
    "login_type": "qrcode",
    "crawler_type": "search",
    "keywords": "",
    "specified_ids": "",
    "creator_ids": "",
    "start_page": 1,
    "save_option": "jsonl",
    "cookies": "",
    "headless": False,
    "enable_comments": True,
    "enable_sub_comments": False,
    "max_notes_count": 15,
    "max_comments_count": 10,
    "max_concurrency_num": 1,
    "enable_ip_proxy": False,
    "ip_proxy_provider_name": "kuaidaili",
    "static_proxy_url": "",
    "browser_path": "",
    "data_dir": "",
    "language": "zh-CN",
}


def load_settings() -> Dict[str, Any]:
    data = dict(DEFAULT_SETTINGS)
    f = paths.settings_file()
    if f.exists():
        try:
            loaded = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception:
            pass
    return data


def save_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    data = load_settings()
    data.update(patch or {})
    f = paths.settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _b(v: Any) -> str:
    return "true" if v else "false"


def to_worker_args(s: Dict[str, Any]) -> list[str]:
    """把 settings 转成 crawler worker 的命令行参数。"""
    args: list[str] = [
        "--platform", str(s.get("platform", "xhs")),
        "--lt", str(s.get("login_type", "qrcode")),
        "--type", str(s.get("crawler_type", "search")),
        "--save_data_option", str(s.get("save_option", "jsonl")),
        "--get_comment", _b(s.get("enable_comments", True)),
        "--get_sub_comment", _b(s.get("enable_sub_comments", False)),
        "--headless", _b(s.get("headless", False)),
        "--enable_ip_proxy", _b(s.get("enable_ip_proxy", False)),
        "--start", str(int(s.get("start_page", 1) or 1)),
        "--crawler_max_notes_count", str(int(s.get("max_notes_count", 15) or 15)),
        "--max_comments_count_singlenotes", str(int(s.get("max_comments_count", 10) or 10)),
        "--max_concurrency_num", str(int(s.get("max_concurrency_num", 1) or 1)),
        "--ip_proxy_provider_name", str(s.get("ip_proxy_provider_name", "kuaidaili")),
    ]

    ctype = s.get("crawler_type", "search")
    if ctype == "search" and s.get("keywords"):
        args += ["--keywords", str(s["keywords"])]
    elif ctype == "detail" and s.get("specified_ids"):
        args += ["--specified_id", str(s["specified_ids"])]
    elif ctype == "creator" and s.get("creator_ids"):
        args += ["--creator_id", str(s["creator_ids"])]

    if s.get("cookies"):
        args += ["--cookies", str(s["cookies"])]
    if s.get("static_proxy_url"):
        args += ["--static_proxy_url", str(s["static_proxy_url"])]

    data_dir = s.get("data_dir") or str(paths.user_data_root())
    args += ["--save_data_path", str(data_dir)]

    return args
