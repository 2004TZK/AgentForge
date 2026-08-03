package com.agentforge.conversation.vo;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 对话记录出参。
 */
@Data
@Builder
public class ConversationVO {

    private Long id;

    private Long agentId;

    private String userMessage;

    private String assistantMessage;

    private LocalDateTime createdTime;
}
