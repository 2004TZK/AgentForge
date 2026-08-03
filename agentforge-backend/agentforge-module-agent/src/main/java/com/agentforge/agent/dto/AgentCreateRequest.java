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

    /** 默认模型，缺省 deepseek-chat */
    private String modelName = "deepseek-chat";

    /** 采样温度 0-1，缺省 0.70 */
    @DecimalMin(value = "0", message = "temperature 需在 0-1 之间")
    @DecimalMax(value = "1", message = "temperature 需在 0-1 之间")
    private BigDecimal temperature = new BigDecimal("0.70");

    /** 工具配置列表 */
    @Valid
    private List<ToolConfigRequest> tools = new ArrayList<>();
}
