@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   AI 模型聚合网关 - 本地一键启动 (Windows)
echo ============================================================

echo.
echo [1/4] 检查后端虚拟环境...
if not exist "backend\.venv\Scripts\python.exe" (
    echo       创建虚拟环境 backend\.venv ...
    python -m venv backend\.venv || goto :error
)

echo [2/4] 安装后端依赖...
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip >nul
"backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.txt || goto :error
"backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements-web.txt || goto :error

echo [3/4] 构建前端...
where npm >nul 2>nul
if %errorlevel%==0 (
    pushd frontend
    call npm ci || goto :error
    call npm run build || goto :error
    popd
) else (
    echo       未检测到 npm，跳过前端构建；将使用现有 frontend\dist（如有）。
)

echo [4/4] 启动网关: http://127.0.0.1:8300
echo.
cd backend
set PYTHONDONTWRITEBYTECODE=1
".venv\Scripts\python.exe" run.py
goto :eof

:error
echo.
echo 启动失败，请检查上方错误信息。
exit /b 1
