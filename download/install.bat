@echo off
chcp 65001 >nul
title TriGenClaw 一键安装
echo ============================================
echo   TriGenClaw 一键安装
echo   正在从服务器下载最新版本...
echo ============================================
echo.

:: 检测架构
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
  set ARCH=win-x64
) else (
  set ARCH=win-x86
)

:: 下载最新 ZIP 便携版
set DOWNLOAD_URL=https://github.com/wj910621/ai-nexus-server/releases/latest/download/TriGenClaw-Portable.zip
set INSTALL_DIR=%USERPROFILE%\Desktop\TriGenClaw

echo 📥 下载地址: %DOWNLOAD_URL%
echo 📂 安装目录: %INSTALL_DIR%
echo.

:: 创建临时目录
set TEMP_DIR=%TEMP%\TriGenClaw-Install
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

:: 下载
echo 正在下载...
curl -L -o "%TEMP_DIR%\TriGenClaw.zip" "%DOWNLOAD_URL%" --progress-bar 2>&1
if %errorlevel% neq 0 (
  echo ❌ 下载失败！请检查网络连接。
  echo 也可以手动访问: https://j3trisheng.com/download
  pause
  exit /b 1
)

:: 解压
echo 正在解压...
powershell -Command "Expand-Archive -Path '%TEMP_DIR%\TriGenClaw.zip' -DestinationPath '%INSTALL_DIR%' -Force" 2>&1
if %errorlevel% neq 0 (
  echo ❌ 解压失败！
  pause
  exit /b 1
)

:: 创建桌面快捷方式
echo 正在创建桌面快捷方式...
mshta VBScript:Execute("Set a=CreateObject(""WScript.Shell""):Set b=a.CreateShortcut(a.SpecialFolders(""Desktop"") & ""\TriGenClaw.lnk""):b.TargetPath=""%INSTALL_DIR%\TriGenClaw.exe"":b.WorkingDirectory=""%INSTALL_DIR%"":b.IconLocation=""%INSTALL_DIR%\TriGenClaw.exe,0"":b.Save:close") 2>&1

echo.
echo ============================================
echo   ✅ 安装完成！
echo.
echo   桌面快捷方式已创建
echo   双击 "TriGenClaw" 即可运行
echo.
echo   安装位置: %INSTALL_DIR%
echo ============================================
echo.
:: 询问是否立即启动
set /p START_NOW=是否立即启动 TriGenClaw？(Y/N):
if /i "%START_NOW%"=="Y" (
  start "" "%INSTALL_DIR%\TriGenClaw.exe"
)
echo.
echo 感谢使用 TriGenClaw！
pause
