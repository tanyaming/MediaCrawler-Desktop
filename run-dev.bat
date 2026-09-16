@echo off
REM MediaCrawler 桌面版 —— 开发态一键启动（免打包，用于验证功能）
REM 双击本文件即可打开桌面窗口，或访问 http://127.0.0.1:8799
cd /d "%~dp0"
echo [MediaCrawler] 正在启动桌面版...
python desktop\app.py --server-only --port 8799
pause
