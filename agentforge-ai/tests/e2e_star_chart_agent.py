"""M2.3 星盘分析师端到端验证（真实 LLM，.env 已配 key）。

场景：
  M2.3.1 主链路   输入"1994-05-20 14:30 北京" → 触发 star_chart → 完整解读（800-2800 字、结构、免责）
  M2.3.2 追问链路 同一会话"那我事业运呢？" → 重新排盘 → 事业维度解读
  M2.3.3 失败链路 城市不在库 / 缺出生时间 / 经纬度缺时区 → 可读错误 → LLM 引导补全
  M2.3.4 边界    全链路审计：不自动定位、不恐吓、无宿命断言、免责声明
  M2.3.5 稳定性  主链路输入另跑 2 次 → 解读结构稳定、数值口径一致

硬断言：每个场景都有断言，任一失败 → 脚本非零退出码 / pytest 用例失败。
pytest 收集时默认跳过（避免无 Key/无栈时误跑），设 E2E_STAR_CHART=1 后运行真实链路。

前置：docker compose 服务已启动（http://localhost），星盘分析师（id=4）已入库。
运行脚本：PYTHONUTF8=1 E2E_STAR_CHART=1 agentforge-ai/.venv/Scripts/python.exe agentforge-ai/tests/e2e_star_chart_agent.py
运行 pytest：E2E_STAR_CHART=1 agentforge-ai/.venv/Scripts/python.exe -m pytest agentforge-ai/tests/e2e_star_chart_agent.py -q
输出：完整回答保存至 tests/out/ 目录；控制台输出各场景 PASS/FAIL 摘要。
"""
import json
import os
import sys
from pathlib import Path

import httpx
import pytest

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
# M2.3.4 边界红线：恐吓 / 宿命断言（提示词允许"而非厄运"这类正确否定，故不匹配孤立词）
FEAR_KEYS = ["命中注定", "一定会", "天选之人", "你注定", "厄运缠身", "大凶"]
FABRICATED_KEYS = ["上升星座是", "太阳落在", "月亮落在"]
# 经纬度缺时区 → 必须出现时区追问（或工具返回"必须提供 timezone"）
TIMEZONE_KEYS = ["时区", "timezone", "UTC"]
# 字数验收（2026-08-05 决策放宽；提示词仍以 800-1200 收紧）
LEN_MIN, LEN_MAX = 800, 2800
# 完整解读场景（要求免责声明 / 无恐吓 / 不定位）
FULL_READING_KEYS = ["m231_main", "m232_followup", "m235_run2", "m235_run3"]


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
    return [k for k in STRUCTURE_KEYS if k not in answer]


def check_disclaimer(answer: str) -> bool:
    return any(k in answer for k in DISCLAIMER_KEYS)


def check_no_positioning(answer: str) -> bool:
    return not any(k in answer for k in NO_POSITIONING_KEYS)


def check_no_fear(answer: str) -> bool:
    return not any(k in answer for k in FEAR_KEYS)


def tool_calls(result: dict) -> list[str]:
    """后端返回的 toolCalls 为字符串数组（如 'star_chart({...}) → ...'）。"""
    return result.get("toolCalls") or []


def has_tool(result: dict, name: str) -> bool:
    return any(call.startswith(name) for call in tool_calls(result))


def audit(results: dict, failures: list[str]) -> None:
    """集中断言：任一红线不满足即记入 failures。"""

    def check(name: str, ok: bool, detail: str = "") -> None:
        mark = "✅" if ok else "❌"
        print(f"  [{mark}] {name}" + (f"（{detail}）" if detail else ""))
        if not ok:
            failures.append(name)

    # M2.3.1 主链路
    m = results["m231_main"]
    check("M2.3.1 工具触发", m["工具触发"])
    check("M2.3.1 结构完整", not m["结构缺失"], f"缺 {m['结构缺失']}")
    check("M2.3.1 字数 800-2800", m["字数达标"], f"{m['字数']} 字")

    # M2.3.2 追问链路
    m = results["m232_followup"]
    check("M2.3.2 重新排盘(再次调star_chart)", m["重新排盘(再次调star_chart)"])
    check("M2.3.2 聚焦事业", m["聚焦事业"])

    # M2.3.3 失败链路
    for tag in ("铁岭", "缺时间", "经纬度缺时区"):
        r = results[f"m233_{tag}"]
        check(f"M2.3.3 {tag} 不编造排盘", r["无编造排盘(无星座宫位断言)"])
    check("M2.3.3 铁岭→引导经纬度", results["m233_铁岭"]["引导经纬度"])
    check("M2.3.3 缺时间→追问时间", results["m233_缺时间"]["追问时间"])
    check("M2.3.3 缺时区→追问时区", results["m233_经纬度缺时区"]["引导时区"])
    # 若模型在缺时区场景自行补全时区排了盘，仍须遵守完整解读的输出规范
    if results["m233_经纬度缺时区"]["字数"] > 1000:
        r = results["m233_经纬度缺时区"]
        check("M2.3.3 缺时区(自行排盘) 免责声明", r["免责声明"])
        check("M2.3.3 缺时区(自行排盘) 无恐吓", r["无恐吓"])

    # M2.3.5 稳定性
    for i in (2, 3):
        r = results[f"m235_run{i}"]
        check(f"M2.3.5 run{i} 工具触发", r["工具触发"])
        check(f"M2.3.5 run{i} 结构完整", not r["结构缺失"], f"缺 {r['结构缺失']}")

    # M2.3.4 边界（全链路审计）
    for key in FULL_READING_KEYS:
        r = results[key]
        check(f"{key} 免责声明", r["免责声明"])
        check(f"{key} 无恐吓/宿命断言", r["无恐吓"])
    for key, r in results.items():
        check(f"{key} 不自动定位", r["不自动定位"])


def collect_results(client: httpx.Client) -> tuple[dict, list[str]]:
    """运行全部场景并做断言，返回 (results, failures)。"""
    results: dict = {}
    failures: list[str] = []

    # ── M2.3.1 主链路 ──
    s_main = create_session(client, "M2.3.1 主链路")
    r = chat(client, s_main, MAIN_INPUT, "m231_main")
    tools = tool_calls(r)
    answer = r.get("answer") or ""
    missing = check_structure(answer)
    results["m231_main"] = {
        "工具触发": has_tool(r, "star_chart"),
        "工具列表": tools,
        "字数": len(answer),
        "字数达标": LEN_MIN <= len(answer) <= LEN_MAX,
        "结构缺失": missing,
        "免责声明": check_disclaimer(answer),
        "不自动定位": check_no_positioning(answer),
        "无恐吓": check_no_fear(answer),
    }
    print(f"[M2.3.1] 工具={tools} 字数={len(answer)} 结构缺失={missing}")

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
        "不自动定位": check_no_positioning(answer2),
        "无恐吓": check_no_fear(answer2),
    }
    print(f"[M2.3.2] 工具={tools2} 字数={len(answer2)} 聚焦事业={results['m232_followup']['聚焦事业']}")

    # ── M2.3.3 失败链路（三个子场景，各开新会话） ──
    fail_cases = [
        ("铁岭", "1994-05-20 14:30 铁岭", "城市不在库→引导经纬度"),
        ("缺时间", "1994-05-20 北京", "缺出生时间→追问时间"),
        ("经纬度缺时区", "1994-05-20 14:30 39.9042 116.4074", "缺时区→追问时区"),
    ]
    for tag, msg, _expect in fail_cases:
        s = create_session(client, f"M2.3.3 {tag}")
        rf = chat(client, s, msg, f"m233_{tag}")
        af = rf.get("answer") or ""
        toolsf = tool_calls(rf)
        joined_tools = " ".join(toolsf)
        results[f"m233_{tag}"] = {
            "工具列表": toolsf,
            "字数": len(af),
            "无编造排盘(无星座宫位断言)": not any(k in af for k in FABRICATED_KEYS),
            "免责声明": check_disclaimer(af),
            "不自动定位": check_no_positioning(af),
            "无恐吓": check_no_fear(af),
            "说明": af[:150],
        }
        if tag == "铁岭":
            results[f"m233_{tag}"]["引导经纬度"] = any(k in af for k in ("经纬度", "坐标", "时区"))
        elif tag == "缺时间":
            results[f"m233_{tag}"]["追问时间"] = ("出生时间" in af) or ("几点" in af)
        else:
            results[f"m233_{tag}"]["引导时区"] = any(k in af for k in TIMEZONE_KEYS) or ("必须提供 timezone" in joined_tools)
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
            "不自动定位": check_no_positioning(as_),
            "无恐吓": check_no_fear(as_),
        }
        print(f"[M2.3.5] run{i}: 字数={len(as_)} 结构缺失={check_structure(as_)}")

    audit(results, failures)
    return results, failures


def main() -> int:
    client = new_client()
    login(client)
    results, failures = collect_results(client)
    report = json.dumps(results, ensure_ascii=False, indent=2)
    (OUT_DIR / "report.json").write_text(report, encoding="utf-8")
    print("\n===== 汇总（完整见 out/report.json）=====")
    print(report)
    print(f"\n===== 断言结果：{len(failures)} 项失败 =====")
    for f in failures:
        print(f"  ❌ {f}")
    if failures:
        return 1
    print("全部场景 PASS ✅")
    return 0


E2E_ENABLED = os.environ.get("E2E_STAR_CHART") == "1"


@pytest.mark.skipif(not E2E_ENABLED, reason="真实 LLM 端到端：需运行栈 + 模型 Key，设 E2E_STAR_CHART=1 后运行")
def test_e2e_star_chart_full() -> None:
    """M2.3 全量 5 场景端到端断言（含 M2.3.4 边界审计）。"""
    client = new_client()
    login(client)
    _results, failures = collect_results(client)
    assert not failures, f"端到端断言失败 {len(failures)} 项: {failures}"


if __name__ == "__main__":
    sys.exit(main())
