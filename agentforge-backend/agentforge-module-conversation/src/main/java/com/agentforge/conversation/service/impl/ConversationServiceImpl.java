package com.agentforge.conversation.service.impl;

import com.agentforge.agent.entity.Agent;
import com.agentforge.agent.entity.AgentTool;
import com.agentforge.agent.mapper.AgentMapper;
import com.agentforge.agent.mapper.AgentToolMapper;
import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiChatRequest;
import com.agentforge.aigateway.dto.AiChatResponse;
import com.agentforge.aigateway.dto.ChatHistoryItem;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.conversation.dto.ChatRequest;
import com.agentforge.conversation.entity.Conversation;
import com.agentforge.conversation.mapper.ConversationMapper;
import com.agentforge.conversation.service.ConversationService;
import com.agentforge.conversation.vo.ChatVO;
import com.agentforge.conversation.vo.ConversationVO;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 对话服务实现。
 * 链路（设计 7.4 节）：用户问题 → AI /agent/chat（携带 Agent 配置与最近历史）
 * → 返回 answer+sources → 落库 conversation → 透传前端。
 * 注意：AI 调用失败时不落库（避免记录半截对话），错误码由 ai-gateway 映射。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ConversationServiceImpl implements ConversationService {

    /** 携带给 AI 的历史轮数 */
    private static final int HISTORY_ROUNDS = 10;

    private final ConversationMapper conversationMapper;
    private final AgentMapper agentMapper;
    private final AgentToolMapper agentToolMapper;
    private final AiServiceClient aiServiceClient;

    @Override
    @Transactional
    public ChatVO chat(ChatRequest request, Long userId) {
        Agent agent = agentMapper.selectById(request.getAgentId());
        if (agent == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "智能体不存在");
        }

        // 1. 组装最近历史（倒序取最近 N 轮后反转为正序）
        List<Conversation> recent = conversationMapper.selectList(
                new LambdaQueryWrapper<Conversation>()
                        .eq(Conversation::getAgentId, request.getAgentId())
                        .eq(Conversation::getUserId, userId)
                        .orderByDesc(Conversation::getId)
                        .last("LIMIT " + HISTORY_ROUNDS));
        List<ChatHistoryItem> history = new ArrayList<>();
        for (int i = recent.size() - 1; i >= 0; i--) {
            Conversation c = recent.get(i);
            history.add(new ChatHistoryItem("user", c.getUserMessage()));
            history.add(new ChatHistoryItem("assistant", c.getAssistantMessage()));
        }

        // 2. 加载 Agent 工具配置快照
        List<String> tools = agentToolMapper.selectList(
                        new LambdaQueryWrapper<AgentTool>().eq(AgentTool::getAgentId, agent.getId()))
                .stream()
                .filter(t -> Boolean.TRUE.equals(t.getEnabled()))
                .map(AgentTool::getToolName)
                .toList();

        // 3. 调用 AI 服务（同步 JSON，Phase 3 起演进 SSE）
        AiChatResponse aiResponse = aiServiceClient.chat(AiChatRequest.builder()
                .agentId(agent.getId())
                .message(request.getMessage())
                .history(history)
                .systemPrompt(agent.getSystemPrompt())
                .modelName(agent.getModelName())
                .temperature(agent.getTemperature())
                .tools(tools)
                .build());

        // 4. 落库（一问一答一行）
        Conversation conversation = new Conversation();
        conversation.setAgentId(request.getAgentId());
        conversation.setUserId(userId);
        conversation.setUserMessage(request.getMessage());
        conversation.setAssistantMessage(aiResponse.getAnswer());
        conversationMapper.insert(conversation);

        return ChatVO.builder()
                .answer(aiResponse.getAnswer())
                .sources(aiResponse.getSources() == null ? List.of() : aiResponse.getSources())
                .toolCalls(aiResponse.getToolCalls() == null ? List.of() : aiResponse.getToolCalls())
                .build();
    }

    @Override
    public PageResult<ConversationVO> history(Long agentId, Long userId, long page, long size) {
        IPage<Conversation> result = conversationMapper.selectPage(Page.of(page, size),
                new LambdaQueryWrapper<Conversation>()
                        .eq(Conversation::getAgentId, agentId)
                        .eq(Conversation::getUserId, userId)
                        .orderByDesc(Conversation::getId));
        List<ConversationVO> list = result.getRecords().stream()
                .map(c -> ConversationVO.builder()
                        .id(c.getId())
                        .agentId(c.getAgentId())
                        .userMessage(c.getUserMessage())
                        .assistantMessage(c.getAssistantMessage())
                        .createdTime(c.getCreatedTime())
                        .build())
                .collect(Collectors.toList());
        return PageResult.of(list, result.getTotal(), page, size);
    }
}
