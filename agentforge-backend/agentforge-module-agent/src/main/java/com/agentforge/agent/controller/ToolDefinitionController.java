package com.agentforge.agent.controller;

import com.agentforge.agent.dto.ToolDefinitionRequest;
import com.agentforge.agent.dto.ToolTestRequest;
import com.agentforge.agent.service.ToolDefinitionService;
import com.agentforge.agent.vo.ToolDefinitionVO;
import com.agentforge.agent.vo.ToolTestResult;
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
 * 用户自定义工具定义接口（工具定义开发文档 v3.0 §7 阶段一）。
 * CRUD + 复制 + 测试；权限（PRIVATE 仅创建者 / PUBLIC 所有人可见但密钥脱敏）。
 */
@Tag(name = "自定义工具")
@Validated
@RestController
@RequestMapping("/tool-definitions")
@RequiredArgsConstructor
public class ToolDefinitionController {

    private final ToolDefinitionService toolDefinitionService;

    @Operation(summary = "分页查询自定义工具（本人 + 公开）")
    @GetMapping("/page")
    public Result<PageResult<ToolDefinitionVO>> page(
            @RequestParam(defaultValue = "1") @Min(value = 1, message = "page 需 >= 1") long page,
            @RequestParam(defaultValue = "10") @Min(value = 1) @Max(value = 100, message = "size 需 <= 100") long size,
            @RequestParam(required = false) String keyword) {
        return Result.success(toolDefinitionService.page(page, size, keyword, UserContext.getUserId()));
    }

    @Operation(summary = "自定义工具详情（密钥脱敏）")
    @GetMapping("/{id}")
    public Result<ToolDefinitionVO> detail(@PathVariable Long id) {
        return Result.success(toolDefinitionService.detail(id, UserContext.getUserId()));
    }

    @Operation(summary = "创建自定义工具")
    @PostMapping
    public Result<ToolDefinitionVO> create(@Valid @RequestBody ToolDefinitionRequest request) {
        return Result.success(toolDefinitionService.create(request, UserContext.getUserId()));
    }

    @Operation(summary = "更新自定义工具（仅创建者）")
    @PutMapping("/{id}")
    public Result<ToolDefinitionVO> update(@PathVariable Long id,
                                           @Valid @RequestBody ToolDefinitionRequest request) {
        return Result.success(toolDefinitionService.update(id, request, UserContext.getUserId()));
    }

    @Operation(summary = "删除自定义工具（仅创建者）")
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        toolDefinitionService.delete(id, UserContext.getUserId());
        return Result.success();
    }

    @Operation(summary = "复制自定义工具到本人工具库")
    @PostMapping("/{id}/copy")
    public Result<ToolDefinitionVO> copy(@PathVariable Long id) {
        return Result.success(toolDefinitionService.copy(id, UserContext.getUserId()));
    }

    @Operation(summary = "复制系统内置工具为本人可编辑副本（tool_type=builtin）")
    @PostMapping("/from-builtin/{name}")
    public Result<ToolDefinitionVO> copyFromBuiltin(@PathVariable String name) {
        return Result.success(toolDefinitionService.copyBuiltin(name, UserContext.getUserId()));
    }

    @Operation(summary = "测试自定义工具（HTTP 直发 / 代码进沙箱真实执行）")
    @PostMapping("/test")
    public Result<ToolTestResult> test(@Valid @RequestBody ToolTestRequest request) {
        return Result.success(toolDefinitionService.test(request, UserContext.getUserId()));
    }
}
