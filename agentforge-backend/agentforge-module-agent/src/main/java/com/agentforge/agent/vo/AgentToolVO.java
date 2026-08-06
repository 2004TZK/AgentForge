package com.agentforge.agent.vo;

import lombok.Builder;
import lombok.Data;

import java.util.Map;

/**
 * 工具配置出参。
 */
@Data
@Builder
public class AgentToolVO {

    private String toolName;

    /** 工具来源（M5）：builtin / custom */
    private String toolSource;

    /** 自定义工具定义 ID（toolSource=custom 时） */
    private Long toolDefinitionId;

    private Map<String, Object> toolConfig;

    private Boolean enabled;
}
