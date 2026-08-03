package com.agentforge.conversation.vo;

import com.agentforge.aigateway.dto.AiSourceItem;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

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

    /** 引用来源（同步/流式回答均落库，历史可回溯） */
    private List<AiSourceItem> sources;

    private LocalDateTime createdTime;
}
