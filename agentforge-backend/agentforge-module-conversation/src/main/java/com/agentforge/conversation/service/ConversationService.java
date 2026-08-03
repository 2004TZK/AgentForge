package com.agentforge.conversation.service;

import com.agentforge.common.core.PageResult;
import com.agentforge.conversation.dto.ChatRequest;
import com.agentforge.conversation.vo.ChatVO;
import com.agentforge.conversation.vo.ConversationVO;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

/**
 * 对话服务：发送消息（经 AI 服务）、SSE 流式发送与历史查询。
 */
public interface ConversationService {

    /** 发送消息：加载 Agent 配置 → 携带最近历史调 AI → 落库 → 返回回答 */
    ChatVO chat(ChatRequest request, Long userId);

    /**
     * SSE 流式发送：透传 AI 服务原始事件流（delta 增量实时输出），
     * 收到 done 事件时落库；错误转为 SSE error 事件。
     */
    StreamingResponseBody chatStream(ChatRequest request, Long userId);

    /**
     * 历史记录分页（按时间倒序，最新在前）。
     * sessionId 非空时按会话隔离；为空按旧版语义（不隔离）。
     */
    PageResult<ConversationVO> history(Long agentId, Long sessionId, Long userId, long page, long size);
}
