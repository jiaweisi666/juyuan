#!/usr/bin/env bash
# AI 模型聚合网关 - 本地一键启动 (Linux / macOS)
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================================"
echo "  AI 模型聚合网关 - 本地一键启动"
echo "============================================================"

echo
echo "[1/4] 检查后端虚拟环境..."
if [ ! -x "backend/.venv/bin/python" ]; then
    echo "      创建虚拟环境 backend/.venv ..."
    python3 -m venv backend/.venv
fi

echo "[2/4] 安装后端依赖..."
backend/.venv/bin/python -m pip install --upgrade pip >/dev/null
backend/.venv/bin/python -m pip install -r backend/requirements.txt

echo "[3/4] 构建前端..."
if command -v npm >/dev/null 2>&1; then
    (cd frontend && npm ci && npm run build)
else
    echo "      未检测到 npm，跳过前端构建；将使用现有 frontend/dist（如有）。"
fi

echo "[4/4] 启动网关: http://127.0.0.1:8300"
echo
cd backend
export PYTHONDONTWRITEBYTECODE=1
exec .venv/bin/python run.py
