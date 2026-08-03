package com.agentforge.aigateway.controller;

import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.common.core.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 工具元数据接口：透传 AI 服务 /agent/tools/meta。
 * 前端按 Schema（parameters/config）渲染工具配置表单；后端不重复维护工具定义。
 */
@Tag(name = "工具")
@RestController
@RequestMapping("/tools")
@RequiredArgsConstructor
public class ToolMetaController {

    private final AiServiceClient aiServiceClient;

    @Operation(summary = "工具元数据列表（名称/描述/参数/配置 Schema）")
    @GetMapping("/meta")
    public Result<List<Map<String, Object>>> meta() {
        return Result.success(aiServiceClient.getToolMeta());
    }
}
