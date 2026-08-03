package com.agentforge.workflow.controller;

import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.Result;
import com.agentforge.framework.context.UserContext;
import com.agentforge.workflow.dto.WorkflowCreateRequest;
import com.agentforge.workflow.dto.WorkflowRunRequest;
import com.agentforge.workflow.service.WorkflowService;
import com.agentforge.workflow.vo.WorkflowRunVO;
import com.agentforge.workflow.vo.WorkflowVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 工作流接口（M3 Workflow v1）：定义 CRUD / 触发运行 / 运行日志。
 * 仅创建者可见与操作；运行经 AI 服务 LangGraph 引擎执行。
 */
@Tag(name = "工作流")
@Validated
@RestController
@RequestMapping("/workflows")
@RequiredArgsConstructor
public class WorkflowController {

    private final WorkflowService workflowService;

    @Operation(summary = "创建工作流")
    @PostMapping
    public Result<WorkflowVO> create(@Valid @RequestBody WorkflowCreateRequest request) {
        return Result.success(workflowService.create(request, UserContext.getUserId()));
    }

    @Operation(summary = "更新工作流（节点整体替换）")
    @PutMapping("/{id}")
    public Result<WorkflowVO> update(@PathVariable Long id,
                                     @Valid @RequestBody WorkflowCreateRequest request) {
        return Result.success(workflowService.update(id, request, UserContext.getUserId()));
    }

    @Operation(summary = "工作流详情（含节点）")
    @GetMapping("/{id}")
    public Result<WorkflowVO> detail(@PathVariable Long id) {
        return Result.success(workflowService.detail(id, UserContext.getUserId()));
    }

    @Operation(summary = "我的工作流分页")
    @GetMapping
    public Result<PageResult<WorkflowVO>> page(
            @RequestParam(defaultValue = "1") @Min(value = 1, message = "page 需 >= 1") long page,
            @RequestParam(defaultValue = "20") @Min(value = 1) @Max(value = 100, message = "size 需 <= 100") long size) {
        return Result.success(workflowService.page(page, size, UserContext.getUserId()));
    }

    @Operation(summary = "删除工作流")
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        workflowService.delete(id, UserContext.getUserId());
        return Result.success();
    }

    @Operation(summary = "触发运行（输入为模板变量）")
    @PostMapping("/{id}/run")
    public Result<WorkflowRunVO> run(@PathVariable Long id,
                                     @RequestBody(required = false) WorkflowRunRequest request) {
        WorkflowRunRequest effective = request == null ? new WorkflowRunRequest() : request;
        return Result.success(workflowService.run(id, effective, UserContext.getUserId()));
    }

    @Operation(summary = "运行记录详情（含节点级日志）")
    @GetMapping("/runs/{runId}")
    public Result<WorkflowRunVO> runDetail(@PathVariable Long runId) {
        return Result.success(workflowService.getRun(runId, UserContext.getUserId()));
    }

    @Operation(summary = "工作流运行记录分页")
    @GetMapping("/{id}/runs")
    public Result<PageResult<WorkflowRunVO>> runs(
            @PathVariable Long id,
            @RequestParam(defaultValue = "1") @Min(value = 1, message = "page 需 >= 1") long page,
            @RequestParam(defaultValue = "20") @Min(value = 1) @Max(value = 100, message = "size 需 <= 100") long size) {
        return Result.success(workflowService.listRuns(id, page, size, UserContext.getUserId()));
    }
}
