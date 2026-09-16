# -*- coding: utf-8 -*-
"""
PyInstaller 打包入口。

这是打包后的 MediaCrawler.exe 的真正入口。它与 desktop/app.py 的区别：
- 确保 frozen 环境下 sys.path / 资源路径正确
- 把 desktop 包所在目录（打包时随 exe 冻结）纳入 import 路径
"""
import os
import sys


def _bootstrap() -> None:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if base not in sys.path:
        sys.path.insert(0, base)


_bootstrap()

from desktop.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
