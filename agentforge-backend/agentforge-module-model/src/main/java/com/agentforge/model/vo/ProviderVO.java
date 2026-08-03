package com.agentforge.model.vo;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 模型 Provider 出参（列表/详情；内置 provider 的 apiKey 为空）。
 */
@Data
@Builder
public class ProviderVO {

    private Long id;

    private String name;

    /** ollama（本地原生）/ openai（OpenAI 兼容） */
    private String providerType;

    private String baseUrl;

    /** API Key（已配置时回显，本地模型为空） */
    private String apiKey;

    /** 可用模型列表 */
    private List<String> models;

    private Boolean enabled;

    /** 创建者 ID（0=系统内置） */
    private Long creatorId;

    private LocalDateTime createdTime;
}
