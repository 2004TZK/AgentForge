"""M3 ReAct 工具循环测试：LLM 决策 → 执行 → 回填 → 总结；规则兜底；记忆按用户隔离。

运行：cd agentforge-ai && pytest tests -q
说明：LLM/Redis 全部 mock，不依赖外部服务。
"""
import json

import pytest

from app.core.config import settings
from app.services import agent_runtime, memory
from app.services.llm import llm_client
from app.tools import registry as tool_registry


# ---------------- 辅助 ----------------

class FakeRedis:
    """内存版 Redis 客户端：支持 memory.py 用到的命令。"""

    def __init__(self):
        self.data: dict[str, list[str]] = {}
        self.expired: set[str] = set()

    def ping(self):
        return True

    def lrange(self, key, start, end):
        items = self.data.get(key, [])
        return items[start:] if end == -1 else items[start:end]

    def rpush(self, key, *values):
        self.data.setdefault(key, []).extend(values)
        return len(self.data[key])

    def ltrim(self, key, start, end):
        items = self.data.get(key, [])
        self.data[key] = items[start:] if end == -1 else items[start:end]

    def expire(self, key, seconds):
        self.expired.add(key)

    def delete(self, key):
        self.data.pop(key, None)
        self.expired.discard(key)


@pytest.fixture
def fake_redis(monkeypatch):
    redis_client = FakeRedis()
    monkeypatch.setattr(memory, "_get_redis", lambda: redis_client)
    return redis_client


@pytest.fixture
def mock_mode(monkeypatch):
    """指向不可用的远端地址（无 Key 且非本地）→ LLM 走 Mock 路径。"""
    monkeypatch.setattr(settings, "llm_local", False)
    monkeypatch.setattr(llm_client, "base_url", "https://api.example.com")


def _fake_llm_with_tools(responses: list[dict], calls: list):
    """构造 chat_with_tools mock：依次返回 responses（可含 {content, tool_calls}）。"""

    def fake(messages, tools, temperature=0.7):
        calls.append(([json.dumps(m, ensure_ascii=False) for m in messages], tools))
        return responses[min(len(calls) - 1, len(responses) - 1)]

    return fake


# ---------------- ReAct 循环 ----------------

class TestReactLoop:
    def test_star_chart_answer_capped_at_max(self, monkeypatch, fake_redis):
        """绑定 star_chart 的智能体回答超长时按句子边界截断至硬上限。"""
        long_text = "完整解读。" * 700  # 3500 字，超过 3000 上限
        monkeypatch.setattr(llm_client, "chat_with_tools",
                            lambda messages, tools, temperature=0.7:
                            {"content": long_text, "tool_calls": []})
        result = agent_runtime.run_chat(agent_id=4, message="1994-05-20 14:30 北京",
                                        tools=["star_chart"])
        assert len(result["answer"]) <= settings.llm_answer_max_chars
        assert result["answer"].endswith("。")

    def test_non_star_chart_answer_not_capped(self, monkeypatch, fake_redis):
        """未绑定 star_chart 的智能体不受硬上限约束。"""
        long_text = "很长的回答。" * 2000
        monkeypatch.setattr(llm_client, "chat_with_tools",
                            lambda messages, tools, temperature=0.7:
                            {"content": long_text, "tool_calls": []})
        result = agent_runtime.run_chat(agent_id=1, message="讲个故事",
                                        tools=["calculator"])
        assert len(result["answer"]) == len(long_text)

    def test_trim_text_sentence_boundary(self):
        """trim_text 在句子边界收尾，不腰斩句子。"""
        from app.utils import trim_text
        text = "句子。" * 20  # 60 字
        cut = trim_text(text, 30)
        assert len(cut) <= 30
        assert cut.endswith("。")

    def test_model_name_reaches_llm_client(self, monkeypatch, fake_redis):
        """run_chat 的 model_name 透传至 LLM 客户端（Agent 绑定模型生效）。"""
        captured = {}

        class FakeLLMClient:
            def __init__(self, provider=None, model=None):
                captured["provider"] = provider
                captured["model"] = model

            def chat(self, messages, temperature=0.7):
                return "绑定模型回答"

            def chat_with_tools(self, messages, tools, temperature=0.7):
                return {"content": "绑定模型回答", "tool_calls": []}

        monkeypatch.setattr(agent_runtime, "LLMClient", FakeLLMClient)
        result = agent_runtime.run_chat(agent_id=1, message="你好", model_name="qwen3-max")
        assert result["answer"] == "绑定模型回答"
        assert captured["model"] == "qwen3-max"
        assert captured["provider"] is None

    def test_llm_decides_tool_then_summarizes(self, monkeypatch, fake_redis):
        """LLM 决策调用 calculator → 执行回填 → LLM 总结，answer 为总结文本。"""
        calls = []
        responses = [
            {"content": "", "tool_calls": [{"name": "calculator",
                                            "arguments": {"expression": "2 + 3 * 4"}}]},
            {"content": "计算结果为 14", "tool_calls": []},
        ]
        monkeypatch.setattr(llm_client, "chat_with_tools",
                            _fake_llm_with_tools(responses, calls))
        result = agent_runtime.run_chat(agent_id=1, message="帮我算 2+3*4", tools=["calculator"])
        assert result["answer"] == "计算结果为 14"
        assert len(result["toolCalls"]) == 1
        assert "calculator" in result["toolCalls"][0]
        assert "14" in result["toolCalls"][0]  # 整数运算结果为 14（int）
        # 协议：第二次调用时消息序列包含 tool 结果消息
        second_messages = calls[1][0]
        assert any('"role": "tool"' in m for m in second_messages)

    def test_tool_failure_does_not_break_chain(self, monkeypatch, fake_redis):
        """工具执行失败 → 失败说明回填，LLM 继续总结（主链路不受影响）。"""
        def boom(*a, **k):
            raise RuntimeError("GitHub API 不可用")

        monkeypatch.setattr(tool_registry, "call_tool", boom)
        calls = []
        responses = [
            {"content": "", "tool_calls": [{"name": "github", "arguments": {"repo": "a/b"}}]},
            {"content": "仓库查询失败，但我会继续回答", "tool_calls": []},
        ]
        monkeypatch.setattr(llm_client, "chat_with_tools",
                            _fake_llm_with_tools(responses, calls))
        result = agent_runtime.run_chat(agent_id=1, message="查一下 a/b", tools=["github"])
        assert result["answer"] == "仓库查询失败，但我会继续回答"
        assert "调用失败" in result["toolCalls"][0]

    def test_max_rounds_terminates(self, monkeypatch, fake_redis):
        """模型一直要调工具 → 轮数上限后强制无工具总结，不死循环。"""
        calls = []
        responses = [
            {"content": "", "tool_calls": [{"name": "current_time", "arguments": {}}]}
        ] * 10  # 永远要工具
        monkeypatch.setattr(llm_client, "chat_with_tools",
                            _fake_llm_with_tools(responses, calls))
        monkeypatch.setattr(llm_client, "chat",
                            lambda messages, temperature=0.7: "强制总结")
        result = agent_runtime.run_chat(agent_id=1, message="现在几点", tools=["current_time"])
        assert result["answer"] == "强制总结"
        assert len(calls) <= agent_runtime.MAX_TOOL_ROUNDS + 1  # 上限内终止

    def test_rule_fallback_when_llm_ignores_tools(self, monkeypatch, fake_redis):
        """LLM 未决策工具但规则命中（数学表达式）→ 规则兜底执行并重新总结。"""
        calls = []
        monkeypatch.setattr(llm_client, "chat_with_tools",
                            _fake_llm_with_tools(
                                [{"content": "我不用工具", "tool_calls": []}], calls))
        monkeypatch.setattr(llm_client, "chat",
                            lambda messages, temperature=0.7: "根据计算，答案是 4")
        result = agent_runtime.run_chat(agent_id=1, message="2 + 2",
                                        tools=["calculator"])
        assert result["answer"] == "根据计算，答案是 4"
        assert len(result["toolCalls"]) == 1
        assert "4" in result["toolCalls"][0]

    def test_mock_mode_rule_fallback(self, monkeypatch, fake_redis, mock_mode):
        """Mock 模式（LLM 不可用）：规则兜底仍执行工具并记录调用。"""
        result = agent_runtime.run_chat(agent_id=1, message="3 * 7", tools=["calculator"])
        assert len(result["toolCalls"]) == 1
        assert "21" in result["toolCalls"][0]
        assert "【Mock 模式】" in result["answer"]

    def test_no_tools_plain_chat(self, monkeypatch, fake_redis, mock_mode):
        """未启用工具 → 普通对话，无工具调用记录。"""
        result = agent_runtime.run_chat(agent_id=1, message="你好")
        assert result["toolCalls"] == []
        assert "【Mock 模式】" in result["answer"]

    def test_rule_not_fire_without_enabled_tools(self, monkeypatch, fake_redis, mock_mode):
        """规则匹配但工具未启用 → 不调用工具。"""
        result = agent_runtime.run_chat(agent_id=1, message="2+2")
        assert result["toolCalls"] == []


# ---------------- 流式工具事件 ----------------

class TestStreamToolEvents:
    def test_stream_emits_tool_and_delta_events(self, monkeypatch, fake_redis, mock_mode):
        """流式：工具轮执行 → tool 事件；总结轮 → delta 事件；done 汇总。"""
        tool_call_rounds = 1  # 仅第一轮要工具，后续轮直接输出文本（贴近真实行为）

        async def fake_stream_with_tools(messages, tools, temperature=0.7):
            nonlocal tool_call_rounds
            if tool_call_rounds > 0:
                tool_call_rounds -= 1
                yield {"type": "done", "content": "",
                       "tool_calls": [{"name": "calculator", "arguments": {"expression": "2+2"}}]}
            else:
                for chunk in ["结果", "是 4"]:
                    yield {"type": "delta", "content": chunk}
                yield {"type": "done", "content": "结果是 4", "tool_calls": []}

        async def fake_stream(messages, temperature=0.7):
            for chunk in ["计算", "结果", "是 4"]:
                yield chunk

        monkeypatch.setattr(llm_client, "chat_stream_with_tools", fake_stream_with_tools)
        monkeypatch.setattr(llm_client, "chat_stream", fake_stream)

        async def collect():
            return [event async for event in agent_runtime.stream_chat(
                agent_id=1, message="2+2", tools=["calculator"])]

        import asyncio
        events = asyncio.run(collect())
        types = [e["type"] for e in events]
        assert "tool" in types
        tool_event = next(e for e in events if e["type"] == "tool")
        assert tool_event["name"] == "calculator"
        assert "4" in tool_event["result"]
        done = events[-1]
        assert done["type"] == "done"
        assert done["answer"] == "结果是 4"
        assert "calculator" in done["toolCalls"][0]

    def test_stream_rule_fallback_on_empty_output(self, monkeypatch, fake_redis, mock_mode):
        """流式 LLM 无任何输出且规则命中 → 规则兜底执行并补一段回答。"""
        async def fake_stream_with_tools(messages, tools, temperature=0.7):
            yield {"type": "done", "content": "", "tool_calls": []}  # LLM 空输出（决策失败特征）

        async def fake_stream(messages, temperature=0.7):
            yield "根据计算，5 + 5 = 10"

        monkeypatch.setattr(llm_client, "chat_stream_with_tools", fake_stream_with_tools)
        monkeypatch.setattr(llm_client, "chat_stream", fake_stream)

        async def collect():
            return [event async for event in agent_runtime.stream_chat(
                agent_id=1, message="5 + 5", tools=["calculator"])]

        import asyncio
        events = asyncio.run(collect())
        assert any(e["type"] == "tool" for e in events)
        tool_event = next(e for e in events if e["type"] == "tool")
        assert "10" in tool_event["result"]


# ---------------- 记忆按用户隔离 ----------------

class TestMemoryIsolation:
    def test_key_includes_user(self, fake_redis):
        memory.append_round(1, 100, "你好", "你好呀")
        assert "memory:agent:1:user:100" in fake_redis.data
        history = memory.get_history(1, 100)
        assert history == [{"role": "user", "content": "你好"},
                           {"role": "assistant", "content": "你好呀"}]
        # 其他用户隔离
        assert memory.get_history(1, 200) == []

    def test_legacy_key_without_user(self, fake_redis):
        memory.append_round(1, None, "hi", "hello")
        assert "memory:agent:1" in fake_redis.data

    def test_append_round_trim_and_ttl(self, fake_redis, monkeypatch):
        monkeypatch.setattr(settings, "memory_rounds", 2)
        for i in range(4):
            memory.append_round(1, 100, f"u{i}", f"a{i}")
        history = memory.get_history(1, 100)
        assert len(history) == settings.memory_rounds * 2  # 裁剪至最近 2 轮
        assert history[0]["content"] == "u2"
        assert "memory:agent:1:user:100" in fake_redis.expired  # TTL 已刷新

    def test_run_chat_writes_memory(self, monkeypatch, fake_redis, mock_mode):
        agent_runtime.run_chat(agent_id=1, message="你好", user_id=100)
        history = memory.get_history(1, 100)
        assert history[-2]["content"] == "你好"  # user 消息
        assert history[-1]["role"] == "assistant"
        # 未传 userId 不写记忆（兼容旧调用方）
        agent_runtime.run_chat(agent_id=1, message="你好")
        assert "memory:agent:1" not in fake_redis.data

    def test_memory_injected_and_deduped(self, monkeypatch, fake_redis, mock_mode):
        """记忆注入系统提示词；与 MySQL 历史重复的条目被去重。"""
        memory.append_round(1, 100, "跨会话问题", "跨会话回答")
        messages, _, _ = agent_runtime.prepare_chat(
            agent_id=1, message="新问题", user_id=100,
            history=[{"role": "user", "content": "新问题"}])
        assert "近期记忆" in messages[0]["content"]
        assert "跨会话问题" in messages[0]["content"]

        # 历史中已有同内容 → 不重复注入
        messages, _, _ = agent_runtime.prepare_chat(
            agent_id=1, message="跨会话问题", user_id=100,
            history=[{"role": "user", "content": "跨会话问题"},
                     {"role": "assistant", "content": "跨会话回答"}])
        assert "近期记忆" not in messages[0]["content"]

    def test_redis_down_degrades(self, monkeypatch, mock_mode):
        """Redis 不可用 → 记忆读写降级为空，对话不受影响。"""
        monkeypatch.setattr(memory, "_get_redis", lambda: None)
        result = agent_runtime.run_chat(agent_id=1, message="你好", user_id=100)
        assert result["answer"]  # 主链路正常
        assert memory.get_history(1, 100) == []
