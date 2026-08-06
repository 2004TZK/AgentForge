"""M3.1 星盘深度分析工作流端到端验证（真实 LLM，.env 已配 key）。

场景：
  M3.1.1 定义校验  种子工作流「星盘深度分析」存在且链为 chart(tool) → dimension(llm) → summary(llm|END)
  M3.1.2 运行验证  POST /workflows/{id}/run {"input":{"message":"1994-05-20 14:30 北京"}}
                   → RUNNING → SUCCESS；node_logs 三条（chart/dimension/summary）全部 SUCCESS 且按序；
                   输出为完整报告（含总览/维度/免责声明，1000-2800 字）

硬断言：任一失败 → 非零退出码 / pytest 用例失败。
pytest 收集时默认跳过（避免无 Key/无栈时误跑），设 E2E_WORKFLOW=1 后运行真实链路。

前置：docker compose 服务已启动（http://localhost）；20260805-add-star-chart-workflow.sql 已迁移。
运行脚本：PYTHONUTF8=1 E2E_WORKFLOW=1 agentforge-ai/.venv/Scripts/python.exe agentforge-ai/tests/e2e_star_chart_workflow.py
运行 pytest：E2E_WORKFLOW=1 agentforge-ai/.venv/Scripts/python.exe -m pytest agentforge-ai/tests/e2e_star_chart_workflow.py -q
输出：完整报告保存至 tests/out/ 目录；控制台输出各场景 PASS/FAIL 摘要。
"""
import json
import sys
import time
from pathlib import Path

import httpx
import pytest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost/api"
WORKFLOW_NAME = "星盘深度分析"
MAIN_INPUT = "1994-05-20 14:30 北京"
OUT_DIR = Path(__file__).resolve().parent / "out"
OUT_DIR.mkdir(exist_ok=True)

# 报告结构语义断言：实际措辞由 LLM 决定（如宫位写作"2宫"、免责为完整语句）
REPORT_KEYS = ["上升", "太阳", "月亮", "相位", "宫", "建议"]
DISCLAIMER_KEYS = ["仅供娱乐", "自我探索", "仅供参考"]
LEN_MIN, LEN_MAX = 1200, 3200


def new_client(timeout: float = 900.0) -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=timeout)


def login(client: httpx.Client) -> None:
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    data = resp.json()
    assert data.get("code") == 0, f"登录失败: {data}"
    client.headers["Authorization"] = "Bearer " + data["data"]["token"]


def get_workflow(client: httpx.Client) -> dict:
    resp = client.get("/workflows", params={"page": 1, "size": 50})
    data = resp.json()
    assert data.get("code") == 0, f"工作流列表失败: {data}"
    for wf in data["data"]["list"]:
        if wf["name"] == WORKFLOW_NAME:
            return wf
    raise AssertionError(f"未找到工作流「{WORKFLOW_NAME}」")


def run_workflow(client: httpx.Client, wf_id: int, input_text: str) -> dict:
    resp = client.post(f"/workflows/{wf_id}/run", json={"input": {"message": input_text}})
    data = resp.json()
    assert data.get("code") == 0, f"触发运行失败: {data}"
    run_id = data["data"]["id"]
    deadline = time.time() + 600
    while time.time() < deadline:
        run = client.get(f"/workflows/runs/{run_id}").json()["data"]
        if run["status"] in ("SUCCESS", "FAILED"):
            return run
        time.sleep(5)
    raise AssertionError(f"运行 {run_id} 超时（600s）")


def check_definition(wf: dict) -> None:
    assert wf["status"] == "ACTIVE", f"工作流状态异常: {wf['status']}"
    nodes = wf["nodes"]
    assert len(nodes) == 3, f"节点数应为 3，实际 {len(nodes)}"
    chain = [(n["nodeKey"], n["nodeType"], n["nextNode"]) for n in nodes]
    assert chain == [("chart", "tool", "dimension"),
                     ("dimension", "llm", "summary"),
                     ("summary", "llm", None)], f"链路异常: {chain}"
    params = {n["nodeKey"]: n["params"] for n in nodes}
    assert params["chart"]["tool"] == "star_chart", "chart 节点工具应为 star_chart"
    assert params["chart"]["payload"].get("birthText") == "{message}", "birthText 应模板引用 {message}"
    assert "{chart}" in params["dimension"]["prompt"], "dimension 提示词应引用 {chart}"
    assert "{dimension}" in params["summary"]["prompt"], "summary 提示词应引用 {dimension}"


def check_run(run: dict) -> None:
    assert run["status"] == "SUCCESS", f"运行失败: status={run['status']} error={run.get('error')}"
    logs = run["nodeLogs"]
    assert len(logs) == 3, f"节点日志应为 3 条，实际 {len(logs)}"
    keys = [log["node"] for log in logs]
    assert keys == ["chart", "dimension", "summary"], f"节点顺序异常: {keys}"
    for log in logs:
        assert log["status"] == "SUCCESS", f"节点 {log['node']} 失败: {log.get('error')}"
        assert log["durationMs"] is not None
    output = run["output"]
    assert output, "运行输出为空"
    missing = [k for k in REPORT_KEYS if k not in output]
    assert not missing, f"报告缺少关键段落: {missing}"
    assert any(d in output for d in DISCLAIMER_KEYS), "报告缺少免责声明"
    assert LEN_MIN <= len(output) <= LEN_MAX, f"报告长度 {len(output)} 不在 [{LEN_MIN}, {LEN_MAX}]"
    (OUT_DIR / "m31_workflow_report.txt").write_text(output, encoding="utf-8")
    (OUT_DIR / "m31_workflow_node_logs.json").write_text(
        json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")


def run_all() -> None:
    client = new_client()
    login(client)
    print("[M3.1.1] 校验工作流定义…")
    wf = get_workflow(client)
    check_definition(wf)
    print(f"        PASS 工作流 id={wf['id']}「{wf['name']}」定义合法（chart→dimension→summary）")
    print(f"[M3.1.2] 运行「{MAIN_INPUT}」…")
    run = run_workflow(client, wf["id"], MAIN_INPUT)
    check_run(run)
    logs = run["nodeLogs"]
    print(f"        PASS 运行成功 status=SUCCESS")
    for log in logs:
        print(f"          - {log['node']:<10} {log['status']}  {log['durationMs']}ms")
    print(f"        报告 {len(run['output'])} 字 → tests/out/m31_workflow_report.txt")
    print("M3.1 全部 PASS")


def main() -> int:
    if os.environ.get("E2E_WORKFLOW") != "1":
        print("跳过（设 E2E_WORKFLOW=1 运行真实链路）")
        return 0
    try:
        run_all()
        return 0
    except AssertionError as e:
        print(f"M3.1 FAIL: {e}")
        return 1


import os  # noqa: E402  (main 使用)

pytestmark = pytest.mark.skipif(
    os.environ.get("E2E_WORKFLOW") != "1", reason="需要真实 LLM，设 E2E_WORKFLOW=1 运行"
)


def test_workflow_definition() -> None:
    client = new_client()
    login(client)
    check_definition(get_workflow(client))


def test_workflow_run() -> None:
    client = new_client()
    login(client)
    run = run_workflow(client, get_workflow(client)["id"], MAIN_INPUT)
    check_run(run)


if __name__ == "__main__":
    sys.exit(main())
