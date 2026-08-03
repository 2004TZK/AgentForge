package com.agentforge.aigateway.dto;

import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * AI 服务 /agent/chat 请求。
 * agentId + message + history 为核心字段；
 * systemPrompt/modelName/temperature/tools 为 Agent 配置快照，
 * 由后端从 MySQL 加载后透传（AI 服务不直连 MySQL）。
 * M3 起新增 userId（短期记忆按用户隔离）与 toolConfigs（智能体工具配置）。
 */
@Data
@Builder
public class AiChatRequest {

    private Long agentId;

    private String message;

    /** 最近 N 轮对话历史（role: user/assistant） */
    @Builder.Default
    private List<ChatHistoryItem> history = new ArrayList<>();

    /** 系统提示词 */
    private String systemPrompt;

    /** 模型名 */
    private String modelName;

    /** 模型 Provider（M4 多模型配置：{type, baseUrl, apiKey}；null=回落 AI 服务环境变量） */
    private Map<String, Object> provider;

    /** 采样温度 */
    private BigDecimal temperature;

    /** 启用的工具列表（工具名） */
    @Builder.Default
    private List<String> tools = new ArrayList<>();

    /** 用户 ID（M3：Redis 短期记忆按用户隔离） */
    private Long userId;

    /** 智能体工具配置 {tool_name: config}（M3：工具执行时透传） */
    @Builder.Default
    private Map<String, Map<String, Object>> toolConfigs = new HashMap<>();
}
