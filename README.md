# 聚元 · AI 模型聚合网关

基于 `lumingya/universal-web-api` 二次开发的本地 AI 网关，**开箱即用、双击启动**。它将网页版 DeepSeek 的对话能力封装为统一 API，对外暴露 **OpenAI 兼容接口**，同时自带简洁的 Web 控制台，方便你管理账号、切换模型、查看会话。

> **安全定位**：默认仅供本机使用，管理面板与网关均监听 `127.0.0.1`，**不提供公网默认部署方案**。

---

## 一、核心能力

| 模块 | 说明 |
| --- | --- |
| **一键启动** | 双击 `JuyuanLauncher.exe` 即可同时拉起底座、网关与受控浏览器，无需命令行 |
| **Web2API 转换** | 将 DeepSeek 网页版对话能力转换为 OpenAI 兼容接口（`/v1/chat/completions`） |
| **账号池管理** | 支持导入多个 DeepSeek 账号的登录态（Cookie / localStorage），自动轮询防风控 |
| **统一对话窗口** | 内置 880×580 桌面风格控制台，支持会话历史、SSE 流式输出、新建对话 |
| **模型切换** | 支持 `chat`、`reasoner`、`chat-online`、`reasoner-online` 四种模式一键切换 |

---

## 二、目录结构

```
juyuan_code/
├── JuyuanLauncher.exe          # 一键启动器（双击运行）
├── start.cmd / start.sh        # 命令行启动脚本（开发/调试时使用）
├── juyuan_launcher.py          # 启动器源码（Python，可被 PyInstaller 打包为 exe）
│
├── backend/                    # FastAPI 网关后端
│   ├── app/
│   │   ├── api/                # 路由：chat / admin / OpenAI 兼容接口
│   │   ├── platforms/          # 平台插件：DeepSeek 适配器
│   │   ├── gateway/            # 网关编排（orchestrator）
│   │   ├── storage/            # SQLite 数据层（会话、账号）
│   │   └── resources/          # platforms.json（平台定义 + 模型别名）
│   ├── .env.example            # 环境变量示例（一般无需修改）
│   └── requirements.txt        # Python 依赖
│
├── frontend/                   # Vite + React 19 + Tailwind 4 控制台
│   ├── src/pages/              # 对话页 / 配置页 / API Keys 页
│   └── dist/                   # 构建产物（由后端自动托管）
│
└── vendor/universal-web-api/   # 底座（网页自动化 + 受控浏览器）
```

---

## 三、快速开始（推荐方式）

### 方式一：双击启动（Windows）

1. 确保你的电脑已安装 **Python 3.10+**（安装时勾选“Add to PATH”）。
2. 进入 `juyuan_code` 文件夹，**双击 `JuyuanLauncher.exe`**。
3. 启动器会自动完成以下事情：
   - 创建并初始化后端虚拟环境（`backend/.venv`）
   - 启动**底座**服务（`http://127.0.0.1:8199`）与**受控浏览器**（CDP 端口 `9222`）
   - 启动**聚合网关**（`http://127.0.0.1:8300`，并托管前端页面）
   - 就绪后自动打开系统默认浏览器访问 `http://127.0.0.1:8300`

> 首次启动需要等待 1~2 分钟安装依赖，后续启动秒开。保持黑色命令行窗口运行，**按 `Ctrl + C` 可退出**并清理所有子进程。

---

### 方式二：命令行启动（Windows / Linux / macOS）

```bash
# Windows
start.cmd

# Linux / macOS
chmod +x start.sh && ./start.sh
```

脚本会自动：创建虚拟环境 → 安装依赖 → 构建前端 → 启动网关。

手动启动（已装好依赖时）：

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt     # Linux/macOS
.venv/Scripts/python run.py
```

---

## 四、使用指南

### 1. 打开管理面板

启动完成后，浏览器会自动打开 `http://127.0.0.1:8300`。

左侧导航栏：
- **聚元**：点击返回对话首页
- **对话**：进入对话页面，选择模型、输入问题
- **API**：查看和管理 API Key
- **配置**：进入账号管理与模型配置

---

### 2. 配置 DeepSeek 账号（必须）

项目目前内置 **DeepSeek** 平台，使用前需要导入你的 DeepSeek 登录态：

1. 点击左侧 **配置** → 进入 **账号管理** 标签页。
2. 点击 **「导入登录态」** 按钮。
3. 系统会在受控浏览器中打开 `https://chat.deepseek.com`，**请手动完成登录**（扫码或密码）。
4. 登录成功后，回到管理面板，点击对应账号的 **「应用登录态」**。
5. 账号状态变为 **就绪**，即可开始对话。

> **提示**：
> - 支持导入多个账号，系统会自动轮询，降低单账号风控概率。
> - 若重启后账号显示异常，点击 **「应用登录态」** 即可重新注入 Cookie，无需重复登录。

---

### 3. 对话与模型切换

进入 **对话** 页面：
- 顶部下拉框可切换模型：`chat`、`reasoner`、`chat-online`、`reasoner-online`。
- 输入框发送消息，`Enter` 发送，`Shift + Enter` 换行。
- 点击 **「新对话」** 可清空当前上下文，在 DeepSeek 网页端开启新的独立对话。
- 左侧会话栏会保存历史记录，点击即可回顾。

---

### 4. OpenAI 兼容接口

第三方应用可通过标准 OpenAI 格式调用本地网关：

```bash
curl http://127.0.0.1:8300/v1/chat/completions \
  -H "Authorization: Bearer sk-juyuan-local" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

可用模型名：
- `deepseek-chat`
- `deepseek-reasoner`
- `deepseek-chat-online`
- `deepseek-reasoner-online`

> 如需修改 API Key，请编辑 `backend/.env` 中的 `GATEWAY_API_KEY`。

---

## 五、环境变量（可选）

一般用户无需修改。如需调整，复制 `backend/.env.example` 为 `backend/.env`：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `GATEWAY_API_KEY` | `sk-juyuan-local` | 对外 API Key |
| `GATEWAY_ADMIN_TOKEN` | `juyuan-admin` | 管理面板接口令牌 |
| `GATEWAY_DATA_DIR` | `backend/data` | 数据目录（SQLite、账号、密钥） |
| `GATEWAY_ACCOUNT_RPM` | `12` | 单账号每分钟最大请求数 |
| `GATEWAY_COOLDOWN_SECONDS` | `90` | 触发风控后的冷却秒数 |
| `GATEWAY_MAX_CONCURRENCY` | `2` | 全局并发上限 |
| `GATEWAY_BASE_WEB_API_URL` | `http://127.0.0.1:8199` | 底座服务地址 |

---

## 六、常见问题

**Q：双击 `JuyuanLauncher.exe` 后黑窗口闪退？**  
A：请确保系统已安装 Python 3.10+ 并添加到 PATH。首次启动需要联网安装依赖，请保持网络畅通。

**Q：启动后浏览器没有自动打开？**  
A：手动访问 `http://127.0.0.1:8300` 即可。若端口冲突，请检查是否有其他程序占用了 `8300` 或 `8199`。

**Q：对话返回“服务繁忙”或没有回复？**  
A：请检查 **配置 → 账号管理** 中是否有账号状态为 **就绪**。若没有，请重新执行「导入登录态」→「应用登录态」。

**Q：如何更新前端代码？**  
A：修改 `frontend/src/` 下的代码后，进入 `frontend` 目录执行 `npm install && npm run build`，然后重启 `JuyuanLauncher.exe`。

---

## 七、安全说明

- 所有请求均由后端 Python 转发，浏览器不直接暴露上游平台凭据。
- 账号 Cookie / sessionKey 等敏感字段使用 Fernet 加密存储在本地 SQLite。
- 管理面板与网关默认仅监听 `127.0.0.1`，不对外暴露。

---

## 八、技术栈

- **后端**：Python · FastAPI · Uvicorn · Pydantic · SQLite · SSE 流式
- **前端**：Vite 6 · React 19 · Tailwind CSS 4
- **底座**：`lumingya/universal-web-api`（DrissionPage 网页自动化）
- **打包**：PyInstaller（`JuyuanLauncher.exe`）
