package com.agentforge.agent.vo;

import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Agent 列表/摘要出参（不含 systemPrompt 与工具明细）。
 */
@Data
@Builder
public class AgentVO {

    private Long id;

    private String name;

    private String description;

    private String modelName;

    private BigDecimal temperature;

    /** 创建者 ID */
    private Long creatorId;

    private LocalDateTime createdTime;
}
