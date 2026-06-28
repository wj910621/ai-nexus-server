@echo off
chcp 65001 >nul
title TriGenClaw 亿界版一键安装
color 0A
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║     TriGenClaw 亿界版 — AI 桌面工作台    ║
echo   ║     一键安装脚本 v2.0                    ║
echo   ╚══════════════════════════════════════════╝
echo.
echo   📥 将从本站下载 TriGenClaw-Setup-2.0.0.exe
echo   📂 将安装到桌面: %USERPROFILE%\Desktop\TriGenClaw
echo   💾 文件大小约 66.8MB，请耐心等待...
echo.

:: 优先使用环境变量或命令行参数指定主站地址
set BASE_URL=%~1
if "%BASE_URL%"=="" set BASE_URL=https://j3trisheng.com
set DOWNLOAD_URL=%BASE_URL%/download/TriGenClaw-Setup-2.0.0.exe
set INSTALL_DIR=%USERPROFILE%\Desktop\TriGenClaw
set TEMP_EXE=%TEMP%\TriGenClaw-Setup-2.0.0.exe

:: 清理旧临时文件
if exist "%TEMP_EXE%" del /f /q "%TEMP_EXE%" >nul 2>&1

:: 下载（优先用 curl，失败用 PowerShell）
echo [1/3] 下载中...
echo   URL: %DOWNLOAD_URL%
curl -L -o "%TEMP_EXE%" "%DOWNLOAD_URL%" --progress-bar 2>nul
if %errorlevel% neq 0 (
    echo   curl 失败，尝试 PowerShell 下载...
    powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%TEMP_EXE%' }" 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo   ❌ 下载失败！请检查网络连接。
        echo   💡 手动下载: 打开浏览器访问
        echo      %BASE_URL%/download/
        echo      下载 TriGenClaw-Setup-2.0.0.exe 并双击运行即可
        echo.
        pause
        exit /b 1
    )
)

:: 验证下载
if not exist "%TEMP_EXE%" (
    echo   ❌ 下载文件不存在！
    pause
    exit /b 1
)

for %%A in ("%TEMP_EXE%") do set SIZE=%%~zA
if %SIZE% LSS 30000000 (
    echo   ❌ 下载文件异常（仅 %SIZE% 字节），请重试
    pause
    exit /b 1
)
echo   ✅ 下载完成 (%SIZE% 字节)

:: 清理旧安装
echo [2/3] 安装中...
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%" >nul 2>&1
mkdir "%INSTALL_DIR%" >nul 2>&1

: 运行安装包（便携版 NSIS 安装包，自动解压运行）
echo   正在运行安装程序...
start /wait "" "%TEMP_EXE%" /S /D="%INSTALL_DIR%"

:: 删除临时文件
del /f /q "%TEMP_EXE%" >nul 2>&1

:: 查找 EXE
set EXE_PATH=
for /r "%INSTALL_DIR%" %%F in (TriGenClaw.exe) do (
    set EXE_PATH=%%F
    goto :found
)
:found

if not defined EXE_PATH (
    echo   ⚠️ 未找到 TriGenClaw.exe，尝试查找其他可执行文件...
    for /r "%INSTALL_DIR%" %%F in (*.exe) do (
        set EXE_PATH=%%F
        goto :found2
    )
)
:found2

:: 创建桌面快捷方式
echo [3/3] 创建快捷方式...
if defined EXE_PATH (
    powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\TriGenClaw.lnk'); $Shortcut.TargetPath = '%EXE_PATH%'; $Shortcut.WorkingDirectory = Split-Path '%EXE_PATH%'; $Shortcut.IconLocation = '%EXE_PATH%,0'; $Shortcut.Save()" >nul 2>&1
    echo   ✅ 快捷方式已创建
) else (
    echo   ⚠️ 快捷方式创建失败，请手动运行
)

:: 完成
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║           ✅ 安装完成！                  ║
echo   ║                                         ║
echo   ║  桌面快捷方式: TriGenClaw               ║
echo   ║  安装位置: %INSTALL_DIR%               ║
echo   ║  本地 AI: 首次启动后自动检测 Ollama     ║
echo   ╚══════════════════════════════════════════╝
echo.
echo   💡 双击桌面 "TriGenClaw" 快捷方式即可运行
echo.
pause
