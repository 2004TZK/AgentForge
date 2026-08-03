package com.agentforge.aigateway.dto;

import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * AI 服务 /agent/chat 请求。
 * agentId + message + history 为核心字段；
 * systemPrompt/modelName/temperature/tools 为 Agent 配置快照，
 * 由后端从 MySQL 加载后透传（AI 服务不直连 MySQL）。
 */
@Data
@Builder
public class AiChatRequest {

    private Long agentId;

    private String message;

    /** 最近 N 轮对话历史（role: user/assistant） */
    private List<ChatHistoryItem> history = new ArrayList<>();

    /** 系统提示词 */
    private String systemPrompt;

    /** 模型名 */
    private String modelName;

    /** 采样温度 */
    private BigDecimal temperature;

    /** 启用的工具列表（工具名） */
    private List<String> tools = new ArrayList<>();
}
