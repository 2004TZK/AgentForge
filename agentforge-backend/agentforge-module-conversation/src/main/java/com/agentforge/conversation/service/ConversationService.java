package com.agentforge.conversation.service;

import com.agentforge.common.core.PageResult;
import com.agentforge.conversation.dto.ChatRequest;
import com.agentforge.conversation.vo.ChatVO;
import com.agentforge.conversation.vo.ConversationVO;

/**
 * 对话服务：发送消息（经 AI 服务）与历史查询。
 */
public interface ConversationService {

    /** 发送消息：加载 Agent 配置 → 携带最近历史调 AI → 落库 → 返回回答 */
    ChatVO chat(ChatRequest request, Long userId);

    /** 历史记录分页（按时间倒序，最新在前） */
    PageResult<ConversationVO> history(Long agentId, Long userId, long page, long size);
}
