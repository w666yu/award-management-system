@echo off
chcp 65001 >nul
title 获奖管理系统（单人版）
echo ================================
echo    🏆 获奖管理系统（单人版） 启动中...
echo ================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 检查依赖...
pip install fastapi uvicorn python-multipart -q 2>nul

REM 启动服务
echo [2/3] 启动服务...
echo [3/3] 浏览器即将打开...
echo.
echo ================================
echo  服务地址: http://127.0.0.1:8091
echo  按 Ctrl+C 可停止服务
echo ================================
echo.

start http://127.0.0.1:8091
python app.py
pause