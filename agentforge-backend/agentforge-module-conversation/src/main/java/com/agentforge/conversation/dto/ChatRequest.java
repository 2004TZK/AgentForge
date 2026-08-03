package com.agentforge.conversation.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 聊天请求入参。
 */
@Data
public class ChatRequest {

    @NotNull(message = "agentId 不能为空")
    private Long agentId;

    /** 会话 ID（M2 多会话；为空时按旧版语义处理，不隔离历史） */
    private Long sessionId;

    @NotBlank(message = "消息内容不能为空")
    @Size(max = 4000, message = "单条消息长度不能超过 4000")
    private String message;
}
