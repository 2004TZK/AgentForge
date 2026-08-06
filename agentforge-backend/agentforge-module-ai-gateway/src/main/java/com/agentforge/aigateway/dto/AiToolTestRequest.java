package com.agentforge.aigateway.dto;

import lombok.Builder;
import lombok.Data;

import java.util.Map;

/**
 * AI 服务自定义工具测试请求：POST /agent/tools/test。
 * 定义 + 示例参数 → AI 服务直接执行（HTTP 工具发请求 / 代码工具进沙箱）。
 */
@Data
@Builder
public class AiToolTestRequest {

    /** http / script */
    private String toolType;

    private Map<String, Object> httpConfig;

    private Map<String, Object> scriptConfig;

    private Map<String, Object> parameters;

    private Map<String, Object> args;
}
