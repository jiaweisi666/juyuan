# 聚源 · AI 模型聚合网关

基于 `lumingya/universal-web-api` 二次开发的 **AI 模型聚合网关**：将多个 AI 平台的网页能力转换为统一 API，对外暴露 **OpenAI / Anthropic 兼容接口**，内置 **AUTO 智能路由**、**账号池防封号** 与 **统一对话窗口**，让第三方应用用一套协议调用所有平台。

> 安全定位：默认仅供本机使用，管理面板仅监听 `127.0.0.1`，**不提供公网默认部署方案**。

---

## 一、核心能力

| 模块 | 说明 |
| --- | --- |
| **Web2API 转换引擎** | 基于 `PlatformPlugin` 插件体系，把各平台网页/接口转换为 OpenAI 兼容的对话接口；内置模拟适配器，无需真实浏览器即可跑通全链路 |
| **账号池与防封号** | KeyPool 多账号轮询、单账号 RPM 限流、命中风控自动冷却、请求间随机延迟、敏感字段加密存储 |
| **AUTO 智能路由** | 问题评估 → 模型画像 → 加权决策（准确率 0.5 / 延迟 0.2 / 成本 0.3）→ 失败降级 → 基于反馈的画像自优化 |
| **统一对话窗口** | 880×580 桌面风格 Web 控制台，会话历史落 SQLite，SSE 流式输出，消息点赞点踩反馈 |
| **管理面板** | 模型配置、账号管理、路由配置、日志与统计四大页面，前端 Vite + React 19 构建 |

内置平台：`deepseek`、`chatgpt`、`claude`、`kimi`、`gemini`、`qwen`、`doubao`、`glm`。

---

## 二、目录结构

```
juyuan_code/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/              # 路由层：openai / anthropic / admin / chat / system
│   │   ├── accounts/         # 账号池：加密、存储、KeyPool 调度
│   │   ├── platforms/        # 平台插件体系：base / registry / mock / web
│   │   ├── router/           # AUTO 智能路由：评估 / 画像 / 策略 / 引擎
│   │   ├── storage/          # SQLite 存储层
│   │   ├── gateway/          # 网关编排（orchestrator）
│   │   ├── resources/        # platforms.json（平台定义 + 模型别名）
│   │   ├── config.py         # 全局配置（环境变量）
│   │   ├── schemas.py        # OpenAI / Anthropic 兼容数据模型
│   │   ├── tool_calling.py   # Tool Calling 支持
│   │   └── main.py           # 应用入口（并托管前端产物）
│   ├── requirements.txt      # 后端依赖
│   ├── requirements-web.txt  # 可选：真实网页自动化依赖
│   ├── .env.example          # 环境变量示例
│   └── run.py                # 启动入口
├── frontend/                 # Vite + React 19 + Tailwind 4 控制台
│   ├── src/pages/            # 对话 / 模型 / 账号 / 路由 / 日志 五页面
│   ├── src/components/       # UI 原语与图标
│   ├── vite.config.js        # 开发代理 → 127.0.0.1:8300
│   └── dist/                 # 构建产物（由后端托管）
├── vendor/universal-web-api/ # 二次开发底座（参考集成）
├── Dockerfile                # 多阶段构建：Node 构建前端 → Python 运行后端
├── docker-compose.yml        # 一键部署编排
├── start.cmd / start.sh      # 本地一键启动脚本
└── README.md
```

---

## 三、快速开始

### 方式一：Docker 一键部署（推荐）

```bash
# 可选：自定义配置（不改则使用内置默认值）
cp backend/.env.example backend/.env

# 构建并启动
docker compose up -d --build

# 查看日志 / 停止
docker compose logs -f
docker compose down
```

启动后访问 <http://127.0.0.1:8300>。数据持久化在 `backend/data/`，容器重启不丢失。

> 端口映射固定为 `127.0.0.1:8300`，仅本机可访问，符合安全约束。

### 方式二：本地运行

前置条件：Python ≥ 3.10；如需构建前端，另需 Node.js ≥ 18。

```bash
# Windows
start.cmd

# Linux / macOS
chmod +x start.sh && ./start.sh
```

脚本会自动：创建虚拟环境 → 安装后端依赖 → 构建前端 → 启动网关（<http://127.0.0.1:8300>）。

手动启动（已装好依赖时）：

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt     # Linux/macOS
.venv/Scripts/python run.py
```

### 前端开发模式（可选）

```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:5273 ，已配置代理到后端 8300
npm run build      # 产物输出 dist/，由后端自动托管
```

---

## 四、使用指南

### 1. 访问密钥

在 `backend/.env` 中配置（默认值仅用于本机体验，请按需修改）：

- `GATEWAY_API_KEY`：第三方应用调用 `/v1/*` 的 Key（`Authorization: Bearer` 或 `x-api-key`）
- `GATEWAY_ADMIN_TOKEN`：管理面板接口令牌（前端 `X-Admin-Token`）

> 留空表示本机访问免鉴权，**仅建议在 127.0.0.1 下使用**。

### 2. OpenAI 兼容接口

```bash
curl http://127.0.0.1:8300/v1/chat/completions \
  -H "Authorization: Bearer sk-juyuan-local" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

- `GET /v1/models`：列出可用模型（含 `auto`，AUTO 智能路由）
- `model` 填 `auto` 由 AUTO 路由自动选型；填具体模型名则直接路由（失败自动降级）

### 3. Anthropic 兼容接口

```bash
curl http://127.0.0.1:8300/v1/messages \
  -H "x-api-key: sk-juyuan-local" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 4. Tool Calling

在 `/v1/chat/completions` 请求中携带标准 `tools` 参数即可，网关会按 OpenAI 规范回传 `tool_calls`。

### 5. AUTO 智能路由

综合得分 = 准确率 × 0.5 + 延迟 × 0.2 + 成本 × 0.3，权重可在「路由配置」页滑块实时调整（运行时自动归一化）。失败自动降级到候选模型，历史反馈用于模型画像自优化。

---

## 五、环境变量

完整清单见 [`backend/.env.example`](backend/.env.example)，常用项：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `GATEWAY_HOST` / `GATEWAY_PORT` | `127.0.0.1` / `8300` | 服务监听地址 |
| `GATEWAY_API_KEY` | 空 | 对外 API Key |
| `GATEWAY_ADMIN_TOKEN` | 空 | 管理面板令牌 |
| `GATEWAY_DATA_DIR` | `backend/data` | 数据目录（DB / 账号 / 密钥） |
| `GATEWAY_SECRET_KEY` | 空 | 敏感字段加密主密钥（留空自动生成到 `data/secret.key`） |
| `GATEWAY_ACCOUNT_RPM` | `12` | 单账号每分钟最大请求数 |
| `GATEWAY_COOLDOWN_SECONDS` | `90` | 触发风控后的冷却秒数 |
| `GATEWAY_MIN/MAX_DELAY_SECONDS` | `0.3` / `1.2` | 请求随机延迟区间 |
| `GATEWAY_MAX_CONCURRENCY` | `2` | 全局并发上限 |
| `GATEWAY_AUTO_ROUTER_ENABLED` | `true` | 默认开启 AUTO 路由 |
| `GATEWAY_WEIGHT_ACCURACY/LATENCY/COST` | `0.5 / 0.2 / 0.3` | 路由权重 |
| `GATEWAY_REAL_BROWSER_ENABLED` | `false` | 是否启用真实网页自动化 |
| `GATEWAY_MOCK_FALLBACK` | `true` | 真实浏览器不可用时回退模拟适配器 |

---

## 六、安全说明

- 所有大模型请求均由后端 Python 转发，浏览器不直接接触上游平台凭据。
- 账号 cookie / sessionKey 等敏感字段使用 Fernet 加密存储。
- 管理面板默认仅监听 `127.0.0.1`；Docker 部署端口亦绑定回环。
- 对外 API Key 与管理令牌均可自定义。

---

## 七、进阶：接入真实网页平台（可选）

默认使用**模拟适配器**，全链路即可跑通。如需接入真实平台：

1. 安装可选依赖：`pip install -r backend/requirements-web.txt`
2. 在 `backend/.env` 中设置 `GATEWAY_REAL_BROWSER_ENABLED=true`
3. 确保底座 `vendor/universal-web-api` 就绪，并按需配置 `GATEWAY_BASE_WEB_API_URL`
4. Docker 场景下取消 `docker-compose.yml` 中 vendor 卷挂载的注释

---

## 八、技术栈

- **后端**：Python · FastAPI · Uvicorn · Pydantic · SQLite · SSE 流式 · httpx · cryptography
- **前端**：Vite 6 · React 19 · Tailwind CSS 4 · recharts · react-markdown · HugeIcons
- **底座**：`lumingya/universal-web-api`（DrissionPage 网页自动化）
- **部署**：Docker（多阶段构建）· docker-compose
