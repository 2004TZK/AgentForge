"""LLM 流式工具调用回归测试（M2.5 修复）。

背景：OpenAI 兼容流式协议的 tool_calls 是增量传输——首个 chunk 带 id+name+空
arguments，后续 chunk 仅携带 arguments 片段。此前实现把每个 chunk 当独立调用，
导致 name 为空（工具未注册）与参数残缺（执行报错）。本测试验证按 index 累积
拼接后产出完整 tool_call。
"""
import json

import asyncio
import pytest


async def _collect(client, messages=None, tools=None):
    """收集 _stream_openai_tools 全部事件。"""
    events = []
    async for event in client._stream_openai_tools(
        messages or [{"role": "user", "content": "hi"}],
        tools or [],
        0.7,
    ):
        events.append(event)
    return events



from app.services.llm import LLMClient

# 模拟 qwen3.7-plus 的流式分块：id+name 首块 → arguments 分片 → [DONE]
_STREAM_CHUNKS = [
    'data: {"choices": [{"delta": {"tool_calls": ['
    '{"index": 0, "id": "call_abc", "function": {"name": "star_chart", "arguments": ""}}'
    "]}}]}",
    'data: {"choices": [{"delta": {"tool_calls": ['
    '{"index": 0, "function": {"arguments": "{\\"birthDate\\": \\"1994-05-20\\", '
    '\\"birthTime\\": \\"14:30\\", \\"city\\": \\"北京\\"}"}}'
    "]}}]}",
    "data: [DONE]",
]


class _FakeResp:
    def __init__(self):
        self._lines = _STREAM_CHUNKS
        self.is_success = True
        self.status_code = 200

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeClient:
    """替换 httpx.AsyncClient：stream() 返回 fake resp。"""

    def __init__(self, timeout=None):
        self.resp = _FakeResp()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, *args, **kwargs):
        class _Ctx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *exc):
                return False

        return _Ctx(self.resp)


def test_stream_openai_tools_accumulates_incremental_arguments(monkeypatch):
    """增量 tool_calls 按 index 累积拼接，产出完整调用。"""
    client = LLMClient({"baseUrl": "http://fake", "apiKey": "k", "type": "openai"})
    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", _FakeClient)

    events = asyncio.run(_collect(client, [{"role": "user", "content": "1994-05-20 14:30 北京"}], [{"type": "function", "function": {"name": "star_chart"}}]))

    done = events[-1]
    assert done["type"] == "done"
    calls = done["tool_calls"]
    assert len(calls) == 1, f"应产出 1 个完整调用，实际 {len(calls)}"
    call = calls[0]
    assert call["name"] == "star_chart"
    assert call["tool_call_id"] == "call_abc"
    assert call["arguments"] == {
        "birthDate": "1994-05-20",
        "birthTime": "14:30",
        "city": "北京",
    }, f"arguments 应完整解析为 dict，实际 {call['arguments']}"


def test_stream_openai_tools_multiple_calls(monkeypatch):
    """多个并发 tool_call（不同 index）互不串扰。"""
    chunks = [
        'data: {"choices": [{"delta": {"tool_calls": ['
        '{"index": 0, "id": "c1", "function": {"name": "calc", "arguments": "{\\"expression\\": \\"1+1\\"}"}},'
        '{"index": 1, "id": "c2", "function": {"name": "calc", "arguments": "{\\"expression\\": "}}'
        "]}}]}",
        'data: {"choices": [{"delta": {"tool_calls": ['
        '{"index": 1, "function": {"arguments": "\\"2*3\\"}"}}'
        "]}}]}",
        "data: [DONE]",
    ]
    fake_resp = _FakeResp()
    fake_resp._lines = chunks
    fake_client = _FakeClient()
    fake_client.resp = fake_resp

    client = LLMClient({"baseUrl": "http://fake", "apiKey": "k", "type": "openai"})
    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", lambda **kw: fake_client)

    events = asyncio.run(_collect(client))

    calls = events[-1]["tool_calls"]
    assert len(calls) == 2
    assert calls[0]["tool_call_id"] == "c1"
    assert calls[0]["arguments"] == {"expression": "1+1"}
    assert calls[1]["tool_call_id"] == "c2"
    assert calls[1]["arguments"] == {"expression": "2*3"}, f"index1 参数应跨块拼接，实际 {calls[1]['arguments']}"


def test_stream_openai_tools_broken_json_keeps_raw(monkeypatch):
    """arguments 非完整 JSON 时保持 _raw 兜底（不抛异常）。"""
    chunks = [
        'data: {"choices": [{"delta": {"tool_calls": ['
        '{"index": 0, "id": "c1", "function": {"name": "github", "arguments": "{"}}'
        "]}}]}",
        "data: [DONE]",
    ]
    fake_resp = _FakeResp()
    fake_resp._lines = chunks
    fake_client = _FakeClient()
    fake_client.resp = fake_resp

    client = LLMClient({"baseUrl": "http://fake", "apiKey": "k", "type": "openai"})
    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", lambda **kw: fake_client)

    events = asyncio.run(_collect(client))

    calls = events[-1]["tool_calls"]
    assert len(calls) == 1
    assert calls[0]["name"] == "github"
    assert calls[0]["arguments"] == {"_raw": "{"}, f"非法 JSON 应以 _raw 保留原文，实际 {calls[0]['arguments']}"
