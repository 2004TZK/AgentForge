package com.agentforge.agent.vo;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 用户自定义工具定义出参。
 * http_config 中密钥字段已脱敏为掩码（不泄露明文；编辑回显留空不修改）。
 */
@Data
@Builder
public class ToolDefinitionVO {

    private Long id;

    private Long creatorId;

    /** 工具名（用户级唯一，供 LLM 调用） */
    private String name;

    private String displayName;

    private String description;

    /** http / script */
    private String toolType;

    /** 内置工具引用（toolType=builtin 时） */
    private String builtinName;

    /** LLM 调用参数 Schema */
    private Map<String, Object> parameters;

    /** HTTP 请求定义（密钥字段脱敏） */
    private Map<String, Object> httpConfig;

    /** 代码定义（code 为明文，无密钥） */
    private Map<String, Object> scriptConfig;

    /** PRIVATE / PUBLIC */
    private String visibility;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
