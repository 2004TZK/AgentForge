package com.agentforge.conversation.service.impl;

import com.agentforge.agent.entity.Agent;
import com.agentforge.agent.entity.AgentTool;
import com.agentforge.agent.mapper.AgentMapper;
import com.agentforge.agent.mapper.AgentToolMapper;
import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiChatRequest;
import com.agentforge.aigateway.dto.AiChatResponse;
import com.agentforge.aigateway.dto.AiSourceItem;
import com.agentforge.aigateway.dto.ChatHistoryItem;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.conversation.dto.ChatRequest;
import com.agentforge.conversation.entity.Conversation;
import com.agentforge.conversation.entity.Session;
import com.agentforge.conversation.mapper.ConversationMapper;
import com.agentforge.conversation.mapper.SessionMapper;
import com.agentforge.conversation.service.ConversationService;
import com.agentforge.conversation.vo.ChatVO;
import com.agentforge.conversation.vo.ConversationVO;
import com.agentforge.workflow.entity.Workflow;
import com.agentforge.workflow.service.WorkflowService;
import com.agentforge.workflow.vo.WorkflowRunVO;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 对话服务实现。
 * 同步链路（设计 7.4 节）：用户问题 → AI /agent/chat（携带 Agent 配置与最近历史）
 * → 返回 answer+sources → 落库 conversation → 透传前端。
 * 流式链路（M1）：AI /agent/chat/stream 事件流原样透传，done 事件时落库。
 * M2 起历史按会话隔离（sessionId）；会话默认名在首条消息成功后自动命名。
 * 注意：AI 调用失败时不落库（避免记录半截对话），错误码由 ai-gateway 映射。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ConversationServiceImpl implements ConversationService {

    /** 携带给 AI 的历史轮数 */
    private static final int HISTORY_ROUNDS = 10;

    /** 会话默认名称（首条消息成功后自动命名覆盖） */
    private static final String DEFAULT_SESSION_NAME = "新会话";

    /** 自动命名的消息截断长度 */
    private static final int SESSION_NAME_MAX = 20;

    private final ConversationMapper conversationMapper;
    private final SessionMapper sessionMapper;
    private final AgentMapper agentMapper;
    private final AgentToolMapper agentToolMapper;
    private final AiServiceClient aiServiceClient;
    private final ObjectMapper objectMapper;
    private final WorkflowService workflowService;

    @Override
    @Transactional
    public ChatVO chat(ChatRequest request, Long userId) {
        Agent agent = loadAgentVisibleOrThrow(request.getAgentId(), userId);

        // M3 工作流模式：聊天消息作为工作流输入 {message}，答案取流程输出
        if ("workflow".equals(agent.getMode())) {
            WorkflowRunVO run = workflowService.runForAgent(
                    loadAgentWorkflow(agent), agent.getId(), request.getMessage(), userId);
            AiChatResponse workflowResponse = new AiChatResponse();
            workflowResponse.setAnswer(run.getOutput() == null ? "" : run.getOutput());
            recordConversation(request, userId, workflowResponse);
            autoNameSession(request, userId);
            return toChatVO(workflowResponse);
        }

        AiChatRequest aiRequest = buildAiChatRequest(agent, request, userId);

        // 调用 AI 服务（同步 JSON）
        AiChatResponse aiResponse = aiServiceClient.chat(aiRequest);

        // 落库（一问一答一行；失败随事务回滚，向上抛错）
        recordConversation(request, userId, aiResponse);
        autoNameSession(request, userId);

        return toChatVO(aiResponse);
    }

    @Override
    public StreamingResponseBody chatStream(ChatRequest request, Long userId) {
        // 参数/权限校验在进入流式前完成；真正的 IO 透传发生在 WebMvc 异步线程
        Agent agent = loadAgentVisibleOrThrow(request.getAgentId(), userId);
        if ("workflow".equals(agent.getMode())) {
            // M3 工作流模式：运行工作流后按块输出答案（打字机效果一致）
            return outputStream -> relayWorkflowStream(agent, request, userId, outputStream);
        }
        AiChatRequest aiRequest = buildAiChatRequest(agent, request, userId);
        return outputStream -> relayStream(aiRequest, request, userId, outputStream);
    }

    /**
     * SSE 字节透传：AI 服务原始事件流原样转发给前端（保证打字机低延迟），
     * 嗅探 done/error 终端事件用于落库与结束。
     * 运行在 WebMvc 异步线程，见 {@link #recordStreamResult} 关于事务的说明。
     */
    private void relayStream(AiChatRequest aiRequest, ChatRequest request, Long userId,
                             OutputStream outputStream) {
        try (ClientHttpResponse response = aiServiceClient.openStream(aiRequest)) {
            if (!response.getStatusCode().is2xxSuccessful()) {
                // 连接阶段失败（AI 服务未启动/内部错误）：读取结构化错误转为 SSE error 事件
                writeErrorEvent(outputStream, aiServiceClient.mapAiError(response));
                return;
            }
            BufferedReader reader = new BufferedReader(
                    new InputStreamReader(response.getBody(), StandardCharsets.UTF_8));
            String line;
            while ((line = reader.readLine()) != null) {
                outputStream.write(line.getBytes(StandardCharsets.UTF_8));
                outputStream.write('\n');
                outputStream.flush();
                String data = extractSseData(line);
                if (data != null && handleStreamEvent(data, request, userId)) {
                    return; // done/error 终端事件已转发
                }
            }
        } catch (IOException e) {
            if (isClientDisconnect(e)) {
                log.debug("客户端中断 SSE 流: {}", e.getMessage());
            } else {
                log.error("SSE 透传失败", e);
            }
        }
    }

    /**
     * 工作流模式 SSE 透传：同步运行工作流 → 答案按块输出 delta → done 事件。
     * 落库失败不影响已输出的回答（与流式链路一致）；执行失败转为 error 事件。
     */
    private void relayWorkflowStream(Agent agent, ChatRequest request, Long userId,
                                     OutputStream outputStream) {
        try {
            WorkflowRunVO run = workflowService.runForAgent(
                    loadAgentWorkflow(agent), agent.getId(), request.getMessage(), userId);
            String answer = run.getOutput() == null ? "" : run.getOutput();
            recordStreamResult(request, userId, toAiResponse(answer));
            autoNameSession(request, userId);
            int chunkSize = 16;
            for (int i = 0; i < answer.length(); i += chunkSize) {
                Map<String, Object> delta = new HashMap<>();
                delta.put("type", "delta");
                delta.put("content", answer.substring(i, Math.min(i + chunkSize, answer.length())));
                writeSse(outputStream, delta);
            }
            Map<String, Object> done = new HashMap<>();
            done.put("type", "done");
            done.put("answer", answer);
            done.put("sources", List.of());
            done.put("toolCalls", List.of());
            writeSse(outputStream, done);
        } catch (Exception e) {
            log.error("工作流对话失败: agentId={}, userId={}", agent.getId(), userId, e);
            try {
                writeErrorEvent(outputStream, new BusinessException(ResultCode.LLM_ERROR,
                        "工作流执行失败: " + e.getMessage()));
            } catch (IOException io) {
                log.debug("工作流 SSE 错误事件写入失败: {}", io.getMessage());
            }
        }
    }

    private AiChatResponse toAiResponse(String answer) {
        AiChatResponse response = new AiChatResponse();
        response.setAnswer(answer);
        response.setSources(List.of());
        response.setToolCalls(List.of());
        return response;
    }

    /** 序列化事件为 SSE data 帧（消息经 Jackson 转义，保证 JSON 合法） */
    private void writeSse(OutputStream outputStream, Map<String, Object> event) throws IOException {
        outputStream.write("data: ".getBytes(StandardCharsets.UTF_8));
        outputStream.write(objectMapper.writeValueAsBytes(event));
        outputStream.write("\n\n".getBytes(StandardCharsets.UTF_8));
        outputStream.flush();
    }

    /**
     * 解析 AI 服务事件：done → 落库；error → 仅记录日志。返回是否终端事件。
     * 解析失败只记录日志（透传优先，不影响已输出的内容）。
     */
    private boolean handleStreamEvent(String data, ChatRequest request, Long userId) {
        try {
            JsonNode node = objectMapper.readTree(data);
            String type = node.path("type").asText("");
            if ("done".equals(type)) {
                AiChatResponse result = new AiChatResponse();
                result.setAnswer(node.path("answer").asText(""));
                result.setSources(parseSources(node.path("sources")));
                result.setToolCalls(parseStringArray(node, "toolCalls"));
                recordStreamResult(request, userId, result);
                autoNameSession(request, userId);
                return true;
            }
            if ("error".equals(type)) {
                log.warn("AI 流式对话错误: code={}, message={}",
                        node.path("code").asInt(0), node.path("message").asText(""));
                return true;
            }
        } catch (IOException e) {
            log.warn("解析 AI 流式事件失败，忽略: {}", data);
        }
        return false;
    }

    /**
     * 落库一问一答（同步链路：随 @Transactional 事务提交，失败向上抛错）。
     */
    private void recordConversation(ChatRequest request, Long userId, AiChatResponse result) {
        Conversation conversation = new Conversation();
        conversation.setAgentId(request.getAgentId());
        conversation.setUserId(userId);
        conversation.setSessionId(request.getSessionId());
        conversation.setUserMessage(request.getMessage());
        conversation.setAssistantMessage(result.getAnswer());
        conversation.setSources(result.getSources() == null ? List.of() : result.getSources());
        conversationMapper.insert(conversation);
    }

    /**
     * 流式链路落库：由 WebMvc 异步线程调用，不经事务代理 —— 单条 INSERT 原子提交，
     * 无需事务；落库失败不阻断已输出的回答，仅记录日志。
     */
    private void recordStreamResult(ChatRequest request, Long userId, AiChatResponse result) {
        try {
            recordConversation(request, userId, result);
        } catch (Exception e) {
            log.error("流式对话落库失败: agentId={}, userId={}", request.getAgentId(), userId, e);
        }
    }

    /**
     * 首条消息自动命名会话：会话名仍为默认「新会话」时，以消息前 20 字覆盖。
     * 显式自定义过名称的会话不受影响；仅校验本人会话；失败不影响主链路。
     */
    private void autoNameSession(ChatRequest request, Long userId) {
        Long sessionId = request.getSessionId();
        if (sessionId == null || !StringUtils.hasText(request.getMessage())) {
            return;
        }
        try {
            Session session = sessionMapper.selectById(sessionId);
            if (session != null && session.getUserId().equals(userId)
                    && DEFAULT_SESSION_NAME.equals(session.getName())) {
                String message = request.getMessage().trim();
                String name = message.length() > SESSION_NAME_MAX
                        ? message.substring(0, SESSION_NAME_MAX) : message;
                Session update = new Session();
                update.setId(sessionId);
                update.setName(name);
                sessionMapper.updateById(update);
                log.info("会话自动命名: id={}, name={}", sessionId, name);
            }
        } catch (Exception e) {
            log.warn("会话自动命名失败: sessionId={}", sessionId, e);
        }
    }

    private Agent loadAgentOrThrow(Long agentId) {
        Agent agent = agentMapper.selectById(agentId);
        if (agent == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "智能体不存在");
        }
        return agent;
    }

    /** M4 可见性校验：PRIVATE 仅创建者可聊天，非创建者视为不存在 */
    private Agent loadAgentVisibleOrThrow(Long agentId, Long userId) {
        Agent agent = loadAgentOrThrow(agentId);
        if (!"PUBLIC".equals(agent.getVisibility()) && !agent.getCreatorId().equals(userId)) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "智能体不存在");
        }
        return agent;
    }

    /** 加载 Agent 绑定的工作流（校验归属：必须是创建者本人名下） */
    private Workflow loadAgentWorkflow(Agent agent) {
        return workflowService.getOwned(agent.getWorkflowId(), agent.getCreatorId());
    }

    private ChatVO toChatVO(AiChatResponse aiResponse) {
        return ChatVO.builder()
                .answer(aiResponse.getAnswer())
                .sources(aiResponse.getSources() == null ? List.of() : aiResponse.getSources())
                .toolCalls(aiResponse.getToolCalls() == null ? List.of() : aiResponse.getToolCalls())
                .build();
    }

    /** 加载 Agent 校验 + 组装最近历史 + 工具配置快照，构造 AI 请求（同步/流式共用） */
    private AiChatRequest buildAiChatRequest(Agent agent, ChatRequest request, Long userId) {
        // 1. 组装最近历史（按会话隔离；倒序取最近 N 轮后反转为正序）
        List<Conversation> recent = conversationMapper.selectList(
                new LambdaQueryWrapper<Conversation>()
                        .eq(Conversation::getAgentId, request.getAgentId())
                        .eq(Conversation::getUserId, userId)
                        .eq(request.getSessionId() != null, Conversation::getSessionId,
                                request.getSessionId())
                        .orderByDesc(Conversation::getId)
                        .last("LIMIT " + HISTORY_ROUNDS));
        List<ChatHistoryItem> history = new ArrayList<>();
        for (int i = recent.size() - 1; i >= 0; i--) {
            Conversation c = recent.get(i);
            history.add(new ChatHistoryItem("user", c.getUserMessage()));
            history.add(new ChatHistoryItem("assistant", c.getAssistantMessage()));
        }

        // 2. 加载 Agent 工具配置快照（M3：含工具配置 {tool_name: config} 透传 AI 服务）
        List<AgentTool> agentTools = agentToolMapper.selectList(
                new LambdaQueryWrapper<AgentTool>().eq(AgentTool::getAgentId, agent.getId()));
        List<String> tools = agentTools.stream()
                .filter(t -> Boolean.TRUE.equals(t.getEnabled()))
                .map(AgentTool::getToolName)
                .toList();
        Map<String, Map<String, Object>> toolConfigs = new HashMap<>();
        for (AgentTool t : agentTools) {
            if (t.getToolConfig() != null && !t.getToolConfig().isEmpty()) {
                toolConfigs.put(t.getToolName(), t.getToolConfig());
            }
        }

        return AiChatRequest.builder()
                .agentId(agent.getId())
                .message(request.getMessage())
                .history(history)
                .systemPrompt(agent.getSystemPrompt())
                .modelName(agent.getModelName())
                .temperature(agent.getTemperature())
                .tools(tools)
                .userId(userId)
                .toolConfigs(toolConfigs)
                .build();
    }

    @Override
    public PageResult<ConversationVO> history(Long agentId, Long sessionId, Long userId,
                                              long page, long size) {
        IPage<Conversation> result = conversationMapper.selectPage(Page.of(page, size),
                new LambdaQueryWrapper<Conversation>()
                        .eq(Conversation::getAgentId, agentId)
                        .eq(Conversation::getUserId, userId)
                        .eq(sessionId != null, Conversation::getSessionId, sessionId)
                        .orderByDesc(Conversation::getId));
        List<ConversationVO> list = result.getRecords().stream()
                .map(c -> ConversationVO.builder()
                        .id(c.getId())
                        .agentId(c.getAgentId())
                        .userMessage(c.getUserMessage())
                        .assistantMessage(c.getAssistantMessage())
                        .sources(c.getSources() == null ? List.of() : c.getSources())
                        .createdTime(c.getCreatedTime())
                        .build())
                .collect(Collectors.toList());
        return PageResult.of(list, result.getTotal(), page, size);
    }

    // ---------------- 流式透传辅助 ----------------

    /** 提取 SSE data 行的 JSON 载荷；非 data 行（注释/空行）返回 null */
    private String extractSseData(String line) {
        if (line.startsWith("data:")) {
            return line.substring("data:".length()).trim();
        }
        return null;
    }

    /** 将业务异常序列化为 SSE error 事件（消息经 Jackson 转义，保证 JSON 合法） */
    private void writeErrorEvent(OutputStream outputStream, BusinessException e) throws IOException {
        Map<String, Object> event = new HashMap<>();
        event.put("type", "error");
        event.put("code", e.getResultCode().getCode());
        event.put("message", e.getMessage());
        outputStream.write("data: ".getBytes(StandardCharsets.UTF_8));
        outputStream.write(objectMapper.writeValueAsBytes(event));
        outputStream.write("\n\n".getBytes(StandardCharsets.UTF_8));
        outputStream.flush();
    }

    /** 解析 done 事件中的 sources 数组（[{file, snippet, score}]） */
    private List<AiSourceItem> parseSources(JsonNode sourcesNode) {
        List<AiSourceItem> sources = new ArrayList<>();
        if (sourcesNode == null || !sourcesNode.isArray()) {
            return sources;
        }
        sourcesNode.forEach(item -> {
            AiSourceItem source = new AiSourceItem();
            source.setFile(item.path("file").asText(""));
            source.setSnippet(item.path("snippet").asText(""));
            source.setScore(item.path("score").asDouble(0.0));
            sources.add(source);
        });
        return sources;
    }

    private List<String> parseStringArray(JsonNode node, String field) {
        List<String> list = new ArrayList<>();
        node.path(field).forEach(item -> list.add(item.asText()));
        return list;
    }

    /** 客户端主动断开（浏览器关闭/取消）时的 IOException 特征 */
    private boolean isClientDisconnect(IOException e) {
        String message = e.getMessage();
        return message != null && (message.contains("Broken pipe")
                || message.contains("Connection reset")
                || message.contains("aborted"));
    }
}
