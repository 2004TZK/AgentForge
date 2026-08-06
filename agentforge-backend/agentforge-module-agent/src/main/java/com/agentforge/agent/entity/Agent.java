package com.agentforge.agent.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 智能体实体，对应表 `agent`。
 */
@Data
@TableName("`agent`")
public class Agent {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 智能体名称 */
    private String name;

    /** 描述 */
    private String description;

    /** 系统提示词 */
    private String systemPrompt;

    /** 默认模型 */
    private String modelName;

    /** 模型 Provider ID（M4：NULL=内置千问云端，回落 AI 服务环境变量） */
    private Long providerId;

    /** 采样温度 */
    private BigDecimal temperature;

    /** 运行模式（M3）：chat 对话模式 / workflow 工作流模式 */
    private String mode;

    /** 绑定的工作流 ID（mode=workflow 时生效） */
    private Long workflowId;

    /** 可见性（M4）：PUBLIC 公开 / PRIVATE 私有（仅创建者可见），缺省 PRIVATE */
    private String visibility;

    /** 创建者 ID */
    private Long creatorId;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
