package com.agentforge.agent.controller;

import com.agentforge.agent.dto.AgentCreateRequest;
import com.agentforge.agent.dto.AgentUpdateRequest;
import com.agentforge.agent.service.AgentService;
import com.agentforge.agent.vo.AgentDetailVO;
import com.agentforge.agent.vo.AgentVO;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.Result;
import com.agentforge.framework.context.UserContext;
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
 * 智能体接口：分页 / 详情 / 创建 / 更新 / 删除。
 * 只做参数接收与响应包装，业务逻辑在 AgentService。
 */
@Tag(name = "智能体")
@Validated
@RestController
@RequestMapping("/agent")
@RequiredArgsConstructor
public class AgentController {

    private final AgentService agentService;

    @Operation(summary = "分页查询智能体")
    @GetMapping("/page")
    public Result<PageResult<AgentVO>> page(
            @RequestParam(defaultValue = "1") @Min(value = 1, message = "page 需 >= 1") long page,
            @RequestParam(defaultValue = "10") @Min(value = 1) @Max(value = 100, message = "size 需 <= 100") long size,
            @RequestParam(required = false) String name) {
        return Result.success(agentService.page(page, size, name, UserContext.getUserId()));
    }

    @Operation(summary = "智能体详情")
    @GetMapping("/{id}")
    public Result<AgentDetailVO> detail(@PathVariable Long id) {
        return Result.success(agentService.detail(id, UserContext.getUserId()));
    }

    @Operation(summary = "创建智能体")
    @PostMapping
    public Result<AgentDetailVO> create(@Valid @RequestBody AgentCreateRequest request) {
        return Result.success(agentService.create(request, UserContext.getUserId()));
    }

    @Operation(summary = "更新智能体（仅创建者）")
    @PutMapping("/{id}")
    public Result<AgentDetailVO> update(@PathVariable Long id,
                                        @Valid @RequestBody AgentUpdateRequest request) {
        return Result.success(agentService.update(id, request, UserContext.getUserId()));
    }

    @Operation(summary = "删除智能体（仅创建者）")
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        agentService.delete(id, UserContext.getUserId());
        return Result.success();
    }
}
