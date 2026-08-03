package com.agentforge.conversation.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 对话记录实体，对应表 `conversation`（一问一答一行）。
 * Phase 1 单表；Phase 3 演进多会话（conversation_id / 双表）。
 */
@Data
@TableName("`conversation`")
public class Conversation {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 智能体 ID */
    private Long agentId;

    /** 用户 ID */
    private Long userId;

    /** 用户消息 */
    private String userMessage;

    /** 助手回复 */
    private String assistantMessage;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
