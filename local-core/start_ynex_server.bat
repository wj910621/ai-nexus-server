@echo off
chcp 65001 >nul
title Y·NEX 本地AI核心服务
cd /d "C:\Y·NEX版Y·NEX项目"
"C:\Users\13111\.workbuddy\binaries\python\envs\jarvis\Scripts\python.exe" start_ynex_server.py
pause
