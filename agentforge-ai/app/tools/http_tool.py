"""HTTP 自定义工具执行器（工具定义开发文档 v3.0 §7 阶段二）。

- URL / query / headers / body 模板渲染（{param} 占位符替换为 LLM 入参）
- 认证注入：api_key（自定义头）/ bearer / basic
- httpx 统一超时、响应体大小上限（1MB）、非 2xx 转失败文本（不抛异常）
- SSRF 防护：默认拒绝内网/保留地址段（IP 段校验 + DNS 解析后二次校验，可配置开关）
"""
import base64
import ipaddress
import json
import logging
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
_TEMPLATE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_template(value: Any, params: dict) -> Any:
    """渲染模板：字符串中的 {param} 替换为入参值；其余类型原样返回。

    参数缺失时替换为空串（交由目标端报错，保持可读性）；JSON 标量参数转为字符串。
    """
    if isinstance(value, str):
        def _sub(match: "re.Match[str]") -> str:
            key = match.group(1)
            param = params.get(key)
            if param is None:
                return ""
            return str(param) if not isinstance(param, (dict, list)) else json.dumps(
                param, ensure_ascii=False)
        return _TEMPLATE.sub(_sub, value)
    if isinstance(value, dict):
        return {k: render_template(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [render_template(item, params) for item in value]
    return value


# ---------------- SSRF 防护 ----------------

def _is_forbidden_ip(ip: str) -> bool:
    """判定 IP 是否属于内网/保留/链路本地等非公网地址段。"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    # is_global=False 覆盖：私有、回环、链路本地、多播、未指定、保留、CGNAT 等
    return not addr.is_global


def _resolve_host_ips(host: str) -> list[str]:
    """DNS 解析 host 得到全部 IP（IPv4/IPv6）；解析失败抛 ValueError。"""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"域名解析失败: {host}") from exc
    ips = {info[4][0] for info in infos}
    return sorted(ips)


def check_ssrf(url: str) -> None:
    """SSRF 防护：URL 主机为 IP 直接校验；为域名则 DNS 解析后逐个 IP 校验。

    任一地址命中内网/保留段即拒绝；解析失败视为不可达，拒绝执行。
    """
    if not settings.http_tool_ssrf_enabled:
        return
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError(f"URL 缺少主机: {url}")
    candidate_ips: list[str]
    try:
        # host 本身是 IP（含 IPv6 字面量）时直接校验
        ipaddress.ip_address(host)
        candidate_ips = [host]
    except ValueError:
        candidate_ips = _resolve_host_ips(host)
    for ip in candidate_ips:
        if _is_forbidden_ip(ip):
            raise ValueError(f"SSRF 防护：拒绝访问内网/保留地址 {ip}（{host}）")


# ---------------- 认证注入 ----------------

def _inject_auth(headers: dict, auth: Any, params: dict) -> None:
    """认证注入：api_key / bearer / basic（auth.value 支持 {param} 模板）。"""
    if not isinstance(auth, dict):
        return
    auth_type = str(auth.get("type", "")).lower()
    if not auth_type:
        return
    header_name = str(auth.get("headerName") or "Authorization")
    if auth_type == "api_key":
        headers[header_name] = str(render_template(auth.get("value", ""), params))
    elif auth_type == "bearer":
        token = str(render_template(auth.get("value", ""), params))
        headers[header_name] = f"Bearer {token}" if not token.startswith("Bearer ") else token
    elif auth_type == "basic":
        value = auth.get("value")
        if isinstance(value, dict):
            username = str(render_template(value.get("username", ""), params))
            password = str(render_template(value.get("password", ""), params))
        else:
            username, _, password = str(render_template(value or "", params)).partition(":")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers[header_name] = f"Basic {token}"


# ---------------- 执行 ----------------

def _normalize_config(config: dict) -> dict:
    """规范化配置：方法大写 + 白名单；timeoutSeconds 限制在 1-60s。"""
    method = str(config.get("method", "GET")).upper()
    if method not in _ALLOWED_METHODS:
        raise ValueError(f"不支持的 HTTP 方法: {method}")
    try:
        timeout = max(1, min(60, int(config.get("timeoutSeconds", settings.http_tool_timeout_seconds))))
    except (TypeError, ValueError):
        timeout = settings.http_tool_timeout_seconds
    return {**config, "method": method, "timeout": timeout}


def _limit_body(body: bytes) -> str:
    """响应体解码 + 超限截断（1MB 上限，截断标记保留）。"""
    text = body.decode("utf-8", errors="replace")
    if len(text) > settings.http_tool_max_response_bytes:
        return text[: settings.http_tool_max_response_bytes] + "…[响应体超限截断]"
    return text


def execute(config: dict, params: dict) -> str:
    """执行 HTTP 工具：渲染 → SSRF 校验 → 发请求 → 返回可读结果文本。

    非 2xx 返回失败文本（如 "HTTP 404: ..."），不抛异常 —— 工具失败不阻断对话主链路。
    """
    cfg = _normalize_config(config)
    method = cfg["method"]
    params = params or {}

    url = str(render_template(cfg.get("url", ""), params))
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"URL 必须以 http:// 或 https:// 开头: {url}")

    # SSRF 防护：发请求前校验（IP 段 + DNS 二次校验）
    check_ssrf(url)

    headers = {str(k): str(v) for k, v in render_template(cfg.get("headers") or {}, params).items()}
    if "Content-Type" not in headers and cfg.get("bodyTemplate") is not None:
        headers["Content-Type"] = "application/json"
    _inject_auth(headers, cfg.get("auth"), params)

    query: dict[str, str] = {}
    for k, v in (render_template(cfg.get("query") or {}, params) or {}).items():
        query[str(k)] = "" if v is None else str(v)

    body: Any = None
    body_template = cfg.get("bodyTemplate")
    if body_template is not None:
        rendered = render_template(body_template, params)
        body = json.dumps(rendered, ensure_ascii=False) if isinstance(rendered, (dict, list)) \
            else str(rendered)

    try:
        with httpx.Client(timeout=cfg["timeout"], follow_redirects=False) as client:
            response = client.request(method, url, params=query or None,
                                      headers=headers, content=body)
            text = _limit_body(response.content)
    except httpx.TimeoutException as exc:
        raise TimeoutError(f"HTTP 请求超时（{cfg['timeout']}s）") from exc
    except httpx.RequestError as exc:
        raise ConnectionError(f"HTTP 请求失败: {exc}") from exc

    if 200 <= response.status_code < 300:
        return text
    # 非 2xx：转为失败文本（可读、不阻断主链路）
    detail = text[:500].strip()
    return f"HTTP {response.status_code}: {detail}" if detail else f"HTTP {response.status_code}"
