package com.agentforge.agent.vo;

import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Agent 详情出参（含 systemPrompt 与工具配置，用于编辑页回显）。
 */
@Data
@Builder
public class AgentDetailVO {

    private Long id;

    private String name;

    private String description;

    private String systemPrompt;

    private String modelName;

    private BigDecimal temperature;

    private Long creatorId;

    private LocalDateTime createdTime;

    private List<AgentToolVO> tools;
}
