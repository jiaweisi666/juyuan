# syntax=docker/dockerfile:1
# ============================================================
# AI 模型聚合网关 —— 多阶段构建
#   阶段一：Node 构建前端（Vite + React 19 + Tailwind 4）
#   阶段二：Python 运行后端（FastAPI），并托管前端构建产物
# ============================================================

# ---------- 阶段一：构建前端 ----------
FROM node:20-alpine AS frontend-build
WORKDIR /build/frontend

# 先复制依赖清单以充分利用镜像层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# 再复制源码并构建（产物输出到 /build/frontend/dist）
COPY frontend/ ./
RUN npm run build


# ---------- 阶段二：后端运行 ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GATEWAY_HOST=0.0.0.0 \
    GATEWAY_PORT=8300 \
    GATEWAY_DATA_DIR=/app/backend/data

WORKDIR /app/backend

# 后端依赖（默认仅装 requirements.txt；真实网页自动化见 README）
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 后端源码
COPY backend/ ./

# 前端构建产物（后端 PROJECT_DIR/frontend/dist 下托管）
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

# 数据目录（数据库 / 账号 / 密钥），供卷挂载持久化
RUN mkdir -p /app/backend/data
VOLUME ["/app/backend/data"]

EXPOSE 8300

# 健康检查：/health 返回 200
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8300/health').status==200 else 1)"

CMD ["python", "run.py"]
