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

    /** 采样温度 */
    private BigDecimal temperature;

    /** 创建者 ID */
    private Long creatorId;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
