# -*- coding: utf-8 -*-
"""M3.2.3 星盘知识库检索验证（Qdrant agent_4，text-embedding-v3）。

验证问题清单 → 期望命中文件（topK=4 内）：
  宫位    "太阳落10宫怎么解读"    → 星盘宫位完整解析-第10宫
  相位    "刑相位是什么意思"      → 手册-六、第四步：认识相位 / 格局速查表
  相位    "拱相位呢"              → 手册-六、第四步：认识相位 / 格局速查表
  格局    "大三角格局代表什么"    → 格局速查表-大三角
  落座    "火星落天蝎座"          → 行星落座速查表-火星
  方法论  "解读星盘按什么步骤"    → 手册-七、完整读盘步骤

访问路径：/ai/rag/search（nginx /ai/ upstream → AI 服务，X-Internal-Token 保护；
文档原写的 /rag/search 会被 Java 后端兜底拦截，实为 /ai/rag/search）。

前置：五件套切片已入库（scripts/seed_star_chart_kb.py 跑过，agent 4）。
运行：PYTHONUTF8=1 agentforge-ai/.venv/Scripts/python.exe -m pytest agentforge-ai/tests/test_rag_star_chart_search.py -q
      （可离线重复执行——检索不调 LLM，仅 Embedding API）
"""
import sys
from typing import Any

import httpx
import pytest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost"
INTERNAL_TOKEN = "change-me-internal-token"
AGENT_ID = 4
TOP_K = 4

CASES: list[tuple[str, str, str]] = [
    ("宫位", "太阳落10宫怎么解读", "星盘宫位完整解析-第10宫"),
    ("相位-刑", "刑相位是什么意思", "星盘完整阅读逻辑手册-六、第四步：认识相位"),
    ("相位-拱", "拱相位呢", "星盘完整阅读逻辑手册-六、第四步：认识相位"),
    ("格局", "大三角格局代表什么", "格局速查表-大三角"),
    ("落座", "火星落天蝎座", "行星落座速查表-火星"),
    ("方法论", "解读星盘按什么步骤", "星盘完整阅读逻辑手册-七、完整读盘步骤"),
]


def search(query: str) -> list[dict[str, Any]]:
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        resp = client.post("/ai/rag/search",
                           json={"agentId": AGENT_ID, "query": query, "topK": TOP_K},
                           headers={"X-Internal-Token": INTERNAL_TOKEN})
        assert resp.status_code == 200, f"检索接口异常: {resp.status_code} {resp.text[:200]}"
        return resp.json()["chunks"]


def hit(chunks: list[dict[str, Any]], expect: str) -> bool:
    return any(expect in ch["file"] for ch in chunks)


@pytest.mark.parametrize("label,query,expect", CASES, ids=[c[0] for c in CASES])
def test_kb_hit(label: str, query: str, expect: str) -> None:
    chunks = search(query)
    assert chunks, f"{label}: 检索无结果"
    assert hit(chunks, expect), (
        f"{label}: 未命中 {expect}（topK={TOP_K} 内）\n"
        + "\n".join(f"  {ch['file']} score={ch['score']:.3f}" for ch in chunks)
    )


def test_kb_top1_house_query() -> None:
    """宫位类问题应命中第 1 位（验收示例口径）。"""
    chunks = search("太阳落10宫怎么解读")
    assert "星盘宫位完整解析-第10宫" in chunks[0]["file"], (
        "第10宫应排第 1 位\n" + "\n".join(f"  {ch['file']} {ch['score']:.3f}" for ch in chunks)
    )
