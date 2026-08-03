package com.agentforge.conversation.vo;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * 聊天出参：回答 + RAG 来源 + 工具调用记录。
 */
@Data
@Builder
public class ChatVO {

    /** 助手回答 */
    private String answer;

    /** 引用来源文件名列表 */
    private List<String> sources;

    /** 工具调用记录 */
    private List<String> toolCalls;
}
