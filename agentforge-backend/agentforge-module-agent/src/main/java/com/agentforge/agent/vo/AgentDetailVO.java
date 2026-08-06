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

    /** 模型 Provider ID（M4：NULL=内置千问云端，回落 AI 服务环境变量） */
    private Long providerId;

    private BigDecimal temperature;

    /** 运行模式（M3）：chat / workflow */
    private String mode;

    /** 绑定的工作流 ID（mode=workflow 时生效） */
    private Long workflowId;

    /** 可见性（M4）：PUBLIC 公开 / PRIVATE 私有（仅创建者可见） */
    private String visibility;

    private Long creatorId;

    private LocalDateTime createdTime;

    private List<AgentToolVO> tools;
}
