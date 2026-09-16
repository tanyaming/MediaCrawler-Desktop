# MediaCrawler 桌面版 —— 一键构建脚本 (PowerShell)
# 用法:  powershell -ExecutionPolicy Bypass -File build.ps1
#
# 步骤:
#   1) 构建前端 webui -> api/webui
#   2) 安装 Python 构建依赖
#   3) PyInstaller 打包 -> dist/MediaCrawler/
#   4) (可选) Inno Setup 生成安装包 -> dist/MediaCrawler-Setup-*.exe

param(
    [switch]$SkipFrontend,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Step($msg) { Write-Host "`n==== $msg ====" -ForegroundColor Cyan }

# ---------- 1. 前端 ----------
if (-not $SkipFrontend) {
    Step "构建前端 WebUI"
    Push-Location "$Root\webui"
    if (-not (Test-Path "node_modules\vite")) {
        npm install --no-audit --no-fund --include=dev
    }
    npm run build
    Pop-Location
    Write-Host "前端产物: api/webui" -ForegroundColor Green
} else {
    Write-Host "跳过前端构建" -ForegroundColor Yellow
}

# ---------- 2. Python 依赖 ----------
Step "安装 Python 构建依赖"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller pywebview

# ---------- 3. PyInstaller ----------
Step "PyInstaller 打包"
python -m PyInstaller "desktop\MediaCrawler.spec" --noconfirm --clean
Write-Host "打包产物: dist\MediaCrawler\MediaCrawler.exe" -ForegroundColor Green

# ---------- 4. Inno Setup ----------
if (-not $SkipInstaller) {
    Step "生成安装包 (Inno Setup)"
    $iscc = $null
    foreach ($p in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )) {
        if (Test-Path $p) { $iscc = $p; break }
    }
    if ($iscc) {
        & $iscc "desktop\installer.iss"
        Write-Host "安装包: dist\MediaCrawler-Setup-1.0.0.exe" -ForegroundColor Green
    } else {
        Write-Host "未检测到 Inno Setup 6，跳过安装包生成。" -ForegroundColor Yellow
        Write-Host "可从 https://jrsoftware.org/isdl.php 安装后重跑本步骤。" -ForegroundColor Yellow
    }
}

Step "完成"
Write-Host "可执行文件: dist\MediaCrawler\MediaCrawler.exe"
