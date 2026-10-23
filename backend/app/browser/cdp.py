"""
cdp.py - 通过 Chrome DevTools Protocol 直接控制受控浏览器。

背景：底座（universal-web-api）只暴露了「读取」登录态 Cookie 的接口，没有
「写入」。为避免修改底座代码 / 重启底座（底座关闭会连带关闭受控浏览器），
网关侧直接连接受控浏览器的 DevTools 端口（默认 127.0.0.1:9222），用
`Network.setCookies` 把账号池中已导入的 Cookie 注入浏览器并刷新页面，
从而让底座驱动的那套浏览器真正处于登录态。

仅用于本机回环，不接受外部输入的可执行指令（只发固定的 CDP 方法）。
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger(__name__)

# Network.setCookies 允许的字段（过滤掉 size/session/来源等只读字段，避免报错）
_COOKIE_FIELDS = ("domain", "path", "secure", "httpOnly", "sameSite", "expires", "url", "priority")


class CDPError(RuntimeError):
    """CDP 注入失败（浏览器未连接、未找到标签页、Cookie 非法等）。"""


def _debug_base() -> str:
    return (get_settings().browser_debug_url or "http://127.0.0.1:9222").strip().rstrip("/")


def _host_of(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"http://{value}"
    return str(urlparse(value).hostname or "").strip().lower()


def _host_matches(target_url: str, host: str) -> bool:
    """受控浏览器标签页 URL 是否属于目标站点。"""
    target_host = _host_of(target_url)
    if not host or not target_host:
        return False
    return (
        target_host == host
        or target_host.endswith(f".{host}")
        or host.endswith(f".{target_host}")
    )


def list_pages() -> list[dict[str, Any]]:
    """列出受控浏览器中所有普通页面标签（type == page）。"""
    url = f"{_debug_base()}/json/list"
    try:
        with httpx.Client(timeout=httpx.Timeout(5.0), trust_env=False) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise CDPError(f"无法连接受控浏览器 DevTools（{url}）：{exc}") from exc
    except ValueError as exc:
        raise CDPError("受控浏览器 DevTools 返回非法数据") from exc
    return [item for item in (data or []) if isinstance(item, dict) and item.get("type") == "page"]


def find_page(host: str) -> dict[str, Any] | None:
    """查找匹配 `host` 的页面标签（优先精确匹配域名）。"""
    pages = list_pages()
    for page in pages:
        if _host_matches(str(page.get("url") or ""), host):
            return page
    return None


def _sanitize_cookie(cookie: dict[str, Any], host: str) -> dict[str, Any] | None:
    name = str(cookie.get("name") or "").strip()
    if not name or cookie.get("value") is None:
        return None
    out: dict[str, Any] = {"name": name, "value": str(cookie["value"])}
    for key in ("domain", "path", "url"):
        value = cookie.get(key)
        if value:
            out[key] = str(value)
    for key in ("secure", "httpOnly"):
        if cookie.get(key) is not None:
            out[key] = bool(cookie[key])
    if cookie.get("sameSite") in {"Strict", "Lax", "None"}:
        out["sameSite"] = cookie["sameSite"]
    if cookie.get("priority") in {"Low", "Medium", "High"}:
        out["priority"] = cookie["priority"]
    expires = cookie.get("expires")
    if isinstance(expires, (int, float)) and expires > 0:
        out["expires"] = float(expires)
    # CDP 要求每个 cookie 至少有 domain 或 url；原始 Cookie 串缺域名时补上目标站点
    if "domain" not in out and "url" not in out:
        out["url"] = f"https://{host}/" if host else ""
        if not out["url"]:
            return None
    return {k: v for k, v in out.items() if k in _COOKIE_FIELDS or k in ("name", "value")}


def parse_cookies(raw: Any, host: str) -> list[dict[str, Any]]:
    """把账号池中的 Cookie（JSON 数组 / JSON 对象 / 原始 Cookie 串）解析为 CDP 格式。"""
    host = str(host or "").strip()
    items: list[dict[str, Any]] = []

    def _from_dict(mapping: dict[str, Any]) -> list[dict[str, Any]]:
        nested = mapping.get("cookies")
        if isinstance(nested, list):
            return [c for c in nested if isinstance(c, dict)]
        return [{"name": k, "value": v} for k, v in mapping.items()]

    if isinstance(raw, list):
        items = [c for c in raw if isinstance(c, dict)]
    elif isinstance(raw, dict):
        items = _from_dict(raw)
    elif isinstance(raw, str):
        text = raw.strip()
        if text:
            parsed: Any = None
            if text[0] in "[{":
                try:
                    parsed = json.loads(text)
                except (ValueError, TypeError):
                    parsed = None
            if isinstance(parsed, list):
                items = [c for c in parsed if isinstance(c, dict)]
            elif isinstance(parsed, dict):
                items = _from_dict(parsed)
            else:
                # 原始 Cookie 头字符串：name=value; name2=value2
                for part in text.split(";"):
                    piece = part.strip()
                    if not piece or "=" not in piece:
                        continue
                    name, value = piece.split("=", 1)
                    items.append({"name": name.strip(), "value": value.strip()})

    result: list[dict[str, Any]] = []
    for item in items:
        clean = _sanitize_cookie(item, host)
        if clean is not None:
            result.append(clean)
    return result


def parse_storage(raw: Any) -> dict[str, str]:
    """把账号池中的 localStorage 解析为 {key: value} 字典。

    支持 JSON 对象字符串 / dict / [{"name"|"key","value"}] 列表。无法解析时返回空字典。
    """
    parsed: Any = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text or text[0] not in "{[":
            return {}
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return {}

    if isinstance(parsed, list):
        items: list[tuple[str, Any]] = []
        for item in parsed:
            if isinstance(item, dict):
                key = item.get("name", item.get("key"))
                if key is not None and item.get("value") is not None:
                    items.append((str(key), item["value"]))
        return {k: str(v) for k, v in items}

    if isinstance(parsed, dict):
        nested = parsed.get("storage", parsed.get("localStorage"))
        if isinstance(nested, (dict, list)):
            return parse_storage(nested)
        return {
            str(k): str(v)
            for k, v in parsed.items()
            if isinstance(k, str) and v is not None
        }
    return {}


def _call(ws: Any, msg_id: int, method: str, params: dict[str, Any] | None = None, timeout: float = 10.0) -> Any:
    payload: dict[str, Any] = {"id": msg_id, "method": method}
    if params is not None:
        payload["params"] = params
    ws.send(json.dumps(payload))
    deadline = time.time() + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise CDPError(f"CDP {method} 超时")
        ws.settimeout(remaining)
        raw = ws.recv()
        try:
            message = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(message, dict) or message.get("id") != msg_id:
            continue  # 其它响应或事件
        if message.get("error"):
            raise CDPError(f"CDP {method} 失败：{message['error']}")
        return message.get("result")


def _evaluate(ws: Any, msg_id: int, expression: str, timeout: float) -> Any:
    """在页面上下文执行 JS，返回其求值结果（returnByValue）。"""
    result = _call(
        ws,
        msg_id,
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": False},
        timeout=timeout,
    )
    if isinstance(result, dict) and result.get("exceptionDetails"):
        detail = result["exceptionDetails"].get("text") or "JS 执行异常"
        raise CDPError(f"页面脚本执行失败：{detail}")
    if isinstance(result, dict):
        return result.get("result", {}).get("value")
    return None


def _wait_page_ready(ws: Any, msg_id: int, host: str, timeout: float = 15.0) -> tuple[int, bool]:
    """等待标签页真正完成导航且当前文档可访问 localStorage。

    新开的标签页在导航完成前 `document.readyState` 仍为 loading/blank，
    此时写 localStorage 会抛 SecurityError（Access is denied），因此先轮询等待。
    返回 (最新消息 id, 是否就绪)。
    """
    deadline = time.time() + max(1.0, timeout)
    expression = (
        "(function(){try{return location.href+'|'+document.readyState+'|'+(typeof localStorage);}"
        "catch(e){return 'ERR:'+e;}})()"
    )
    while time.time() < deadline:
        msg_id += 1
        try:
            state = _evaluate(ws, msg_id, expression, timeout=2.0)
        except CDPError:
            state = None
        if isinstance(state, str) and not state.startswith("ERR:"):
            parts = state.split("|")
            if len(parts) >= 3 and parts[1] == "complete" and parts[2] == "object":
                current = _host_of(parts[0])
                if not host or current == host or current.endswith(f".{host}") or host.endswith(f".{current}"):
                    return msg_id, True
        time.sleep(0.25)
    return msg_id, False


def apply_login(
    host: str,
    *,
    cookies: Any = None,
    storage: Any = None,
    reload: bool = True,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """把登录态（Cookie + localStorage）注入受控浏览器中匹配 `host` 的标签页并刷新。

    DeepSeek 等站点的登录态存放在 localStorage（userToken/settingsJwt）而非 Cookie，
    因此同时支持注入 localStorage，二者可在一次连接内完成、只刷新一次页面。
    返回注入结果（host / 注入条数 / 命中标签页 id）。失败抛 CDPError。
    """
    host = str(host or "").strip().lower()
    if not host:
        raise CDPError("目标站点域名为空")

    cookie_params = parse_cookies(cookies, host) if cookies else []
    storage_items = parse_storage(storage) if storage else {}
    if not cookie_params and not storage_items:
        raise CDPError("未解析到有效登录态（Cookie 与 localStorage 均为空）")

    page = find_page(host)
    if page is None:
        raise CDPError(f"受控浏览器中未找到 {host} 的标签页，请先点击「登录导入」打开该站点")
    ws_url = str(page.get("webSocketDebuggerUrl") or "").strip()
    if not ws_url:
        raise CDPError("受控浏览器标签页未提供 CDP 调试地址")

    import websocket  # websocket-client（随 requirements-web 安装）

    try:
        ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
    except Exception as exc:  # noqa: BLE001
        raise CDPError(f"连接受控浏览器标签页失败：{exc}") from exc

    msg_id = 0
    try:
        # Page/Runtime 只启用一次；后续等待页面就绪、写 localStorage、刷新都复用
        try:
            msg_id += 1
            _call(ws, msg_id, "Page.enable", timeout=timeout)
        except CDPError:
            pass
        msg_id += 1
        _call(ws, msg_id, "Runtime.enable", timeout=timeout)

        if cookie_params:
            msg_id += 1
            _call(ws, msg_id, "Network.enable", timeout=timeout)
            msg_id += 1
            _call(ws, msg_id, "Network.setCookies", {"cookies": cookie_params}, timeout=timeout)

        if storage_items:
            msg_id, ready = _wait_page_ready(ws, msg_id, host, timeout=max(timeout, 15.0))
            if not ready:
                # 标签页可能仍停在 about:blank / 导航中：主动导航到站点后再等一次
                try:
                    msg_id += 1
                    _call(ws, msg_id, "Page.navigate", {"url": f"https://{host}/"}, timeout=timeout)
                except CDPError as exc:
                    logger.warning("导航 %s 标签页失败：%s", host, exc)
                msg_id, ready = _wait_page_ready(ws, msg_id, host, timeout=max(timeout, 15.0))
            if not ready:
                raise CDPError(f"{host} 标签页尚未加载完成，请稍后重试（登录态未写入）")

            payload = json.dumps(storage_items, ensure_ascii=False)
            expression = (
                "(function(){try{var d="
                + payload
                + ";for(var k in d){if(Object.prototype.hasOwnProperty.call(d,k))"
                + "{localStorage.setItem(k,d[k]);}}return true;}catch(e){return 'ERR:'+e;}})()"
            )
            last_error = ""
            for _ in range(12):
                msg_id += 1
                try:
                    outcome = _evaluate(ws, msg_id, expression, timeout)
                except CDPError as exc:
                    outcome = f"ERR:{exc}"
                if outcome is True:
                    last_error = ""
                    break
                last_error = str(outcome)
                time.sleep(0.5)
            if last_error:
                raise CDPError(f"写入 localStorage 失败：{last_error[4:] if last_error.startswith('ERR:') else last_error}")
        if reload:
            try:
                msg_id += 1
                _call(ws, msg_id, "Page.reload", {"ignoreCache": True}, timeout=timeout)
            except CDPError as exc:
                logger.warning("刷新 %s 标签页失败（登录态已注入）：%s", host, exc)
    finally:
        try:
            ws.close()
        except Exception:  # noqa: BLE001
            pass

    logger.info(
        "已向受控浏览器注入登录态（host=%s, cookies=%d, storage=%d, target=%s）",
        host,
        len(cookie_params),
        len(storage_items),
        page.get("id"),
    )
    return {
        "host": host,
        "cookie_count": len(cookie_params),
        "storage_count": len(storage_items),
        "reloaded": bool(reload),
        "target_id": str(page.get("id") or ""),
    }


def apply_cookies(host: str, cookies: Any, *, reload: bool = True, timeout: float = 10.0) -> dict[str, Any]:
    """仅注入 Cookie（`apply_login` 的兼容入口）。"""
    return apply_login(host, cookies=cookies, reload=reload, timeout=timeout)


def read_local_storage(host: str, *, timeout: float = 10.0) -> dict[str, str]:
    """读取受控浏览器中匹配 `host` 的标签页 localStorage（未找到标签页时返回空）。"""
    host = str(host or "").strip().lower()
    if not host:
        return {}
    page = find_page(host)
    if page is None:
        return {}
    ws_url = str(page.get("webSocketDebuggerUrl") or "").strip()
    if not ws_url:
        return {}

    import websocket

    try:
        ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
    except Exception as exc:  # noqa: BLE001
        raise CDPError(f"连接受控浏览器标签页失败：{exc}") from exc

    try:
        _call(ws, 1, "Runtime.enable", timeout=timeout)
        expression = (
            "(function(){try{var o={};for(var i=0;i<localStorage.length;i++)"
            + "{var k=localStorage.key(i);o[k]=localStorage.getItem(k);}return o;}"
            + "catch(e){return {};}})()"
        )
        value = _evaluate(ws, 2, expression, timeout)
    finally:
        try:
            ws.close()
        except Exception:  # noqa: BLE001
            pass

    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if v is not None}
    return {}
