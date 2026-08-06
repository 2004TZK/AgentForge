package com.agentforge.agent.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.Map;

/**
 * 工具配置入参（单条）。
 */
@Data
public class ToolConfigRequest {

    /** 工具名：calculator / github / 自定义工具名 */
    @NotBlank(message = "工具名不能为空")
    private String toolName;

    /** 工具来源（M5）：builtin=内置注册表 / custom=自定义工具定义，缺省 builtin */
    private String toolSource = "builtin";

    /** 自定义工具定义 ID（toolSource=custom 时必填） */
    private Long toolDefinitionId;

    /** 工具参数配置（任意 JSON） */
    private Map<String, Object> toolConfig;

    /** 是否启用，默认启用 */
    private Boolean enabled = true;
}
