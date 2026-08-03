"""工作流接口：POST /agent/workflow/run（流程定义 → LangGraph 编译执行 → 节点日志）。"""
from fastapi import APIRouter, Depends

from app.api.deps import require_internal_token
from app.schemas.workflow import WorkflowRunRequest, WorkflowRunResponse
from app.services import workflow_engine

router = APIRouter(prefix="/agent", tags=["workflow"],
                   dependencies=[Depends(require_internal_token)])


@router.post("/workflow/run", response_model=WorkflowRunResponse)
def run_workflow(request: WorkflowRunRequest) -> WorkflowRunResponse:
    """执行工作流：定义 + 输入 → {status, output, nodeLogs, error}。"""
    result = workflow_engine.execute_workflow(request.definition.model_dump(),
                                              request.input)
    return WorkflowRunResponse(**result)
