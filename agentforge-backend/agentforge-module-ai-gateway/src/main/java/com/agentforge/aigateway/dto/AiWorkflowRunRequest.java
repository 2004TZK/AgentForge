package com.agentforge.aigateway.dto;

import lombok.Builder;
import lombok.Data;

import java.util.HashMap;
import java.util.Map;

/**
 * AI 服务 /agent/workflow/run 请求（定义 JSON + 输入变量）。
 * 流程定义由后端从 workflow_node 表组装后透传（AI 服务不直连 MySQL）。
 */
@Data
@Builder
public class AiWorkflowRunRequest {

    /** 流程定义 {"nodes": [{nodeKey, type, params, next}]} */
    private Map<String, Object> definition;

    /** 运行输入变量 {key: value} */
    @Builder.Default
    private Map<String, Object> input = new HashMap<>();
}
