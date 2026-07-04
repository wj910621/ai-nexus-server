@echo off
chcp 65001 >nul
title Y·NEX Desktop 开发模式
cd /d "C:\Y·NEX版Y·NEX项目"
"C:\Users\13111\.workbuddy\binaries\python\envs\jarvis\Scripts\python.exe" start_dev_mode.py
pause
