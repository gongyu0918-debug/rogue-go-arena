@echo off
chcp 65001 >nul
setlocal
title GoAI - 围棋AI

cd /d "%~dp0"

echo ============================================================
echo   GoAI 围棋 AI — 当前源码启动器
echo ============================================================
echo.

set "ENGINE_OPENCL=katago\katago_opencl.exe"
set "ENGINE_CPU=katago\katago_cpu.exe"
set "MODEL_FILE=katago\model.bin.gz"
set "SERVER_EXE=GoAI_Server\GoAI_Server.exe"

if not exist "%MODEL_FILE%" (
    echo [!] 模型不存在，正在运行 setup.py ...
    python setup.py
)

if not exist "%ENGINE_OPENCL%" if not exist "%ENGINE_CPU%" (
    echo [!] KataGo 引擎不存在，正在运行 setup.py ...
    python setup.py
)

if not exist "%MODEL_FILE%" (
    echo [错误] model.bin.gz 仍不存在，无法启动
    pause
    exit /b 1
)

if not exist "%ENGINE_OPENCL%" if not exist "%ENGINE_CPU%" (
    echo [错误] OpenCL / CPU 引擎仍不存在，无法启动
    pause
    exit /b 1
)

echo 启动 GoAI 服务...
if exist "%SERVER_EXE%" (
    echo [i] 使用已打包服务端: %SERVER_EXE%
) else (
    echo [i] 使用 Python 源码服务端: server.py
)
echo [i] 浏览器会在服务响应后自动打开
echo ============================================================
echo.

start "" powershell -NoProfile -WindowStyle Hidden -Command ^
  "$deadline=(Get-Date).AddMinutes(2);" ^
  "while((Get-Date) -lt $deadline){" ^
  "  try {" ^
  "    $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/status' -TimeoutSec 2;" ^
  "    if ($resp) { Start-Process 'http://localhost:8000'; break }" ^
  "  } catch {}" ^
  "  Start-Sleep -Seconds 2" ^
  "}"

if exist "%SERVER_EXE%" (
    "%SERVER_EXE%"
) else (
    python server.py
)

pause
