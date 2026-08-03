package com.agentforge.workflow.service;

import com.agentforge.common.core.PageResult;
import com.agentforge.workflow.dto.WorkflowCreateRequest;
import com.agentforge.workflow.dto.WorkflowRunRequest;
import com.agentforge.workflow.entity.Workflow;
import com.agentforge.workflow.vo.WorkflowRunVO;
import com.agentforge.workflow.vo.WorkflowVO;

import java.util.Map;

/**
 * 工作流服务：定义 CRUD（仅创建者）+ 执行（经 AI 服务 LangGraph 引擎）+ 运行日志。
 */
public interface WorkflowService {

    WorkflowVO create(WorkflowCreateRequest request, Long creatorId);

    WorkflowVO update(Long workflowId, WorkflowCreateRequest request, Long operatorId);

    WorkflowVO detail(Long workflowId, Long userId);

    PageResult<WorkflowVO> page(long page, long size, Long userId);

    void delete(Long workflowId, Long operatorId);

    /** 手动触发运行（input 为模板变量） */
    WorkflowRunVO run(Long workflowId, WorkflowRunRequest request, Long userId);

    /** 对话模式触发运行：以 {message} 为输入、记录触发 Agent */
    WorkflowRunVO runForAgent(Workflow agentWorkflow, Long agentId, String message, Long userId);

    WorkflowRunVO getRun(Long runId, Long userId);

    PageResult<WorkflowRunVO> listRuns(Long workflowId, long page, long size, Long userId);

    /** 加载工作流（不存在/非本人可见时抛异常）；供 Agent 绑定校验复用 */
    Workflow getOwned(Long workflowId, Long userId);
}
