"""Workflow v1 引擎测试：定义校验、模板变量、工具/LLM 节点、失败语义、节点日志。

运行：cd agentforge-ai && pytest tests -q
说明：LLM 全部 mock（Mock 模式或 monkeypatch），不依赖外部服务。
"""
import pytest

from app.core.config import settings
from app.services import workflow_engine
from app.services.llm import llm_client


# ---------------- 定义校验 ----------------

class TestValidate:
    def test_minimal_chain(self):
        nodes = workflow_engine.validate_definition({
            "nodes": [
                {"nodeKey": "a", "type": "tool", "params": {}, "next": "b"},
                {"nodeKey": "b", "type": "llm", "params": {}, "next": None},
            ]})
        assert [n["nodeKey"] for n in nodes] == ["a", "b"]

    def test_empty_definition_rejected(self):
        with pytest.raises(ValueError, match="缺少节点"):
            workflow_engine.validate_definition({"nodes": []})

    def test_duplicate_keys_rejected(self):
        with pytest.raises(ValueError, match="重复"):
            workflow_engine.validate_definition({"nodes": [
                {"nodeKey": "a", "type": "tool"},
                {"nodeKey": "a", "type": "llm"},
            ]})

    def test_multi_start_rejected(self):
        with pytest.raises(ValueError, match="一个起点"):
            workflow_engine.validate_definition({"nodes": [
                {"nodeKey": "a", "type": "tool"},
                {"nodeKey": "b", "type": "llm"},
            ]})

    def test_cycle_rejected(self):
        """带入口的环（a→b→c→b）在遍历时被循环检测拦截。"""
        with pytest.raises(ValueError, match="循环"):
            workflow_engine.validate_definition({"nodes": [
                {"nodeKey": "a", "type": "tool", "next": "b"},
                {"nodeKey": "b", "type": "llm", "next": "c"},
                {"nodeKey": "c", "type": "tool", "next": "b"},
            ]})

    def test_unknown_node_type_rejected(self):
        with pytest.raises(ValueError, match="节点类型"):
            workflow_engine.validate_definition({"nodes": [
                {"nodeKey": "a", "type": "notify"},
            ]})


# ---------------- 模板变量 ----------------

class TestTemplate:
    def test_render_basic(self):
        assert workflow_engine._render("star: {stars}", {"stars": "100"}) == "star: 100"

    def test_render_missing_keeps_literal(self):
        assert workflow_engine._render("x={missing}", {}) == "x={missing}"

    def test_render_payload_recursive(self):
        rendered = workflow_engine._render_payload(
            {"repo": "{input_repo}", "nested": {"expr": "{stars} * 2"}},
            {"input_repo": "a/b", "stars": "5"})
        assert rendered == {"repo": "a/b", "nested": {"expr": "5 * 2"}}


# ---------------- 执行 ----------------

class TestExecute:
    def test_tool_chain_with_input_and_cross_ref(self):
        """工具链：输入变量 + 前置节点输出引用（{calc1}），全链路执行。"""
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(workflow_engine.tool_registry, "call_tool",
                            lambda name, payload, config=None: str(eval(payload["expression"])))
        result = workflow_engine.execute_workflow({
            "nodes": [
                {"nodeKey": "calc1", "type": "tool",
                 "params": {"tool": "calculator", "payload": {"expression": "{stars} + 2"}},
                 "next": "calc2"},
                {"nodeKey": "calc2", "type": "tool",
                 "params": {"tool": "calculator", "payload": {"expression": "{calc1} * 2"}},
                 "next": None},
            ]}, {"stars": "100"})
        monkeypatch.undo()
        assert result["status"] == "SUCCESS"
        assert result["output"] == "204"  # (100+2)*2
        logs = result["nodeLogs"]
        assert [log["node"] for log in logs] == ["calc1", "calc2"]
        assert all(log["status"] == "SUCCESS" for log in logs)

    def test_github_repo_workflow(self, monkeypatch):
        """验收示例：查仓库 → 算指标 → 生成报告（github + calculator + llm 三节点）。"""
        def fake_call_tool(name, payload, config=None):
            if name == "github":
                return '{"fullName": "spring-projects/spring-boot", "stars": 76000}'
            return str(eval(payload["expression"]))

        monkeypatch.setattr(workflow_engine.tool_registry, "call_tool", fake_call_tool)
        monkeypatch.setattr(llm_client, "chat",
                            lambda messages, temperature=0.7: "Spring Boot 仓库指标报告：Star 76000")
        result = workflow_engine.execute_workflow({
            "nodes": [
                {"nodeKey": "fetch_repo", "type": "tool",
                 "params": {"tool": "github", "payload": {"repo": "spring-projects/spring-boot"}},
                 "next": "calc_stars"},
                {"nodeKey": "calc_stars", "type": "tool",
                 "params": {"tool": "calculator", "payload": {"expression": "{stars} + 1000"}},
                 "next": "report"},
                {"nodeKey": "report", "type": "llm",
                 "params": {"prompt": "生成报告：仓库 Star 数 {stars}"},
                 "next": None},
            ]}, {"stars": "76000"})
        assert result["status"] == "SUCCESS"
        assert len(result["nodeLogs"]) == 3
        assert result["nodeLogs"][1]["output"] == "77000"

    def test_llm_node_uses_template(self, monkeypatch):
        """LLM 节点：提示词模板注入变量，输出成为最终 output。"""
        calls = []

        def fake_chat(messages, temperature=0.7):
            calls.append((messages, temperature))
            return "报告：Star 数翻倍后为 200"

        monkeypatch.setattr(llm_client, "chat", fake_chat)
        result = workflow_engine.execute_workflow({
            "nodes": [
                {"nodeKey": "report", "type": "llm",
                 "params": {"prompt": "根据数据生成报告：Star 数翻倍后为 {stars}"},
                 "next": None},
            ]}, {"stars": "100"})
        assert result["status"] == "SUCCESS"
        assert result["output"] == "报告：Star 数翻倍后为 200"
        assert calls[0][0][-1]["content"] == "根据数据生成报告：Star 数翻倍后为 100"

    def test_node_failure_fails_run_with_logs(self, monkeypatch):
        """工具节点失败 → 运行 FAILED，节点日志含错误，后续节点不执行。"""
        def boom(name, payload, config=None):
            raise ValueError("GitHub API 不可用")

        monkeypatch.setattr(workflow_engine.tool_registry, "call_tool", boom)
        result = workflow_engine.execute_workflow({
            "nodes": [
                {"nodeKey": "fetch", "type": "tool",
                 "params": {"tool": "github", "payload": {"repo": "a/b"}},
                 "next": "report"},
                {"nodeKey": "report", "type": "llm", "params": {"prompt": "x"}, "next": None},
            ]}, {})
        assert result["status"] == "FAILED"
        assert result["error"] and "GitHub API" in result["error"]
        assert result["nodeLogs"][0]["status"] == "FAILED"
        assert len(result["nodeLogs"]) == 1  # 后续节点未执行

    def test_mock_mode_llm_node(self, monkeypatch):
        """Mock 模式（LLM 不可用）：LLM 节点仍产出 Mock 回答，运行 SUCCESS。"""
        monkeypatch.setattr(settings, "llm_local", False)
        monkeypatch.setattr(llm_client, "base_url", "https://api.example.com")
        result = workflow_engine.execute_workflow({
            "nodes": [
                {"nodeKey": "g", "type": "llm", "params": {"prompt": "你好"}, "next": None},
            ]}, {})
        assert result["status"] == "SUCCESS"
        assert "Mock" in result["output"]
