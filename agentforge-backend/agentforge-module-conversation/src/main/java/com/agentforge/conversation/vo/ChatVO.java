package com.agentforge.conversation.vo;

import com.agentforge.aigateway.dto.AiSourceItem;
import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * 聊天出参：回答 + RAG 来源（含片段，M2 起）+ 工具调用记录。
 */
@Data
@Builder
public class ChatVO {

    /** 助手回答 */
    private String answer;

    /** 引用的知识库来源（文件名 + 片段 + 分数） */
    private List<AiSourceItem> sources;

    /** 工具调用记录 */
    private List<String> toolCalls;
}
