@echo off
REM ============================================
REM SearXNG Setup Launcher for Windows
REM ============================================
REM This script launches SearXNG setup in WSL
REM ============================================

echo ============================================
echo SearXNG Setup for Windows
echo ============================================
echo.

REM Check if WSL is installed
wsl --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] WSL is not installed
    echo.
    echo Please install WSL first:
    echo   wsl --install
    echo.
    echo After installation, restart your computer and run this script again.
    pause
    exit /b 1
)

echo [OK] WSL is installed
echo.

REM Check if Docker is accessible in WSL
echo Checking Docker in WSL...
wsl docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not available in WSL
    echo.
    echo You need Docker installed in WSL:
    echo   Option 1: Install Docker Desktop for Windows
    echo   Option 2: Install Docker in WSL manually
    echo.
    echo Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo [OK] Docker is available
echo.

REM Get current directory in WSL format
for /f "delims=" %%i in ('wsl wslpath -u "%CD%"') do set WSL_PATH=%%i
echo Project path in WSL: %WSL_PATH%
echo.

REM Run setup script in WSL
echo ============================================
echo Running SearXNG setup in WSL...
echo ============================================
echo.

wsl bash "%WSL_PATH%/scripts/setup_searxng.sh"

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo [SUCCESS] SearXNG setup complete!
    echo ============================================
    echo.
    echo Access Points:
    echo   Web UI:  http://localhost:8888
    echo   API:     http://localhost:8888/search?q=query^&format=json
    echo.
    echo Docker Commands ^(run in PowerShell^):
    echo   wsl docker ps                  # Check status
    echo   wsl docker logs searxng        # View logs
    echo   wsl docker restart searxng     # Restart
    echo   wsl docker stop searxng        # Stop
    echo   wsl docker start searxng       # Start
    echo.
    echo Test the setup:
    echo   python test_searxng_integration.py
    echo.
) else (
    echo.
    echo ============================================
    echo [ERROR] Setup failed
    echo ============================================
    echo.
    echo Troubleshooting:
    echo   1. Check Docker Desktop is running
    echo   2. Check WSL has network access
    echo   3. Run manually: wsl bash scripts/setup_searxng.sh
    echo   4. View logs: wsl docker logs searxng
    echo.
)

pause
