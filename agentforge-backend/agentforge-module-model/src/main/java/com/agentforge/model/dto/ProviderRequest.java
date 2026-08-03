package com.agentforge.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/**
 * 创建/更新模型 Provider 入参（M4 多模型配置）。
 */
@Data
public class ProviderRequest {

    @NotBlank(message = "Provider 名称不能为空")
    @Size(max = 100, message = "名称长度不能超过 100")
    private String name;

    /** 类型：ollama（本地原生，think 可控）/ openai（OpenAI 兼容） */
    @NotBlank(message = "Provider 类型不能为空")
    @Pattern(regexp = "ollama|openai", message = "类型仅支持 ollama / openai")
    private String providerType = "ollama";

    @NotBlank(message = "Base URL 不能为空")
    @Size(max = 300, message = "Base URL 长度不能超过 300")
    private String baseUrl;

    /** API Key（本地模型留空） */
    @Size(max = 300, message = "API Key 长度不能超过 300")
    private String apiKey;

    /** 可用模型列表 */
    private List<String> models = new ArrayList<>();

    /** 是否启用 */
    private Boolean enabled = true;
}
