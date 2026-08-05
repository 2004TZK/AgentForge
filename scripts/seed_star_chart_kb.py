# -*- coding: utf-8 -*-
"""M3.2.2 星盘知识库五件套批量入库（docs/star-chart-kb/ 切片 →「星盘分析师」agent id=4）。

流程：demo 登录 → 逐个上传切片 .md（POST /file/upload?agentId=4）→ 轮询 READY。
幂等：同名文件已 READY 则复用跳过（后端同名上传会先删旧向量再入库，可安全重传）。
文件管理页删除某文件后重跑本脚本即可恢复。
输出：入库文件清单（文件数、总字符数、每文件状态）。

运行：PYTHONUTF8=1 agentforge-ai/.venv/Scripts/python.exe scripts/seed_star_chart_kb.py
依赖：httpx（agentforge-ai/.venv 已装）
"""
import sys
import time
from pathlib import Path

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost/api"
AGENT_ID = 4  # 星盘分析师（02-data.sql）
DEMO_USER = "demo"
DEMO_PASSWORD = "demo123"
KB_DIR = Path(__file__).resolve().parent.parent / "docs" / "star-chart-kb"
TIMEOUT = 300.0  # 单文件入库超时（后端同步 ingest，最大可阻塞数分钟）


def login(client: httpx.Client) -> None:
    resp = client.post("/auth/login", json={"username": DEMO_USER, "password": DEMO_PASSWORD})
    data = resp.json()
    if data.get("code") != 0:
        # demo 未注册时先注册
        resp = client.post("/auth/register", json={
            "username": DEMO_USER, "password": DEMO_PASSWORD, "email": "demo@agentforge.local",
        })
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"demo 登录/注册失败: {data}")
        resp = client.post("/auth/login", json={"username": DEMO_USER, "password": DEMO_PASSWORD})
        data = resp.json()
    client.headers["Authorization"] = f"Bearer {data['data']['token']}"
    print(f"[用户] 登录成功: {DEMO_USER}")


def list_ready(client: httpx.Client) -> set[str]:
    lst = client.get("/file/list", params={"agentId": AGENT_ID, "page": 1, "size": 100}).json()
    return {doc["fileName"] for doc in lst.get("data", {}).get("list", [])
            if doc["status"] == "READY"}


def upload_and_wait(client: httpx.Client, path: Path, timeout: float = TIMEOUT) -> str:
    with path.open("rb") as f:
        resp = client.post("/file/upload", params={"agentId": AGENT_ID},
                           files={"file": (path.name, f, "text/markdown")})
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"上传 {path.name} 失败: {data}")
    doc_id = data["data"]["id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        lst = client.get("/file/list", params={"agentId": AGENT_ID, "page": 1, "size": 100}).json()
        for doc in lst.get("data", {}).get("list", []):
            if doc["id"] == doc_id:
                if doc["status"] == "READY":
                    return "READY"
                if doc["status"] == "FAILED":
                    raise RuntimeError(f"{path.name} 入库 FAILED: {doc}")
        time.sleep(3)
    raise RuntimeError(f"{path.name} 入库超时")


def main() -> int:
    files = sorted(KB_DIR.glob("*.md"))
    if not files:
        print(f"未找到切片文件: {KB_DIR}")
        return 1
    total_chars = sum(p.stat().st_size for p in files)
    print(f"[知识库] 待入库 {len(files)} 个切片文件（共 {total_chars} 字节）→ agent {AGENT_ID}")

    client = httpx.Client(base_url=BASE_URL, timeout=600.0)
    login(client)
    ready = list_ready(client)
    print(f"[知识库] 已入库 READY {len(ready)} 个，待上传 {len(files) - len(ready)} 个")

    ok, failed = 0, 0
    for path in files:
        if path.name in ready:
            print(f"  - {path.name}（复用）")
            ok += 1
            continue
        status = upload_and_wait(client, path)
        print(f"  - {path.name} → {status}")
        ok += 1
    print(f"\n[知识库] 完成：{ok} 个 READY，{failed} 个失败")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
