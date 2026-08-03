package com.agentforge.aigateway.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * AI 服务网关配置（application.yml: agentforge.ai.*）。
 * 超时约定（设计 7.3 节）：连接 5s、读取 60s，均可配置。
 */
@Data
@ConfigurationProperties(prefix = "agentforge.ai")
public class AiGatewayProperties {

    /** Python AI Service 基础地址，如 http://localhost:8000 */
    private String baseUrl = "http://localhost:8000";

    /** 内部鉴权 Token（X-Internal-Token 请求头） */
    private String internalToken = "dev-internal-token";

    /** 连接超时（毫秒） */
    private int connectTimeoutMs = 5000;

    /** 读取超时（毫秒） */
    private int readTimeoutMs = 60000;
}
