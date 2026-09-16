# -*- coding: utf-8 -*-
"""
MediaCrawler 桌面版启动器。

用法:
  MediaCrawler.exe                      -> 打开桌面 GUI 窗口
  MediaCrawler.exe --run-crawler ...     -> 以爬虫 worker 模式运行（内部调用）
  MediaCrawler.exe --server-only [port]  -> 只启动本地服务（不开窗口，便于调试）

打包后 sys.executable 就是本 exe，crawler worker 通过 "同一 exe + --run-crawler" 分派，
彻底摆脱对 python/uv 命令行的依赖。
"""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import traceback

# ---- 保证可 import 项目根模块 ----
def _bootstrap_sys_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    for p in (root, here):
        if p not in sys.path:
            sys.path.insert(0, p)


def _bootstrap_sys_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    for p in (root, here):
        if p not in sys.path:
            sys.path.insert(0, p)


def _ensure_std_streams() -> None:
    """console=False 的 GUI 程序在 Windows 上 sys.stdout/stderr 为 None，
    而 uvicorn / logging 会调用 .isatty()，导致崩溃。这里补上空流。"""
    class _NullStream:
        encoding = "utf-8"

        def write(self, *a, **k):
            return 0

        def flush(self):
            pass

        def isatty(self) -> bool:
            return False

        def fileno(self):
            raise OSError("no fileno")

        def close(self):
            pass

    if sys.stdout is None:
        sys.stdout = _NullStream()  # type: ignore[assignment]
    if sys.stderr is None:
        sys.stderr = _NullStream()  # type: ignore[assignment]

    # 覆盖 isatty 防呆（某些环境 stdout 存在但无 isatty）
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is not None and not hasattr(stream, "isatty"):
            try:
                stream.isatty = lambda: False  # type: ignore[attr-defined]
            except Exception:
                pass


_ensure_std_streams()

_bootstrap_sys_path()


def _ensure_bundled_node() -> None:
    """把随包内置的 Node 加入 PATH，供 pyexecjs 执行 libs/*.js（客户机无需装 Node）。"""
    try:
        from desktop.paths import resource_path

        node_dir = os.path.dirname(resource_path(os.path.join("runtime", "node", "node.exe")))
        if os.path.isfile(os.path.join(node_dir, "node.exe")):
            os.environ["PATH"] = node_dir + os.pathsep + os.environ.get("PATH", "")
            # pyexecjs 通过 PATH 找 node，这里也显式设一个提示变量
            os.environ.setdefault("EXECJS_RUNTIME", "Node")
    except Exception:
        pass


_ensure_bundled_node()

from desktop import paths  # noqa: E402

logger = logging.getLogger("mediacrawler.launcher")

# 服务启动结果（供 GUI 线程判断）
_server_ready = threading.Event()
_server_error: list = []


def _setup_logging() -> None:
    """把启动日志写到 %APPDATA%\\MediaCrawler\\logs\\launcher.log。"""
    try:
        log_dir = paths.logs_dir()
        log_file = os.path.join(log_dir, "launcher.log")
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        # 避免重复添加
        if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
            root.addHandler(handler)
        logger.info("launcher logging initialised -> %s", log_file)
    except Exception:
        pass


_SINGLE_INSTANCE_MUTEX = None


def _acquire_single_instance() -> bool:
    """Windows 单实例锁：已有实例时返回 False。"""
    global _SINGLE_INSTANCE_MUTEX
    if os.name != "nt":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, False, "Global\\MediaCrawlerDesktopSingleInstance")
        if not handle:
            return True
        ERROR_ALREADY_EXISTS = 183
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            return False
        _SINGLE_INSTANCE_MUTEX = handle
        return True
    except Exception:
        return True


def _focus_existing_window() -> None:
    """把已存在的 MediaCrawler 窗口拉到前台。"""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def _cb(hwnd, _lparam):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            if "MediaCrawler" in buf.value and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        user32.EnumWindows(WNDENUMPROC(_cb), 0)
        for hwnd in found:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def find_free_port(preferred: int = 8756) -> int:
    for port in [preferred] + list(range(preferred + 1, preferred + 50)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_crawler_worker(argv: list[str]) -> int:
    """worker 模式：直接跑 main.py 的爬虫逻辑。"""
    import asyncio

    worker_args = [a for a in argv if a != "--run-crawler"]
    sys.argv = ["main.py", *worker_args]
    # worker 用主线程跑，避免 multiprocessing 在 frozen 下的 __main__ 保护问题
    import main as crawler_main

    try:
        asyncio.run(crawler_main.main())
    except KeyboardInterrupt:
        return 0
    except SystemExit as e:
        return int(e.code or 0)
    finally:
        try:
            asyncio.run(crawler_main.async_cleanup())
        except Exception:
            pass
    return 0


def _run_server_impl(port: int) -> None:
    """启动本地 FastAPI 服务（阻塞）。"""
    import uvicorn

    os.environ["MEDIACRAWLER_PORT"] = str(port)
    # 直接导入 app 对象：frozen 环境下不能用 "api.main:app" 字符串导入
    from api.main import app as fastapi_app

    logger.info("uvicorn starting on 127.0.0.1:%s", port)
    # 自定义 log_config：避免 uvicorn 默认 dictConfig 在无控制台（console=False）
    # 的 frozen 环境里访问 sys.stdout.isatty() 崩溃。
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "logging.Formatter",
                "fmt": "%(levelname)s [%(name)s] %(message)s",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.NullHandler",
            },
            "file": {
                "class": "logging.FileHandler",
                "filename": os.path.join(paths.logs_dir(), "server.log"),
                "encoding": "utf-8",
                "formatter": "default",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["file"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["file"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["file"], "level": "WARNING", "propagate": False},
        },
        "root": {"handlers": ["file"], "level": "INFO"},
    }
    uvicorn.run(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_config=log_config,
        access_log=False,
    )


def _server_target(port: int) -> None:
    """服务线程入口：带异常捕获，失败写日志并置事件。"""
    try:
        _run_server_impl(port)
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
        msg = traceback.format_exc()
        _server_error.append(msg)
        try:
            logger.error("server crashed:\n%s", msg)
        except Exception:
            pass
        _server_ready.set()  # 让 GUI 线程不要一直等


def run_server(port: int) -> int:
    """前台启动服务（用于 --server-only）。"""
    _setup_logging()
    _run_server_impl(port)
    return 0


def run_gui() -> int:
    """GUI 模式：后台守护线程起服务 + pywebview 开窗口。"""
    paths.ensure_runtime_dirs()
    _setup_logging()

    # 单实例：已有实例则聚焦已有窗口后退出
    if not _acquire_single_instance():
        logger.info("another instance is running, focusing it")
        _focus_existing_window()
        return 0

    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    logger.info("GUI mode starting, port=%s url=%s frozen=%s", port, url, getattr(sys, "frozen", False))

    # 用守护线程跑 uvicorn：不引入 multiprocessing，避免 frozen 下的进程递归 spawn。
    server_thread = threading.Thread(
        target=_server_target, args=(port,), name="mc-server", daemon=True
    )
    server_thread.start()

    # 等服务就绪（含 HTTP 探活）
    ok = _wait_for_server(port, timeout=60.0)
    logger.info("server ready=%s", ok)

    if not ok:
        detail = _server_error[0] if _server_error else "timeout waiting for server"
        logger.error("server did not start: %s", detail)
        _show_fatal(detail)
        return 1

    try:
        import webview
    except Exception:
        # pywebview 不可用时退化为系统浏览器
        webbrowser.open(url)
        print(f"[MediaCrawler] 未检测到窗口运行时，已在浏览器中打开: {url}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0

    window = webview.create_window(
        "舆情采集器",
        url,
        width=1360,
        height=900,
        min_size=(1024, 700),
    )
    webview.start()  # 阻塞直到窗口关闭
    return 0


def _show_fatal(detail: str) -> None:
    """服务起不来时给用户一个可见的错误提示（而不是无尽的白屏）。"""
    msg = (
        "舆情采集器本地服务启动失败。\n\n"
        f"详细信息：{detail[:800]}\n\n"
        f"日志文件：{os.path.join(paths.logs_dir(), 'launcher.log')}"
    )
    try:
        import webview

        webview.create_window("舆情采集器启动失败", html=f"<pre>{msg}</pre>", width=760, height=520)
        webview.start()
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, msg, "舆情采集器启动失败", 0x10)
        except Exception:
            print(msg, file=sys.stderr)


def _wait_for_server(port: int, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_error:
            return False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                # 再确认 HTTP 真的能响应
                if _http_ping(port):
                    return True
        time.sleep(0.25)
    return False


def _http_ping(port: int) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    argv = sys.argv[1:]

    if "--run-crawler" in argv:
        return run_crawler_worker(argv)

    if "--server-only" in argv:
        port = find_free_port()
        for i, a in enumerate(argv):
            if a == "--port" and i + 1 < len(argv):
                port = int(argv[i + 1])
        print(f"[MediaCrawler] 本地服务: http://127.0.0.1:{port}")
        return run_server(port)

    return run_gui()


def _log_exception(exc: BaseException) -> None:
    """将启动异常写入日志文件，便于排查（GUI 模式无控制台）。"""
    try:
        log_dir = paths.logs_dir()
    except Exception:
        log_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(log_dir, "launcher-error.log"), "a", encoding="utf-8") as f:
            f.write("\n===== launcher error =====\n")
            f.write(traceback.format_exc())
    except Exception:
        pass
    print(traceback.format_exc(), file=sys.stderr)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:  # noqa: BLE001
        _log_exception(e)
        sys.exit(1)
