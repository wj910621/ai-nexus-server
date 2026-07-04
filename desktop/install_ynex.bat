@echo off
chcp 65001 >nul
echo 正在初始化Y·NEX 本地AI核心...

set YNEX_DIR=%~dp0resources\ynex
set PYTHON=%YNEX_DIR%\.venv\Scripts\python.exe

if not exist "%PYTHON%" (
  echo 未找到虚拟环境，尝试使用系统 Python 创建...
  where python >nul 2>nul
  if %errorlevel% neq 0 (
    echo 请先安装 Python 3.10+ 并添加到 PATH
    pause
    exit /b 1
  )
  python -m venv "%YNEX_DIR%\.venv"
)

"%PYTHON%" -m pip install --upgrade pip
"%PYTHON%" -m pip install -r "%YNEX_DIR%\requirements.txt"

echo Y·NEX 核心初始化完成
echo 启动 Y·NEX Desktop...
start "" "%~dp0TriGenClaw.exe"
