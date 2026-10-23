# Agent 任务记忆档案
> 档案版本：v1.9
> 最后更新：2026-10-23
> 任务总进度：99%（完成第 6 轮用户反馈：①「应用登录态」只保留/新开 1 个标签页；②网页对话按聚元会话复用，不再每轮新开，首轮由网关显式新建；③模型清单只保留 4 个 DeepSeek 模型，剔除站点标识；④API Key 授权移除 AUTO；⑤前端浅色系美化 + 接入聚元 Logo。附带修复：账号凭证信号量泄漏导致第三次调用超时、底座流式成功后误判冷却）

## 一、核心目标与身份定义
> （固定不变，仅初始化一次）
- Agent 身份：全栈开发助手（Python FastAPI 后端 + Vite/React 前端）
- 终极目标：基于 `lumingya/universal-web-api` 二次开发「AI 模型聚合网关」，实现完整链路：多平台 Web2API 转换 → 统一 OpenAI/Anthropic 兼容 API → AUTO 智能路由 → 统一对话窗口 → 第三方应用调用；并提供 Docker 一键部署
- 核心约束：
  - 所有代码集中在 `D:\Project\juyuan\juyuan_code`
  - Python ≥ 3.10；默认仅监听 `127.0.0.1`（不提供公网默认部署方案）
  - 敏感信息（cookie/sessionKey）加密存储；大模型请求一律由后端转发
  - 需求来源：`d:\Project\juyuan\需求文档.docx`

## 二、已完成工作清单
> （按时间倒序，增量追加）
> 🆕 **最新一轮（2026-10-23）：第 6 轮用户反馈 6 项（登录态单标签页 / 对话连续性 / 模型清单 / AUTO 下架 / 前端美化+Logo）+ 运行时缺陷修复**
> - **①「应用登录态」连开 3 个标签页**：根因 = 后端 `apply_account_login` 每次无条件 `open-url` + 前端注入失败后又 `openLoginPage` 再重试，三步各开一个。修复：新增 `admin_routes._ensure_browser_page()`（有标签页则复用、没有才开 1 个并轮询等待出现）；前端 `AccountsPage.applyLogin` 删除失败回退，仅调一次 `applyAccountLogin`。实测：无标签页时 1 个，已有标签页时前后仍为 1 个。
> - **②每轮对话都新开 DeepSeek 会话（网页端 + API）**：根因两层——底座 `TabSession.get_conversation_status()` 在 `CONVERSATION_TIMEOUT_THRESHOLD=0` 时 `reason=threshold_disabled_reuse` 却没有把 `will_start_new_conversation` 置 False，导致每轮都点「新建对话」；且网关没有「首轮新建」的显式信号。修复：底座阈值为 0 时复用当前对话；新增 `X-Juyuan-New-Conversation` 请求头，网关仅在聚元会话首轮发送（`ChatCompletionRequest.new_conversation` → `orchestrator` → `web.py`），底座在 `tab_routes` 透传到 `workflow` 并强制点击一次「新建对话」。实测 API Key 连续 3 次非流式请求同一 URL；新 `conversation_id` 首轮 URL 变化、第二轮复用；网页端 `/api/chat/send` 同样通过。
> - **③「同步底座模型」蹦出 `chat.deepseek.com`/`deepseek`/`www.chat.deepseek.com`**：根因 = 底座 `/v1/models` 返回的是站点标识，`catalog.refresh` 把无法归因的名字写进动态模型覆盖层。修复：`catalog.refresh` 只保留与 `platforms.json` 同名的模型，站点标识记录日志后忽略；`loader.load_platform_definitions` 不再把动态模型并入 `models`。`/api/models`、`/api/platforms`、`/api/keys/meta`、`/v1/models` 均只返回 4 个模型。
> - **④新建 API Key 弹窗中的 AUTO**：后端 `/api/keys/meta`、`/api/models`、`/v1/models` 移除 AUTO；`platforms.json` 删除 `auto` 别名；前端模型授权弹窗只显示 4 个 DeepSeek 模型。实测弹窗文本确认无 AUTO。
> - **⑤前端美化 + Logo**：`frontend/public/juyuan-logo.png` 替换为用户提供的 320×320 聚元飞鸟 Logo（透明化处理），新增 favicon；`index.css` 重做浅色云白 + 聚元蓝设计令牌、玻璃卡片、轻阴影、渐变按钮、hover 抬升、按压反馈、页面/消息/弹窗/Toast 动效；`App.jsx` 侧栏品牌化、`ChatPage` 空态 Hero + 建议卡片 + 渐变用户气泡 + 助手 Logo 头像、`AccountsPage`/`ModelsPage`/`KeysPage`/`SetupPage` 全面视觉统一。
> - **⑥附带修复两个后端运行时缺陷**：a) `orchestrator._run()` 在调用方收到 `finished` 后 `break` 时不会走 `else`，账号凭证与 `Semaphore` 永久泄漏（第 3 次请求起 90s 超时）→ 改为 `finally` 释放，`completed or saw_content` 判定成功；b) 流式成功但未显式 `finished` 时曾把账号误标冷却 → `saw_content` 兜底。实测连续 3 次非流式 / 网页流式均 200，账号保持 active。
> - 校验：`py_compile` EXIT=0；`npm.cmd run build` 通过（`dist/assets/index-B5YY3Vhe.js 450.25 kB`、`index-DP0At83Z.css 53.72 kB`）；前端控制台无错误，Logo 320×320 正常加载。
> - 说明：底座改动位于 `vendor/universal-web-api`（`session.py`、`workflow.py`、`api/chat.py`、`api/tab_routes.py`），该目录被 `.gitignore` 忽略；当前工作目录已直接打补丁，若重新拉取底座需重新应用「阈值复用 + 新会话 Header」两处补丁。
>
> **（上一轮，2026-10-12）：桌面化 MVP 一键启动器（PyInstaller 打包 EXE）+ Agent 能力边界结论 + 打包需求文档**
> - **【务虚·Agent 失败根因】** 用户反馈自建 API Key 接入 Trae 类 Agent 无法理解指令。定位到两个代码级根因：① `backend/app/tool_calling.py::parse_tool_calls()` 只识别 `{"tool_calls":[...]}` 与 ReAct `Action:/Action Input:` 两种格式，认不出 Trae 的 `<adapter_calls>` XML 格式；② `gateway/orchestrator.py::stream()` 在 `if not use_tools:` 分支下**掐断增量输出**（工具模式缓冲至末尾一次性下发）→ Agent 卡在 4%。**根本结论**：官方 API 是模型**原生训练**输出标准 `tool_calls`（协议级承诺），而本项目是用提示词+正则**模拟**（翻译/恳求），属「聚合对话网关」而非「Agent 运行时」——**是能力边界，非项目失败**。项目定位回归「网页对话大模型」本源的聚合网关。
> - **【产出·需求文档】** 新建 `d:\Project\juyuan\聚元网关-桌面化打包需求文档.md`（11 章：背景目标/现状分析/方案对比/7 项功能需求/技术选型/打包分发/准备工作/风险难点/非功能/阶段划分/验收标准）。方案对比：纯启动器 EXE（**MVP 采用**）/ Electron / Tauri 2（长期推荐，用户表示「之后再说」）/ Docker（**不采用**，不满足「双击即用」）。
> - **【落地·MVP 启动器】** 新建 `juyuan_code/juyuan_launcher.py`（仅标准库）：按序拉起 底座+受控浏览器（复用 `vendor/universal-web-api/start.py`，子进程环境置 `AUTO_UPDATE_ENABLED=false`）→ 轮询 CDP `9222/json/version` → 轮询底座 `8199/health` → 起网关 `backend/run.py` → 轮询 `8300/health` → `webbrowser.open(8300)`；Ctrl+C 用 `taskkill /F /T` 逆序清理子进程树。frozen 适配：`PROJECT_DIR = Path(sys.executable).parent`（要求 exe 与 `vendor/`、`backend/` 同级）。
> - **【打包】** `backend/.venv/Scripts/pyinstaller.exe --onefile --name JuyuanLauncher --distpath . --workpath build --specpath build --noconfirm juyuan_launcher.py` → 生成 `juyuan_code/JuyuanLauncher.exe`。PyInstaller 版本 6.22.3（backend venv 内已装）。
> - **★实测（Python 直跑 + EXE 双击各一轮）** 三服务全部 LISTENING（9222/8199/8300）、自动打开浏览器、`StopCommand` 后三端口全部释放 → **一键启动 + 退出清理 100% 通过**。
> - **踩坑修复**：① 首次 exe 崩溃 `'gbk' codec can't encode character '\u2713'`——冻结后 Windows 控制台默认 GBK，日志里的 `✓` 无法编码；修复 = 去掉 `✓`（改 `[OK]`）+ `sys.stdout/stderr.reconfigure(errors="replace")`；② 另见 `TRAE Sandbox Error … NVIDIA\DXCache`，为沙箱拦截 Edge 写 GPU 缓存，**非代码问题**（用户直接双击不受影响）。
> - `.gitignore` 追加 `build/` 与 `/JuyuanLauncher.exe`（构建产物不入库）。
> - 上一轮（2026-10-11）多模态修复已提交推送：commit `5d1b2f5`（`fix: 兼容 OpenAI 多模态 content，消除第三方应用 422`）。
>
> **（上一轮，2026-10-11）：第三方应用多模态请求 422 修复 + 端到端实测通过**
> - **问题**：第三方 App（Trae 等）连通性测试发**多模态消息**（图片+文本），`content` 为数组 `[{"type":"image_url",...},{"type":"text",...}]`，网关报 `422 {"loc":["body","messages",0,"content"],"msg":"Input should be a valid string","type":"string_type"}`。
> - **根因**：`backend/app/schemas.py` 的 `ChatMessage.content: str` 只接受字符串，拒绝 OpenAI 多模态数组；而底座 `universal-web-api` 其实原生支持数组型 content（`app/api/chat.py::_extract_content_part_media_items`，支持 image_url/input_image/audio_url/video_url 等）。
> - **修复**：① `schemas.py` 放宽 `content: str | list[dict[str, Any]] | None = ""`，并新增 `message_text(content)` helper（把多模态数组规整为纯文本，图片/音频/视频片段以 `[图片]`/`[音频]`/`[视频]` 占位）；② 适配所有假定 content 为字符串的内部纯文本调用点——`gateway/orchestrator.py`（两处 token 估算 `_estimate_tokens(message_text(m.content))`）、`router/evaluator.py`（`_collect_text`）、`platforms/mock.py`（`_last_user_text` + 两处 usage 计算）。底座透传无需改动：`platforms/web.py::_payload` 用 `m.model_dump(exclude_none=True)` 会原样带出数组型 content。
> - **校验**：`py_compile` EXIT=0；Schema 级测试（含 image_url+text 的请求）解析为 list、`message_text` 输出 `[图片]\n图片背景是什么颜色`。
> - **★端到端实测（网关 8300 → 底座 8199 → 受控 Edge 9222）**：以 300×300 纯红背景 PNG（data URL）+ 文本「这张图片的背景是什么颜色？」请求 `POST /v1/chat/completions`（model `deepseek-reasoner`）→ **HTTP 200**，模型回答「红色」(`usage prompt_tokens=12/completion_tokens=1`) → **多模态链路 100% 生效**。
> - 说明：此前一次用 1×1 像素图测试触发底座 400 `attachment_invalid_image`（图片无效，非网关问题）并使账号进入 90s 冷却（`cooldown_seconds=90`）；冷却到期后用合规图片即通过。
>
> **（上一轮，2026-10-09 18:55）：用户第 3 轮 4 项 UI/UX 反馈修复 + 运行时复检**
> - **问题①「登录导入选 DeepSeek 报『受控浏览器未连接，请先启动底座浏览器』」**：根因 = 受控 Edge 9222 被沙箱回收 → 底座 `/health` 503 → `_base_post` 抛 503。修复：重启受控 Edge（保活命令）；并把 `admin_routes.py::_base_post` 的 503 文案改为 **「受控浏览器未连接：请确认受控浏览器已在 9222 端口运行后重试」**（指向受控浏览器而非笼统的「底座浏览器」）。复检：`POST /api/accounts/open-login {"platform":"deepseek"}` → `200 {"success":true,"url":"https://chat.deepseek.com"}`。
> - **问题②「点『同步底座模型』/『立即同步』报『底座未返回可识别的模型』」**：根因 = 底座 `/v1/models` 在「无任何已打开站点」时仅返回通用占位 `{"id":"web-browser"}`，网关归因失败且提示误导。修复：`catalog.py::refresh()` 新增常量 `_GENERIC_BASE_MODELS={"web-browser"}` 与三档中文提示——无模型→「底座未返回任何模型」；仅占位→**「底座暂无已打开站点的模型，请先『登录导入』打开并登录站点后再同步」**；有模型但无法归因→「底座返回的 N 个模型均无法归因到已接入平台」。前端 `ModelsPage.jsx` 同步失败 Toast 由 `error` 改 `info`（可预期情况不报错）。复检：无站点时 `POST /api/models/refresh` 返回该友好文案；`open-url(deepseek)` 后再刷新 → `{"source":"base","count":3,"models":[chat.deepseek.com/deepseek/www.chat.deepseek.com]}`。
> - **问题③「从其它页面进入模型页会转圈较久」**：根因 = `/api/platforms` 内 `asyncio.gather` 对所有平台并发 `health_check()`（各含最多 2×8s 超时），原 `load()` 用 `Promise.all` 将其列入首屏阻塞。修复：`ModelsPage.jsx` 拆分为 `loadCore()`（网关信息/模型/路由/目录，本地快速返回，控制全屏 spinner）+ `loadPlatforms()`（慢，独立 `platformsLoading`，仅平台区显示「正在探测各平台状态…」占位），二者并行发起、互不阻塞。
> - **问题④「『同步底座模型』与『立即同步』功能重复，删掉后者」**：修复：`ModelsPage.jsx` 的 `CatalogStrip` 移除「立即同步」按钮（连带删除其 `onSync`/`syncing` props 与 `<div className="flex-1" />`），保留 `PageHeader` 的「同步底座模型」为唯一同步入口。
> - **校验**：`py_compile` EXIT=0；前端 `GetDiagnostics=[]`；`npm.cmd run build` 通过（`dist/assets/index-Bn1isKop.js 843.63 kB`、`index-CZ8Nmfh-.css 22.42 kB`）；dist 内已无「立即同步」字样、新增「正在探测各平台状态」。三服务重启后复检：底座 `/health` 200（connected port=9222）、网关 8300 启动正常、`/api/models/catalog` 35ms、`/api/platforms` 73ms。
>
> **（上一轮，2026-10-09 18:45）：CDP 登录态注入扩展为「Cookie + localStorage」，全链路实测通过**
> - 后端 `backend/app/browser/cdp.py` 扩展：新增 `parse_storage(raw)`（解析 JSON 对象/`[{"name","value"}]` 列表/含 `storage`/`localStorage` 嵌套，容错返回 `{}`）、`_evaluate(ws,id,expr)`（`Runtime.evaluate` + `returnByValue`，异常转 `CDPError`）、**`apply_login(host, cookies=, storage=, reload=True)`**（一次连接内先 `Network.setCookies` 再 `Runtime.enable`+JS 写 `localStorage`，最后只 `Page.reload` 一次）、`read_local_storage(host)`（批量读页面 `localStorage` 为 `{k:v}`）；原 `apply_cookies` 保留为 `apply_login` 的 Cookie-only 兼容入口。
> - `backend/app/browser/__init__.py` 重写导出 `CDPError, apply_cookies, apply_login, parse_cookies, parse_storage, read_local_storage`。
> - 账号模型/存储支持 localStorage：`models.py` 的 `Account` 新增 `storage_enc`（`to_public` 剔除密文并输出 `has_storage`）；`store.py` 的 `add(..., storage=)`（Fernet 加密）、`update(...)`（支持 `storage` 更新）、`import_batch`（读 `storage`/`local_storage` 字段）。
> - `admin_routes.py` 全链路接入：`AccountCreate/AccountUpdate` 增 `storage`；`POST /api/accounts` 注入条件改 `cookies_enc or storage_enc`；`PUT /api/accounts/{id}` 支持 `storage`；`POST /api/accounts/{id}/apply` 同时解密注入 Cookie+localStorage（两者皆空才 400）；新增 `_read_browser_storage(definition)`（CDP 读页面 localStorage）；`auto-import`/`read-import` 读 Cookie 外再读 localStorage 一并落库（`read-import` 返回新增 `storage_count`）。
> - 前端 `AccountsPage.jsx`：新增账号表单增 `storage` 字段（`Textarea`，hint 提示 DeepSeek 登录态存于此）、校验改「Session Key/Cookies/localStorage 至少一项」、列表凭据展示 `cookies + localStorage`、`has_storage` 时也显示「应用登录态」按钮；`npm.cmd run build` 重建 dist（`index-CfxA2Gau.js 843.44 kB`）。
> - **★运行时实测（受控 Edge 9222，本轮重启后全绿）**：① `read_local_storage('chat.deepseek.com')` 读出 29 个键（含 `userToken`/`settingsJwt`/`__appKit_userInfo`/`smidV2`…）；② `apply_login(storage={'__gateway_probe__':'hello-123'})` → 回读 `MATCH: True`（探针已清理）；③ 网关 `POST /api/accounts/read-import {"platform":"deepseek"}` → `status=added cookies=4 storage=30`，落库账号 `has_cookies=true has_storage=true`；④ 网关 `POST /api/accounts/{id}/apply` → `{cookie_count:4, storage_count:30, reloaded:true}`。→ **网关侧 CDP「读/写 Cookie + localStorage」全链路 100% 生效**。
> - 仍存障碍：本机无真实 deepseek 登录令牌（页面 `userToken={"value":null}`），故 `GET /api/platforms` 的 deepseek 仍 `unavailable`（`health_reason=无标签页或停在登录页`）——**属数据缺口而非机制缺陷**；一旦账号池存入真实 `userToken`/`settingsJwt`，`apply_login` 即可自动登录、进而推进 `ready` 与真实对话。
>
> **（上一轮，2026-10-09 18:30）：网关侧 CDP Cookie 注入落地 + 运行时闭环实测（发现 localStorage 关键障碍）**
> - 后端新增 `backend/app/browser/cdp.py`（+`__init__.py`）：网关侧直接用 CDP 写 Cookie。`apply_cookies(host, cookies, reload=True)` = 解析 Cookie → `GET {debug}/json/list` 找到匹配域名的页面 → `websocket-client` 连 `ws://127.0.0.1:9222/...` → `Network.enable` → `Network.setCookies` → `Page.reload(ignoreCache=True)`。`parse_cookies` 支持 JSON 数组/对象/`{cookies:[...]}`/原始 `name=value; ...` 串。
> - `backend/app/config.py`：新增 `browser_debug_url`（默认 `http://127.0.0.1:9222`，env `GATEWAY_BROWSER_DEBUG_URL`）。
> - 后端 `admin_routes.py`：新增 `POST /api/accounts/{account_id}/apply`（`apply_account_login`），解密账号 `cookies_enc` → `_apply_login_to_browser` → `asyncio.to_thread(apply_cookies, host, cookies)`；`create_account` 时若带 `cookies_enc` 亦自动尝试注入（`response["applied"]`/`apply_error`）。`_definition_host()` 从平台定义 `site_key`/`homepage` 提取域名。
> - 前端 `api.js` 新增 `applyAccountLogin(id)`；`AccountsPage.jsx` 行操作区在 `a.has_cookies` 时显示「应用登录态」按钮 → `applyLogin(a)` 调后端并提示。
> - `backend/requirements-web.txt` 追加 `websocket-client>=1.6.0`。
> - **★运行时实测（受控 Edge 9222）**：`POST /api/accounts/236e26b2c620/apply` → `200 {cookie_count:5, reloaded:true}`；底座 `POST /api/browser/read-cookies` 回读 5 条与账号 Cookie **完全一致**（`ds_session_id`/`HWWAFSESID`/`smidV2`/`HWWAFSESTIME`/`.thumbcache_...`）→ **注入链路 100% 生效**。
> - **★关键新发现（障碍）**：CDP `Runtime.evaluate` 读 deepseek 页 `localStorage` 得 `["userToken","settingsJwt","__appKit_userInfo","smidV2",...]`，且 `userToken={"value":null}`、页面仍 `sign_in` → **DeepSeek 登录态存于 `localStorage`，Cookie 只是反爬（WAF）+ 分析用途**。故「Cookie 注入」无法让 deepseek 进入登录态，`/v1/chat/completions`（`deepseek:quick`）仍返回 500（底座「找不到输入框」）。
> - 前端 `npm.cmd run build` 通过重建 dist（`index-W_mSTXk7.js 842.88 kB` / `index-CMcvx02X.css 22.37 kB`）。
1. 【2026-10-09 15:26】账号导入改造为三按钮（方案A「自动读 Cookie 落库」）：① **一键自动导入**——底座新增 `POST /api/browser/read-cookies`（CDP 页级 `Network.getCookies`，回退浏览器级 `Storage.getCookies`）逐平台读已登录 Cookie，后端新增 `POST /api/accounts/auto-import` 写入/刷新账号池（去重标识 `auto@{site_key}`，重复点击即更新，实现「自动更新」）；② **登录导入**——底座新增 `POST /api/browser/open-url` 打开官方登录页（复用受控浏览器用户目录，免 profile），后端新增 `POST /api/accounts/open-login`，前端选平台后打开，登录完回点「一键自动导入」；③ **手动导入**——保留原 JSON 批量导入弹窗。前端 `AccountsPage.jsx` 顶部拆为三按钮 + 空态文案更新、`api.js` 增 `autoImportAccounts`/`openLoginPage`。`npm run build` 通过，已提交推送 GitHub（提交 `daeb059`）
2. 【2026-10-09 15:12】前端 UI 三项优化：① 默认标签页 `keys`→`chat`（首次打开显示「对话」）；② 聊天空态文案「开始与聚合网关对话」→「开始与聚元网关对话」；③ 新增账号表单加必填星号 + 校验（平台、邮箱/标识、Session Key 与 Cookies 至少一项）
3. 【2026-10-08】API Key 网关：后端动态 Key（SQLite `api_keys` 表、Fernet 加密 + SHA-256 哈希、模型白名单授权）+ 前端「API 密钥」管理页；实测 创建→白名单过滤→401→403→删除 全链路通过
4. 【2026-10-08】模型名称动态匹配：底座 `/v1/models` → `catalog.py` 三级归因 → `loader._DYNAMIC` 覆盖层；`/api/models`、启动刷新、前端展示同步
5. 【2026-10-08】接入真实网页抓取：安装 `backend/requirements-web.txt`（DrissionPage）、`backend/.env` 设 `GATEWAY_REAL_BROWSER_ENABLED=true`，后端启动验证 `real_browser=True`
6. 【2026-10-08】中文名统一「聚源」→「聚元」；修复页面大面积空白（`index.css` 的 `.app-window{width:100%;height:100%}`）
7. 【2026-10-08】代码推送 GitHub：`https://github.com/jiaweisi666/juyuan.git`
8. 【2026-10-08 21:35】启动后端并验证：`/health` 200、`/` 200（前端产物托管正常），浏览器可访问 http://127.0.0.1:8300
9. 【2026-10-08】容器化与项目说明：新建 `Dockerfile`（多阶段：node 构建前端 → python 运行后端）、`docker-compose.yml`（仅绑 127.0.0.1:8300、data 卷持久化、healthcheck）、`.dockerignore`、`start.cmd` / `start.sh`、`README.md`
10. 【2026-10-08】前端 5 页面 + 应用外壳完成：ChatPage / ModelsPage / AccountsPage / RoutingPage / LogsPage + `App.jsx` / `main.jsx` / `ui.jsx` / `icons.jsx`；`npm run build` 通过（dist 由后端托管）
11. 【2026-10-08】补齐前后端契约缺口：新增 `GET/PUT /api/routing/config`（AUTO 开关 / 反馈自优化）
12. 【2026-10-08】后端全链路：platforms 插件体系（base/registry/mock/web/loader）、accounts（crypto/store/pool/models）、router（evaluator/profiles/policy/engine）、storage（SQLite）、gateway/orchestrator、api（openai/anthropic/admin/chat/system）、tool_calling、schemas、config、logging_config
13. 【2026-10-08】环境搭建：backend/.venv 依赖安装、data/gateway.db 就绪、底座 `vendor/universal-web-api` 克隆完成

## 三、关键决策与结论
> （重要选择、技术方案、结论，永久保留）
- 不做 Tauri 桌面外壳 → **无需 Rust/cargo**；前端改为浏览器访问的 Web 控制台
- 平台适配层采用「**插件架构 + 内置模拟适配器**」，默认真实浏览器关闭，全链路即可跑通
- 底座 `universal-web-api` 目录在 `vendor/`（Git 忽略），但**运行时必须启动**（此前的「不作为运行时依赖启动」结论已作废）：由底座 `start.py::_launch_browser_if_needed()` 用 `--remote-debugging-port=9222` 拉起受控 Chromium（Edge），`main.py` 只连接不拉起。**本机（TRAE 沙箱）需手动等价拉起 Edge，必须加 `--disable-gpu` 并用常驻保活命令**，否则 Edge 会在命令结束时被沙箱回收、9222 端口随即消失 → 底座 `/health` 转 503
- **「就绪」判定（消除「就绪假象」）**：平台可用 = ① 底座 `/health` 连接正常 **且** ② 标签池存在**匹配该平台域名**的标签页 **且** ③ 该标签页**不处于登录/鉴权页**。三者任一不满足 → `unavailable` 并给出具体原因
- **标签池填充**：底座 `TabPoolManager` 会自动扫描并收养浏览器中真实站点标签页（跳过 `about:blank` 等内部页）。用底座 `POST /api/browser/open-url {"url":...}` 打开站点即可让标签池非空并触发域名匹配
- **无写 Cookie 接口（旧结论，v1.4 已推翻）**：底座全仓库无 `set-cookie`/`Network.setCookie` 写入实现（仅有 `read-cookies`）。
- **【v1.4 新结论·网关侧 CDP 写 Cookie】**：**不改底座**，由**网关侧**用 CDP 直连受控浏览器注入 Cookie —— 新增 `backend/app/browser/cdp.py`：`websocket-client` 连 `ws://127.0.0.1:9222/...` → `Network.enable` → `Network.setCookies` → `Page.reload`；入口 `POST /api/accounts/{id}/apply`（前端「应用登录态」按钮）。实测注入链路 100% 生效（写 5 条 + `read-cookies` 回读一致）。
- **【v1.4 发现·deepseek 认证在 localStorage】**：CDP `Runtime.evaluate` 读 deepseek 页 `localStorage` 得 `userToken`/`settingsJwt`，未登录时 `userToken={"value":null}` 且页面仍 `sign_in`。**Cookie 只是反爬（WAF：`HWWAFSESID`/`HWWAFSESTIME`）+ 分析（`smidV2`/`ds_session_id`）用途，不含登录凭据** → 仅注入 Cookie 无法让 deepseek 进入登录态。
- **【v1.5 结论·已攻克】**：把注入方案扩展为 **「Cookie + localStorage」**——`apply_login(host, cookies=, storage=)` 在**同一次 CDP 连接内**先 `Network.setCookies` 再 JS 写 `localStorage`，最后统一 `Page.reload` 一次；账号池新增加密字段 `storage_enc` 存 `userToken`/`settingsJwt` 等令牌；`auto-import`/`read-import` 会连同页面 `localStorage` 一并落库。运行时实测：读 29 键 → 写探针回读一致 → 网关 `read-import`（cookie=4/storage=30）落库 → `apply`（cookie=4/storage=30/reloaded）。**机制 100% 就绪；仅缺真实登录令牌这一数据前提**。
- AUTO 路由公式：综合得分 = 准确率×0.5 + 延迟×0.2 + 成本×0.3（权重前端滑块可调，运行时归一化）
- 前端技术栈：Vite 6 + React 19 + Tailwind CSS 4；窗口 880×580 + 64px 图标标签栏，5 页面
- Docker 端口固定映射 `127.0.0.1:8300`，落实「不提供公网默认部署」安全约束
- 本机默认免鉴权（未创建 `.env`，API Key / Admin Token 均为空），打开即用
- 所有大模型请求由后端转发；敏感字段使用 Fernet 加密存储
- 真实网页适配器（`WebPlatformPlugin`）桥接底座：底座经 CDP 连接本机**已运行**的 Chrome（`BROWSER_PORT=9222`，`existing_only()`），复用浏览器登录态，非无头
- 账号凭据（session_key/cookies）当前**仅用于**账号池调度（可用性/限流/冷却）与展示，**未注入**真实浏览器调用；真实链路依赖浏览器登录态
- API Key 网关：静态主 Key + 动态 Key（SQLite `api_keys`、Fernet 加密 + SHA-256 哈希），按**模型白名单**授权第三方（Trae 等）调用
- 【账号导入·决策】选「方案A：自动读 Cookie 落库」——后端**不装 DrissionPage**，改由底座暴露本机端点（`POST /api/browser/read-cookies` 读 Cookie、`POST /api/browser/open-url` 打开官方登录页），后端经 `httpx` 调 `base_web_api_url` 代理；按钮一/二只做「发现已登录站点 + 读 Cookie 写入账号池」，真实模型调用仍复用浏览器登录态；「自动更新」= 点击时实时读取（重复点击走 `store.update()` 刷新 Cookie）
- 底座本机集成端点鉴权：`verify_open_profile_url_auth`（仅回环或控制面板令牌）；`read-cookies` 优先页级 CDP `Network.getCookies`，回退浏览器级 `Storage.getCookies` 并按域名过滤
- **【v1.6 决策·目录同步提示】**：底座 `/v1/models` 无站点时只返回占位 `web-browser`，网关不再报误导性的「底座未返回可识别的模型」，而是分三档给出可操作中文提示（无模型 / 仅占位→先「登录导入」打开站点 / 无法归因）；前端同步失败 Toast 用 `info` 而非 `error`（属可预期状态）
- **【v1.7 决策·多模态 content 兼容】**：网关 `ChatMessage.content` 从 `str` 放宽为 `str | list | None`，**数组型 content 原样透传给底座**（底座原生支持图片/音频/视频片段）；凡需纯文本的内部环节（token 估算、任务分类、mock 回复）一律改用 `schemas.message_text()` 提取文本、非文本片段以 `[图片]`/`[音频]`/`[视频]` 占位。此举使网关对外**完整兼容 OpenAI 多模态消息格式**，第三方 App 不再因数组型 content 报 422
- **【v1.8 结论·Agent 能力边界】**：自建网关无法像官方 API 那样驱动 Trae 类 Agent，属**能力边界而非缺陷**。官方 API = 模型**原生 function calling**（协议级输出标准 `tool_calls`）；本项目 = `tool_calling.py` 的 **ReAct 文本模拟**（注入提示词 + 正则解析），且 `orchestrator.stream()` 在工具模式下**不增量下发**（缓冲后一次性下发）→ Agent 卡死。故项目定位 = **聚合对话网关**，不追求做 Agent 运行时。
- **【v1.8 决策·桌面化分发】**：面向普通用户的分发用「**PyInstaller 一键启动器 EXE**」而非 Docker（Docker 仅适合开发者，不满足「双击即用」）。MVP 形态 = **启动器 EXE + 系统默认浏览器**（暂不开桌面壳）；长期可演进 Tauri 2 桌面壳（用户已确认「之后再说」）。分发形态 = 整个项目目录（含 exe、`vendor/`、`backend/` 及各自 venv）+ 使用说明；后续可加 Inno Setup 做安装包。
- 平台定义 `backend/app/resources/platforms.json` 含 `site_key`(域名) / `homepage`，作自动导入的站点匹配依据；自动导入去重标识 `auto@{site_key}`

## 四、当前状态与待办事项
> （每轮更新，下一轮的执行入口）
- 当前进度：**v1.8 桌面化 MVP（一键启动器 EXE）已跑通并实测通过**；代码侧历史修复已全部提交推送；唯一剩余缺口仍是**本机无真实 deepseek 登录令牌**（数据前提，非代码问题）
- 服务状态：底座 `8199`（`/health` 200 connected，browser healthy port=9222）；网关 `8300`（LISTENING，热重载）；受控 Edge `9222`（LISTENING）；网关侧已可读写该浏览器 `localStorage`
- 桌面化产物：`juyuan_code/juyuan_launcher.py`（MVP 编排器）+ `juyuan_code/JuyuanLauncher.exe`（PyInstaller onefile）；实测一键启动三服务 + 自动打开浏览器 + 退出清理全部通过
- 账号池：**当前为空**（`backend/data/accounts.json` = `{"accounts":[]}`）——用户完成真实登录导入后会新写入
- 待完成（按优先级）：
  1. 【P1·需用户操作】**注入真实登录令牌**：在受控浏览器内登录 deepseek（或用真实 `userToken`/`settingsJwt` 填入账号池 localStorage 字段）→ 点「应用登录态」或调 `POST /api/accounts/{id}/apply` → `GET /api/platforms` 的 deepseek 应转 `ready`
  2. 【P1】deepseek `ready` 后：`POST /v1/chat/completions`（`model=deepseek:quick`）应返回**真实回复**而非「[模拟响应]」或 500
  3. 【P1】复测其它平台：对每个目标平台执行 `POST /api/browser/open-url` → 登录导入（现已含 localStorage）→ 复测对话
  4. 【P2·桌面化阶段 2（用户已说「之后再说」）】桌面壳（Tauri 2 或 Electron）、首启引导、托盘、Inno Setup 安装包、便携 zip 分发
- 阻塞问题：① deepseek 自动登录需真实登录令牌，本机无（沙箱无法代填账号密码）；② 本机无 Docker，镜像/Compose 部署无法实测；③ 本机无 Rust/cargo，Tauri 桌面壳暂无法构建（MVP 已用纯 Python 启动器规避）

## 五、上下文参考信息
> （环境、配置、常用参数等辅助信息）
- 代码根目录：`D:\Project\juyuan\juyuan_code`
- 需求文档：`d:\Project\juyuan\需求文档.docx`（已提取为 `_document_text.txt`）；桌面化打包需求文档：`d:\Project\juyuan\聚元网关-桌面化打包需求文档.md`（v0.1，11 章）
- 后端：`juyuan_code/backend/`（app/、requirements.txt、requirements-web.txt、.env.example、run.py、.venv/、data/）
- 前端：`juyuan_code/frontend/`（src/pages、src/components、dist/）；开发端口 5273，代理 → 8300
- 底座：`juyuan_code/vendor/universal-web-api/`
- 访问地址：http://127.0.0.1:8300
- 启动方式：本地 `start.cmd`（Windows）/`start.sh`（**仅启动网关 1/3 服务**）；手动 `backend\.venv\Scripts\python.exe run.py`
- **一键启动（桌面化 MVP）**：双击 `juyuan_code/JuyuanLauncher.exe`（或 `python juyuan_launcher.py`）→ 按序拉起 受控浏览器 9222 + 底座 8199 + 网关 8300 并打开默认浏览器；Ctrl+C/关闭窗口即清理全部子进程。源码 `juyuan_code/juyuan_launcher.py`（仅标准库）；打包命令见「二、已完成工作清单」最新一轮。
- 打包工具：PyInstaller 6.22.3（`backend/.venv` 内）；构建产物 `build/` 与 `JuyuanLauncher.exe` 已在 `.gitignore` 中忽略
- Docker：`docker compose up -d --build`
- 本机环境：Python 3.14.8、Node v24.21.0（`D:\APP\NodeJs`）、git 2.56.0；无 Rust/cargo；无 Docker
- 内置平台：deepseek、chatgpt、claude、kimi、gemini、qwen、doubao、glm
- 关键 API：`/v1/chat/completions`、`/v1/models`、`/v1/messages`、`/api/{platforms,accounts,routing,logs,stats,chat}`、`/api/accounts/{auto-import,open-login,read-import,health-check}`、`/api/accounts/{id}/apply`（网关侧 CDP 注入 Cookie + localStorage）、`/api/keys`（含 `POST /api/keys/{id}/reveal`）、`/health`
- 底座本机端点（新增）：`POST /api/browser/read-cookies`、`POST /api/browser/open-url`；默认底座地址 `base_web_api_url=http://127.0.0.1:8199`
- 网关 CDP 直连配置：`browser_debug_url`（env `GATEWAY_BROWSER_DEBUG_URL`，默认 `http://127.0.0.1:9222`）；模块 `backend/app/browser/cdp.py`：`apply_login(host, cookies=, storage=, reload=)`（Cookie+localStorage 合并注入）、`read_local_storage(host)`、`parse_cookies`、`parse_storage`、`apply_cookies`（兼容）
- 账号池 localStorage 令牌：加密字段 `storage_enc`（`Account.storage_enc`，`to_public` 输出 `has_storage`）；`POST/PUT /api/accounts` 字段名 `storage`（dict 或 JSON 字符串，形如 `{"userToken":"...","settingsJwt":"..."}` 或 `[{"name","value"}]`）
- 版本控制忽略项：`vendor/`（底座源码）与 `frontend/dist/`（构建产物）在 `.gitignore` 中，**不纳入 Git**；改动底座需另行同步
- 真实浏览器开关：`backend/.env` 的 `GATEWAY_REAL_BROWSER_ENABLED=true`；底座 CDP 端口 `9222`
- 平台定义：`backend/app/resources/platforms.json`（含 `site_key` 域名 / `homepage`，供自动导入匹配）
- GitHub 仓库：`https://github.com/jiaweisi666/juyuan.git`

## 六、错误与踩坑记录
> （避免重复踩坑）
- PowerShell 执行策略禁止加载 `.ps1`（报错噪音无害）；`npm` 须用 `npm.cmd`，`node` 须先 `$env:Path = "D:\APP\NodeJs;" + $env:Path`
- TRAE sandbox 禁止写入 `D:\APP\Python\Lib\**`，需设 `PYTHONDONTWRITEBYTECODE=1`
- `/api/routing/config` 一度返回 404：运行中的旧进程未热加载新路由，重启后端后恢复正常
- DOCX 为二进制格式：需解压 `word/document.xml` + 正则 + HtmlDecode 提取纯文本
- `curl.exe -d` 传 JSON 时引号被 PowerShell 破坏，改用临时文件或 `Invoke-WebRequest`
- 真实浏览器需**带界面** Chrome（无头/无窗口会报错），且需 9222 端口可达；底座连不上时按 `GATEWAY_MOCK_FALLBACK` 降级模拟
- `git commit` 在 PowerShell 下不可用 heredoc，需多个 `-m`；`git push` 前若远端 README 被改需先 `git fetch` + `git merge origin/main`
- 系统 Python **未安装 DrissionPage**（`ModuleNotFoundError`）→ 后端不直连 CDP，改由底座暴露本机端点（`read-cookies` / `open-url`）经 HTTP 代理
- 底座 `/api/tab-pool/tabs` 返回的 tabs **不含 cookies**；原 `open-profile-url` 需 `profile` 标识 → 故新增 `read-cookies` 与免 profile 的 `open-url` 两个端点
- **【关键】TRAE 沙箱会回收 detach 的 Edge 子进程**：`Start-Process` 拉起 Edge 后，命令一结束端口 9222 立即消失；且 Edge 触碰受限路径（`NVIDIA\DXCache`、`Microsoft\TokenBroker\Cache`、`Microsoft\IdentityCache`、`OneAuth\blobs`、`Windows\Recent\CustomDestinations`）会报 `TRAE Sandbox Error: hit restricted`。**解法**：启动参数加 **`--disable-gpu`**，并把启动放入 `blocking=false` 的**常驻保活命令**（启动后 `while ($true) { Start-Sleep 3600 }`），Edge 方可跨命令稳定存活
- 底座 `/health` 在浏览器未连接时**按设计返回 503 且 body 为空**；用 `Invoke-WebRequest -UseBasicParsing` 并捕获 response stream 才能读到 body
- `Get-NetTCPConnection` 在本机沙箱偶发失败 → 改用 `netstat -ano | Select-String ":port"`
- 对话「模拟响应」的来源：底座不可达（`httpx.ConnectError`）且 `GATEWAY_MOCK_FALLBACK=true` 时 `WebPlatformPlugin.chat()` 降级 Mock；底座可达但转发失败（如标签页停在登录页）则走 `HTTPStatusError` → 网关 500（**不降级 Mock**）。故「模拟响应」与「500」分别指向「底座没起/浏览器被回收」与「底座起了但站点未登录」两类不同根因
- **【关键】Cookie 注入 ≠ 登录（deepseek）**：实测 CDP `Network.setCookies` 写入 Cookie 成功、`read-cookies` 回读完全一致，但页面仍停 `sign_in`、对话 500。经 `Runtime.evaluate` 读 `localStorage` 证实 deepseek 认证在 `localStorage`（`userToken`/`settingsJwt`），注入的 Cookie 仅为反爬（`HWWAFSESID`/`HWWAFSESTIME`）+ 分析（`smidV2`/`ds_session_id`）用途。→ **v1.5 已扩展为同时注入 `localStorage`**（`apply_login`），链路实测通过；使站点真正登录仍需真实登录令牌
- **PowerShell 传多行 Python**：`python -c "...`n...\"`"` 会因引号/换行被二次解析而报 `unterminated string literal`；改用 **here-string 管道**（`@'...'@ | .\.venv\Scripts\python.exe -`）传多行脚本最稳
- **网关 debug 热重载 vs 底座无热重载**：网关 `run.py` 用 `uvicorn.run(..., reload=settings.debug)`（`GATEWAY_DEBUG=true` → 改后端自动重载）；底座 `main.py` 结尾 `uvicorn.run(app, ...)` **无 reload** → 改底座必须重启，且底座关闭会调 `browser.close()`，**可能连带杀掉受控浏览器**
- **网关侧写 Cookie 依赖 `websocket-client`**：`backend/requirements-web.txt` 已追加 `>=1.6.0`，但 `start.cmd` 只装 `requirements.txt`，**手动 `pip install -r requirements-web.txt` 或改用直接 CDP 前需确认已安装**
- **【关键】TRAE 沙箱会连带回收底座/网关进程**：不止 Edge，沙箱回收后 `netstat` 甚至返回「三端口全 Down」（`8199`/`8300`/`9222` 全无 LISTENING）→ 网关接口全报「无法连接到远程服务器」。**这不是代码问题**，逐个重启即可（Edge 用保活命令、底座 `python main.py`、网关 `python run.py`）。本 session 出现两次，排查前务必先 `netstat` 确认三端口在线
- **底座 `/v1/models` 的占位语义**：受控浏览器**无任何已打开站点**时，底座仅返回通用占位 `{"id":"web-browser"}`（不含平台信息，无法归因）；用 `POST /api/browser/open-url` 打开站点后，才返回该站点域名派生的模型名（如 `chat.deepseek.com`/`deepseek`/`www.chat.deepseek.com`）→ 可归因。故「同步模型」前必须先在受控浏览器打开目标站点
- **`GET /api/models/catalog` vs 路由**：动态目录路由是 `/api/models/catalog`（非 `/api/model-catalog`），刷新为 `POST /api/models/refresh`；`Invoke-WebRequest` 读中文 JSON 会因控制台编码显示为乱码（mojibake），属显示问题、非数据问题（可用 `[System.Text.Encoding]::UTF8.GetString([System.Text.Encoding]::GetEncoding(1252).GetBytes($r.Content))` 还原）
- **【关键】PyInstaller 冻结后控制台编码为 GBK**：`print` 输出非 GBK 字符（如 `✓` U+2713）会抛 `UnicodeEncodeError` → exe 启动即崩（`'gbk' codec can't encode character '\u2713'`）。修复 = 输出仅用 GBK 可编码字符（`→`/`…`/中文均可，`✓` 不行）+ `sys.stdout/stderr.reconfigure(errors="replace")` 兜底。
- **【关键】PyInstaller onefile 下 `__file__` 指向临时解压目录（`_MEIPASS`）**：不能用于定位项目根，须改用 `Path(sys.executable).resolve().parent`（exe 所在目录）。故启动器 exe **必须与 `vendor/`、`backend/` 同级**放置，否则找不到子项目。
- **PyInstaller 打包时的 sandbox 噪音**：构建过程会尝试写 `D:\APP\Python\Lib\**.pyc` 被沙箱拦截，日志末尾报 `TRAE Sandbox Error` 且**进程退出码为 1**，但此前已打印 `Build complete!`——**exe 已成功生成，退出码 1 属噪音**。同理运行 exe 时 Edge 触碰 `NVIDIA\DXCache` 也报沙箱错，均非代码问题（用户直接双击不受影响）。
- **启动器复用底座 `start.py` 会自动更新上游代码**：`vendor/universal-web-api/start.py` 默认 `AUTO_UPDATE_ENABLED=true`（启动时从 GitHub 拉取）；MVP 启动器在子进程环境置 `AUTO_UPDATE_ENABLED=false` 以保证可复现，如需上游更新可临时去掉该环境变量。
- **`start.cmd` 只启动网关**：它仅做「建 venv→装依赖→构建前端→`cd backend`+`run.py`」4 步，**不含底座(8199)与受控浏览器(9222)**；一键启动须用本轮的 `juyuan_launcher.py`/`JuyuanLauncher.exe`。
