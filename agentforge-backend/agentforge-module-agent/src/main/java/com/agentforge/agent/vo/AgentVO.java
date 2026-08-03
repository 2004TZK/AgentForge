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

    /** 运行模式（M3）：chat / workflow */
    private String mode;

    /** 绑定的工作流 ID（mode=workflow 时生效） */
    private Long workflowId;

    /** 创建者 ID */
    private Long creatorId;

    private LocalDateTime createdTime;
}
