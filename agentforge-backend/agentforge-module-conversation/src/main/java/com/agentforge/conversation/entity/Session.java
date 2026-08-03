package com.agentforge.conversation.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 会话实体，对应表 `session`（M2 多会话）。
 * 同一 Agent 下用户可建多个会话，对话历史按会话隔离。
 */
@Data
@TableName("`session`")
public class Session {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 智能体 ID */
    private Long agentId;

    /** 用户 ID */
    private Long userId;

    /** 会话名称（默认「新会话」，首条消息自动命名） */
    private String name;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
