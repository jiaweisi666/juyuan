"""
juyuan_launcher.py - 聚元网关 MVP 一键启动编排器（Windows）

用途：
    双击 exe（或 `python juyuan_launcher.py`）后，在本地按序拉起整套服务：

    1) 底座 + 受控浏览器：复用 vendor/universal-web-api/start.py
       - 受控 Chromium（Edge/Chrome）DevTools(CDP) 监听  127.0.0.1:9222
       - 底座 Web2API 服务监听                            127.0.0.1:8199
    2) 网关：backend/run.py
       - 聚合网关监听                                     127.0.0.1:8300（并托管前端 dist）

    三服务就绪后自动打开系统默认浏览器访问网关首页；
    按 Ctrl+C 退出并清理本次启动的所有子进程。

设计原则：MVP 最省事路线 —— 尽量复用各子项目既有启动逻辑，不重写浏览器探测等复杂分支。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包后：以 exe 所在目录作为项目根（exe 与 vendor/、backend/ 同级）
    PROJECT_DIR = Path(sys.executable).resolve().parent
else:
    PROJECT_DIR = Path(__file__).resolve().parent
# 打包为 exe 后，Windows 控制台默认编码为 GBK；对无法编码的字符做安全替换，避免打印崩溃
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass

VENDOR_DIR = PROJECT_DIR / "vendor" / "universal-web-api"
VENDOR_PY = VENDOR_DIR / "venv" / "Scripts" / "python.exe"
BACKEND_DIR = PROJECT_DIR / "backend"
BACKEND_PY = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"

VENDOR_HEALTH = "http://127.0.0.1:8199/health"
BROWSER_HEALTH = "http://127.0.0.1:9222/json/version"
GATEWAY_HEALTH = "http://127.0.0.1:8300/health"
GATEWAY_HOME = "http://127.0.0.1:8300"

# 子进程句柄，(名称, Popen)，退出时逆序清理
_children: list[tuple[str, subprocess.Popen]] = []


def _log(msg: str) -> None:
    print(f"[聚元启动器] {msg}", flush=True)


def _http_ok(url: str, timeout: float = 1.5) -> bool:
    """探测 HTTP 端点是否可响应（忽略代理，避免系统代理干扰本地回环）。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def _wait_http(name: str, url: str, timeout: float, interval: float = 1.0) -> None:
    _log(f"等待 {name} 就绪 → {url}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _http_ok(url):
            _log(f"{name} 已就绪 [OK]")
            return
        # 若子进程已提前退出，无需再等
        for child_name, proc in _children:
            if proc.poll() is not None:
                raise RuntimeError(f"{child_name} 进程意外退出（退出码 {proc.returncode}）")
        time.sleep(interval)
    raise RuntimeError(f"{name} 在 {timeout:.0f}s 内未就绪：{url}")


def _spawn(name: str, args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
    _log(f"启动 {name} …")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(args, cwd=str(cwd), env=env, creationflags=creationflags)
    _children.append((name, proc))
    return proc


def _kill_tree(proc: subprocess.Popen) -> None:
    """终止子进程及其进程树（Windows 用 taskkill /T）。"""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
    else:  # pragma: no cover - MVP 仅面向 Windows
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()


def _cleanup() -> None:
    _log("正在关闭本次启动的服务 …")
    for name, proc in reversed(_children):
        _kill_tree(proc)
        _log(f"已关闭 {name}")
    _children.clear()


def _preflight() -> None:
    if not VENDOR_PY.exists():
        raise RuntimeError(
            f"未找到底座虚拟环境：{VENDOR_PY}\n"
            "请先在 vendor/universal-web-api 下运行一次 start.bat 完成初始化。"
        )
    if not BACKEND_PY.exists():
        raise RuntimeError(
            f"未找到网关虚拟环境：{BACKEND_PY}\n"
            "请先在项目根目录运行一次 start.cmd 完成初始化。"
        )


def main() -> int:
    print("=" * 60)
    print("  聚元网关 - MVP 一键启动")
    print("=" * 60)

    _preflight()

    # 1) 底座 + 受控浏览器（复用 start.py：负责浏览器探测、依赖检查、服务循环）
    vendor_env = os.environ.copy()
    vendor_env["PYTHONUTF8"] = "1"
    # MVP 阶段关闭底座自动更新，避免启动时静默拉取上游代码导致不可复现
    vendor_env["AUTO_UPDATE_ENABLED"] = "false"
    _spawn("底座+受控浏览器", [str(VENDOR_PY), "start.py"], VENDOR_DIR, env=vendor_env)

    # 先等受控浏览器 CDP 就绪（底座会先拉起浏览器再起服务）
    _wait_http("受控浏览器", BROWSER_HEALTH, timeout=180)
    _wait_http("底座服务", VENDOR_HEALTH, timeout=300)

    # 2) 网关（底座就绪后再起，便于网关启动期同步动态模型目录）
    _spawn("聚合网关", [str(BACKEND_PY), "run.py"], BACKEND_DIR)
    _wait_http("聚合网关", GATEWAY_HEALTH, timeout=180)

    # 3) 打开系统默认浏览器
    _log(f"打开管理面板：{GATEWAY_HOME}")
    try:
        webbrowser.open(GATEWAY_HOME)
    except Exception as exc:  # noqa: BLE001
        _log(f"自动打开浏览器失败，请手动访问 {GATEWAY_HOME}（{exc}）")

    _log("=" * 60)
    _log("所有服务已启动。按 Ctrl+C 退出并清理进程。")
    _log("=" * 60)

    # 4) 常驻守护：任一子进程退出即整体退出
    try:
        while True:
            time.sleep(1)
            for name, proc in _children:
                if proc.poll() is not None:
                    _log(f"{name} 已退出（退出码 {proc.returncode}），停止其余服务。")
                    return 1
    except KeyboardInterrupt:
        _log("\n收到退出信号。")
        return 0
    finally:
        _cleanup()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        _log(f"启动失败：{exc}")
        _cleanup()
        raise SystemExit(1)
