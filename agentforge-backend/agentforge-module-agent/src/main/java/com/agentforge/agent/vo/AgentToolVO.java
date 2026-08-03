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

    private Map<String, Object> toolConfig;

    private Boolean enabled;
}
