package com.agentforge.agent.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.Map;

/**
 * 工具配置入参（单条）。
 */
@Data
public class ToolConfigRequest {

    /** 工具名：calculator / github */
    @NotBlank(message = "工具名不能为空")
    private String toolName;

    /** 工具参数配置（任意 JSON） */
    private Map<String, Object> toolConfig;

    /** 是否启用，默认启用 */
    private Boolean enabled = true;
}
