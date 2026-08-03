package com.agentforge.conversation.entity;

import com.agentforge.aigateway.dto.AiSourceItem;
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
 * 对话记录实体，对应表 `conversation`（一问一答一行）。
 * M2 起按会话隔离：sessionId 为空表示旧版遗留数据。
 */
@Data
@TableName(value = "`conversation`", autoResultMap = true)
public class Conversation {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 智能体 ID */
    private Long agentId;

    /** 用户 ID */
    private Long userId;

    /** 会话 ID（NULL=旧版数据，不参与会话隔离） */
    private Long sessionId;

    /** 用户消息 */
    private String userMessage;

    /** 助手回复 */
    private String assistantMessage;

    /** 引用来源（M2 起；JSON 存储，旧数据为 NULL） */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<AiSourceItem> sources;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
