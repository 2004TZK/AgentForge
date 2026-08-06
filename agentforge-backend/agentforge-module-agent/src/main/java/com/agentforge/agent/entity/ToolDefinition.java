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
 * 用户自定义工具定义，对应表 `tool_definition`（工具定义开发文档 v3.0 §5.1）。
 *
 * <p>http_config / script_config 中的密钥字段入库前经 AES-GCM 加密（enc:v1: 前缀），
 * 详情返回一律脱敏为掩码；parameters 为 LLM 调用参数 Schema（OpenAI function parameters）。
 */
@Data
@TableName(value = "`tool_definition`", autoResultMap = true)
public class ToolDefinition {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 创建者 ID */
    private Long creatorId;

    /** 工具名（用户级唯一，供 LLM 调用） */
    private String name;

    /** 展示名称 */
    private String displayName;

    /** 给 LLM 看的工具描述 */
    private String description;

    /** http / script */
    private String toolType;

    /** LLM 调用参数 Schema（OpenAI function parameters） */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> parameters;

    /** HTTP 请求定义（tool_type=http；密钥字段已加密） */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> httpConfig;

    /** 代码定义（tool_type=script） */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> scriptConfig;

    /** PRIVATE / PUBLIC */
    private String visibility;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
