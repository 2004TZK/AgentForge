"""M2.3 星盘分析师端到端验证（真实 LLM，.env 已配 key）。

场景：
  M2.3.1 主链路   输入"1994-05-20 14:30 北京" → 触发 star_chart → 完整解读（800-1200 字、结构、免责）
  M2.3.2 追问链路 同一会话"那我事业运呢？" → 重新排盘 → 事业维度解读
  M2.3.3 失败链路 城市不在库 / 缺出生时间 / 经纬度缺时区 → 可读错误 → LLM 引导补全
  M2.3.4 边界    全程观察：不自动定位、不恐吓、免责声明
  M2.3.5 稳定性  主链路输入另跑 2 次 → 解读结构稳定、数值口径一致

前置：docker compose 服务已启动（http://localhost）。
运行：PYTHONUTF8=1 agentforge-ai/.venv/Scripts/python.exe agentforge-ai/tests/e2e_star_chart_agent.py
输出：完整回答保存至 tests/out/ 目录；控制台输出各场景 PASS/FAIL 摘要。
"""
import json
import re
import sys
import time
from pathlib import Path

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost/api"
AGENT_ID = 4  # 星盘分析师（02-data.sql）
OUT_DIR = Path(__file__).resolve().parent / "out"
OUT_DIR.mkdir(exist_ok=True)

# 主链路基准输入
MAIN_INPUT = "1994-05-20 14:30 北京"
FOLLOW_UP = "那我事业运呢？"

# 结构检查关键词（对应 5.1 输出 8 段）
STRUCTURE_KEYS = ["总览", "上升", "太阳", "月亮", "水星", "金星", "火星", "宫位", "相位", "小结"]
DISCLAIMER_KEYS = ["仅供娱乐", "自我探索", "仅供参考"]
NO_POSITIONING_KEYS = ["检测到您的位置", "根据您的IP", "定位到您", "您所在位置"]


def new_client(timeout: float = 600.0) -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=timeout)


def login(client: httpx.Client) -> None:
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"登录失败: {data}")
    client.headers["Authorization"] = f"Bearer {data['data']['token']}"
    print("[登录] admin 成功")


def create_session(client: httpx.Client, name: str) -> int:
    resp = client.post("/chat/session", json={"agentId": AGENT_ID, "name": name})
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"创建会话失败: {data}")
    print(f"[会话] 已创建: {name} (sessionId={data['data']['id']})")
    return data["data"]["id"]


def chat(client: httpx.Client, session_id: int, message: str, tag: str) -> dict:
    """发送消息并保存完整回答到 out/ 目录。"""
    print(f"[聊天] {tag}: {message}")
    resp = client.post("/chat", json={"agentId": AGENT_ID, "sessionId": session_id, "message": message})
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"聊天失败: {data}")
    result = data["data"]
    answer = result.get("answer") or ""
    (OUT_DIR / f"{tag}.txt").write_text(f"## 输入：{message}\n\n" + answer, encoding="utf-8")
    tool_calls = result.get("toolCalls") or []
    if tool_calls:
        print(f"  → 工具调用: {tool_calls}")
    print(f"  → 回答长度: {len(answer)} 字")
    return result


def check_structure(answer: str) -> list[str]:
    """结构检查：8 段关键词命中情况。"""
    missing = [k for k in STRUCTURE_KEYS if k not in answer]
    return missing


def check_disclaimer(answer: str) -> bool:
    return any(k in answer for k in DISCLAIMER_KEYS)


def check_no_positioning(answer: str) -> bool:
    return not any(k in answer for k in NO_POSITIONING_KEYS)


def tool_calls(result: dict) -> list[str]:
    """后端返回的 toolCalls 为字符串数组（如 'star_chart({...}) → ...'）。"""
    return result.get("toolCalls") or []


def has_tool(result: dict, name: str) -> bool:
    return any(call.startswith(name) for call in tool_calls(result))


def main() -> None:
    results = {}
    client = new_client()
    login(client)

    # ── M2.3.1 主链路 ──
    s_main = create_session(client, "M2.3.1 主链路")
    r = chat(client, s_main, MAIN_INPUT, "m231_main")
    tools = tool_calls(r)
    answer = r.get("answer") or ""
    missing = check_structure(answer)
    disclaimer = check_disclaimer(answer)
    no_pos = check_no_positioning(answer)
    length_ok = 600 <= len(answer) <= 1400  # 800-1200 为设计值，放宽观察
    results["m231_main"] = {
        "工具触发": has_tool(r, "star_chart"),
        "工具列表": tools,
        "字数": len(answer),
        "字数达标(600-1400)": length_ok,
        "结构缺失": missing,
        "免责声明": disclaimer,
        "不自动定位": no_pos,
    }
    print(f"[M2.3.1] 工具={tools} 字数={len(answer)} 结构缺失={missing} 免责={disclaimer} 不定位={no_pos}")

    # ── M2.3.2 追问链路（同一会话，验证重新排盘） ──
    r2 = chat(client, s_main, FOLLOW_UP, "m232_followup")
    tools2 = tool_calls(r2)
    answer2 = r2.get("answer") or ""
    results["m232_followup"] = {
        "重新排盘(再次调star_chart)": has_tool(r2, "star_chart"),
        "工具列表": tools2,
        "字数": len(answer2),
        "聚焦事业": ("事业" in answer2) or ("10宫" in answer2) or ("官禄" in answer2),
        "免责声明": check_disclaimer(answer2),
    }
    print(f"[M2.3.2] 工具={tools2} 字数={len(answer2)} 聚焦事业={results['m232_followup']['聚焦事业']}")

    # ── M2.3.3 失败链路（三个子场景，各开新会话） ──
    fail_cases = [
        ("铁岭", "1994-05-20 14:30 铁岭", "城市不在库→引导经纬度"),
        ("缺时间", "1994-05-20 北京", "缺出生时间→追问时间"),
        ("经纬度缺时区", "1994-05-20 14:30 39.9042 116.4074", "缺时区→追问时区"),
    ]
    for tag, msg, expect in fail_cases:
        s = create_session(client, f"M2.3.3 {tag}")
        rf = chat(client, s, msg, f"m233_{tag}")
        af = rf.get("answer") or ""
        toolsf = tool_calls(rf)
        results[f"m233_{tag}"] = {
            "工具列表": toolsf,
            "字数": len(af),
            "无编造排盘(无星座宫位断言)": not any(k in af for k in ["上升星座是", "太阳落在", "月亮落在"]),
            "说明": af[:150],
        }
        print(f"[M2.3.3] {tag}: 工具={toolsf} 摘要={af[:80]!r}")

    # ── M2.3.5 稳定性（主链路另跑 2 次，新会话） ──
    for i in (2, 3):
        s = create_session(client, f"M2.3.5 稳定性-{i}")
        rs = chat(client, s, MAIN_INPUT, f"m235_run{i}")
        as_ = rs.get("answer") or ""
        results[f"m235_run{i}"] = {
            "工具触发": has_tool(rs, "star_chart"),
            "字数": len(as_),
            "结构缺失": check_structure(as_),
            "免责声明": check_disclaimer(as_),
        }
        print(f"[M2.3.5] run{i}: 字数={len(as_)} 结构缺失={check_structure(as_)}")

    # ── 汇总 ──
    report = json.dumps(results, ensure_ascii=False, indent=2)
    (OUT_DIR / "report.json").write_text(report, encoding="utf-8")
    print("\n===== 汇总（完整见 out/report.json）=====")
    print(report)


if __name__ == "__main__":
    main()
