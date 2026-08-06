package com.agentforge.aigateway.dto;

import lombok.Builder;
import lombok.Data;

/**
 * AI 服务自定义工具测试响应。
 */
@Data
@Builder
public class AiToolTestResponse {

    private boolean ok;

    private Object result;

    private String stdout;

    private String error;

    private long durationMs;
}
