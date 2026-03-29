@echo off
chcp 65001 >nul
title GoAI - 围棋AI (KataGo + RTX 5090)

cd /d "%~dp0"

echo ============================================================
echo   GoAI 围棋 AI — KataGo v1.16.4 + RTX 5090 (OpenCL)
echo ============================================================
echo.

if not exist "katago\katago.exe" (
    echo [!] KataGo 未安装，运行安装程序...
    python setup.py
    if not exist "katago\katago.exe" (
        echo [错误] 安装失败
        pause & exit /b 1
    )
)

if not exist "katago\model.bin.gz" (
    echo [!] 模型不存在，运行安装程序...
    python setup.py
)

echo 启动 GoAI 服务器...
echo KataGo 初始化约需 5-10 秒（首次运行后更快）
echo.
echo 浏览器将在初始化完成后自动打开
echo ============================================================
echo.

REM Open browser after KataGo initializes (delay 12s)
start /b cmd /c "timeout /t 12 >nul && start http://localhost:8000"

python server.py

pause
