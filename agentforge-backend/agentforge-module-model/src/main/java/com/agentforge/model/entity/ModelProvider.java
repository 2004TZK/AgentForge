package com.agentforge.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 模型 Provider 配置实体（M4 多模型：本地 Ollama / OpenAI 兼容远端并存）。
 * 对应表 `model_provider`；creator_id=0 为系统内置（不可删除）。
 */
@Data
@TableName(value = "`model_provider`", autoResultMap = true)
public class ModelProvider {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 名称（如 本地 Ollama / DeepSeek 云端） */
    private String name;

    /** 类型：ollama（本地原生 /api/chat，think 可控）/ openai（OpenAI 兼容 /v1/chat/completions） */
    private String providerType;

    /** API 基础地址 */
    private String baseUrl;

    /** API Key（本地模型留空） */
    private String apiKey;

    /** 可用模型列表（JSON 列） */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<String> models;

    /** 是否启用 */
    private Boolean enabled;

    /** 创建者 ID（0=系统内置） */
    private Long creatorId;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
