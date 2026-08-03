package com.agentforge.model.controller;

import com.agentforge.common.core.Result;
import com.agentforge.framework.context.UserContext;
import com.agentforge.model.dto.ProviderRequest;
import com.agentforge.model.service.ModelProviderService;
import com.agentforge.model.vo.ProviderVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 模型 Provider 接口（M4 多模型配置）：列表 / 创建 / 更新 / 删除。
 */
@Tag(name = "模型 Provider")
@Validated
@RestController
@RequestMapping("/model/providers")
@RequiredArgsConstructor
public class ModelProviderController {

    private final ModelProviderService providerService;

    @Operation(summary = "Provider 列表（系统内置 + 本人创建）")
    @GetMapping
    public Result<List<ProviderVO>> list() {
        return Result.success(providerService.list(UserContext.getUserId()));
    }

    @Operation(summary = "创建 Provider")
    @PostMapping
    public Result<ProviderVO> create(@Valid @RequestBody ProviderRequest request) {
        return Result.success(providerService.create(request, UserContext.getUserId()));
    }

    @Operation(summary = "更新 Provider（仅创建者，内置不可改）")
    @PutMapping("/{id}")
    public Result<ProviderVO> update(@PathVariable Long id,
                                     @Valid @RequestBody ProviderRequest request) {
        return Result.success(providerService.update(id, request, UserContext.getUserId()));
    }

    @Operation(summary = "删除 Provider（仅创建者，内置不可删）")
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        providerService.delete(id, UserContext.getUserId());
        return Result.success();
    }
}
