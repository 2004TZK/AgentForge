package com.agentforge.aigateway.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 对话历史单条消息（role: user / assistant）。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ChatHistoryItem {

    private String role;

    private String content;
}
