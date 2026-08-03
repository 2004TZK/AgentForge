package com.agentforge.agent.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Agent 工具配置实体，对应表 `agent_tool`。
 * tool_config 为 JSON 列，经 JacksonTypeHandler 与 Map 互转。
 */
@Data
@TableName(value = "`agent_tool`", autoResultMap = true)
public class AgentTool {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 智能体 ID */
    private Long agentId;

    /** 工具名：calculator / github */
    private String toolName;

    /** 工具参数配置（JSON） */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> toolConfig;

    /** 是否启用 */
    private Boolean enabled;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
