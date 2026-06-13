@echo off
echo === TriGen Desktop Build Script ===
echo.

REM Step 1: Install dependencies
echo [1/3] Installing npm dependencies...
call npm install
if %errorlevel% neq 0 (
  echo FAIL: npm install failed
  exit /b 1
)
echo OK: Dependencies installed

REM Step 2: Build for Windows
echo.
echo [2/3] Building Windows installer...
call npm run dist:win
if %errorlevel% neq 0 (
  echo FAIL: Build failed
  exit /b 1
)

REM Step 3: Show results
echo.
echo [3/3] Build complete!
echo.
echo Installer location: release\TriGen-Desktop-*-win-Setup.exe
echo.
echo Commands:
echo   npm start           Run in development mode
echo   npm run dist:win    Build Windows installer
