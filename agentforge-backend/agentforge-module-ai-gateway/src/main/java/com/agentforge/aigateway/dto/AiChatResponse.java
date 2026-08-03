package com.agentforge.aigateway.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/**
 * AI 服务 /agent/chat 响应。
 * Phase 1 为同步 JSON；Phase 3 起演进 SSE 流式透传。
 */
@Data
public class AiChatResponse {

    /** 助手回答 */
    private String answer;

    /** 引用的来源文件名列表（RAG） */
    private List<String> sources = new ArrayList<>();

    /** 工具调用记录列表（Phase 4） */
    private List<String> toolCalls = new ArrayList<>();
}
