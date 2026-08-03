package com.agentforge.aigateway.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/**
 * AI 服务 /agent/chat 响应。
 * 同步 JSON 与 SSE 流式（done 事件）共用。
 */
@Data
public class AiChatResponse {

    /** 助手回答 */
    private String answer;

    /** 引用的知识库来源（M2 起含片段，便于前端查看引用内容） */
    private List<AiSourceItem> sources = new ArrayList<>();

    /** 工具调用记录列表（Phase 4） */
    private List<String> toolCalls = new ArrayList<>();
}
