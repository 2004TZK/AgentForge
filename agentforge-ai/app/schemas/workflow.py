"""Workflow v1 请求/响应模型（与后端 workflow 模块对齐）。"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorkflowNodeDef(BaseModel):
    """流程节点定义。"""
    nodeKey: str = Field(description="节点键（变量引用/日志标识）")
    type: str = Field(description="节点类型 llm/tool")
    params: Dict[str, Any] = Field(default_factory=dict,
                                   description="节点参数（tool 名与 payload / llm 提示词模板）")
    next: Optional[str] = Field(default=None, description="下一节点键（NULL=流程结束）")


class WorkflowDefinition(BaseModel):
    """流程定义（与后端 workflow_node 表对应的 JSON 视图）。"""
    nodes: List[WorkflowNodeDef] = Field(description="节点列表（线性链）")


class WorkflowRunRequest(BaseModel):
    """POST /agent/workflow/run 请求。"""
    definition: WorkflowDefinition = Field(description="流程定义（AI 服务不直连 MySQL）")
    input: Dict[str, Any] = Field(default_factory=dict, description="运行输入变量 {key: value}")


class WorkflowNodeLog(BaseModel):
    """节点级执行日志。"""
    node: str
    type: str
    status: str = Field(description="SUCCESS / FAILED")
    output: str = ""
    error: Optional[str] = None
    durationMs: int = 0


class WorkflowRunResponse(BaseModel):
    """POST /agent/workflow/run 响应。"""
    status: str = Field(description="SUCCESS / FAILED")
    output: str = ""
    nodeLogs: List[WorkflowNodeLog] = Field(default_factory=list)
    error: str = ""
