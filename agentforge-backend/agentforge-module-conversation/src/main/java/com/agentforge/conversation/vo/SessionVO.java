package com.agentforge.conversation.vo;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 会话出参。
 */
@Data
@Builder
public class SessionVO {

    private Long id;

    /** 所属智能体 ID */
    private Long agentId;

    /** 会话名称 */
    private String name;

    private LocalDateTime createdTime;

    /** 最后活跃时间（列表按此倒序） */
    private LocalDateTime updatedTime;
}
