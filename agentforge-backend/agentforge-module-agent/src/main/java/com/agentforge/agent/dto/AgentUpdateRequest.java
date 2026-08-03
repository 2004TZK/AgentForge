package com.agentforge.agent.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 更新 Agent 入参（整体覆盖：基础信息 + 工具配置）。
 */
@Data
public class AgentUpdateRequest {

    @NotBlank(message = "智能体名称不能为空")
    @Size(max = 100, message = "智能体名称长度不能超过 100")
    private String name;

    @Size(max = 500, message = "描述长度不能超过 500")
    private String description;

    @NotBlank(message = "系统提示词不能为空")
    private String systemPrompt;

    private String modelName = "deepseek-chat";

    /** 模型 Provider ID（M4：NULL=内置 Ollama） */
    private Long providerId;

    @DecimalMin(value = "0", message = "temperature 需在 0-1 之间")
    @DecimalMax(value = "1", message = "temperature 需在 0-1 之间")
    private BigDecimal temperature = new BigDecimal("0.70");

    /** 工具配置列表（整体替换） */
    @Valid
    private List<ToolConfigRequest> tools = new ArrayList<>();

    /** 运行模式（M3）：chat / workflow */
    private String mode = "chat";

    /** 绑定的工作流 ID（mode=workflow 时生效） */
    private Long workflowId;

    /** 可见性（M4）：PUBLIC / PRIVATE（仅创建者可见） */
    private String visibility = "PRIVATE";
}
