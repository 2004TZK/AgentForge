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
 * 创建 Agent 入参。
 */
@Data
public class AgentCreateRequest {

    @NotBlank(message = "智能体名称不能为空")
    @Size(max = 100, message = "智能体名称长度不能超过 100")
    private String name;

    @Size(max = 500, message = "描述长度不能超过 500")
    private String description;

    @NotBlank(message = "系统提示词不能为空")
    private String systemPrompt;

    /** 默认模型，缺省 qwen3.7-plus（千问云端） */
    private String modelName = "qwen3.7-plus";

    /** 模型 Provider ID（M4：NULL=内置千问云端，回落 AI 服务环境变量） */
    private Long providerId;

    /** 采样温度 0-1，缺省 0.70 */
    @DecimalMin(value = "0", message = "temperature 需在 0-1 之间")
    @DecimalMax(value = "1", message = "temperature 需在 0-1 之间")
    private BigDecimal temperature = new BigDecimal("0.70");

    /** 工具配置列表 */
    @Valid
    private List<ToolConfigRequest> tools = new ArrayList<>();

    /** 运行模式（M3）：chat / workflow，缺省 chat */
    private String mode = "chat";

    /** 绑定的工作流 ID（mode=workflow 时生效） */
    private Long workflowId;

    /** 可见性（M4）：PUBLIC / PRIVATE（仅创建者可见），缺省 PRIVATE */
    private String visibility = "PRIVATE";
}
