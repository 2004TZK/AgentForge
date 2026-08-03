package com.agentforge.conversation;

import com.agentforge.IntegrationTestBase;
import com.agentforge.conversation.entity.Conversation;
import com.agentforge.conversation.mapper.ConversationMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 会话（M2 多会话）集成测试：CRUD、归属校验、历史按会话隔离。
 */
class SessionIntegrationTest extends IntegrationTestBase {

    @Autowired
    private ConversationMapper conversationMapper;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("会话 CRUD：新建（可指定名称）→ 列表 → 删除")
    void sessionCrud() throws Exception {
        String token = registerAndLogin("alice");
        long agentId = createAgent(token, "会话助手");

        // 初始为空
        mockMvc.perform(get("/chat/session/list")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").isArray())
                .andExpect(jsonPath("$.data.length()").value(0));

        // 新建（自定义名称 + 默认名称）
        long customId = createSession(token, agentId, "需求讨论");
        createSession(token, agentId, null);

        mockMvc.perform(get("/chat/session/list")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(2))
                .andExpect(jsonPath("$.data[0].name").value("新会话"))  // 默认名
                .andExpect(jsonPath("$.data[1].name").value("需求讨论"));

        // 删除后列表恢复为空
        mockMvc.perform(delete("/chat/session/{id}", customId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));

        mockMvc.perform(get("/chat/session/list")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId)))
                .andExpect(jsonPath("$.data.length()").value(1));
    }

    @Test
    @DisplayName("非创建者删除会话返回 20003")
    void deleteForbidden() throws Exception {
        String ownerToken = registerAndLogin("alice");
        long agentId = createAgent(ownerToken, "会话助手");
        long sessionId = createSession(ownerToken, agentId, null);

        String otherToken = registerAndLogin("bob");
        mockMvc.perform(delete("/chat/session/{id}", sessionId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));
    }

    @Test
    @DisplayName("历史按会话隔离：不同会话的消息互不混淆")
    void historyIsolatedBySession() throws Exception {
        String token = registerAndLogin("alice");
        long agentId = createAgent(token, "会话助手");
        long userId = fetchUserId(token);
        long sessionA = createSession(token, agentId, null);
        long sessionB = createSession(token, agentId, null);

        insertConversation(agentId, userId, sessionA, "会话A的问题", "会话A的回答");
        insertConversation(agentId, userId, sessionB, "会话B的问题", "会话B的回答");
        insertConversation(agentId, userId, sessionA, "会话A第二问", "会话A第二答");

        // 会话 A：仅含 A 的 2 条
        mockMvc.perform(get("/chat/history")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId))
                        .param("sessionId", String.valueOf(sessionA)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(2))
                .andExpect(jsonPath("$.data.list[0].userMessage").value("会话A第二问"))
                .andExpect(jsonPath("$.data.list[1].userMessage").value("会话A的问题"));

        // 会话 B：仅含 B 的 1 条
        mockMvc.perform(get("/chat/history")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId))
                        .param("sessionId", String.valueOf(sessionB)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.list[0].userMessage").value("会话B的问题"));
    }

    // ---------------- 辅助 ----------------

    private long createSession(String token, long agentId, String name) throws Exception {
        String body = name == null
                ? "{\"agentId\":%d}".formatted(agentId)
                : "{\"agentId\":%d,\"name\":\"%s\"}".formatted(agentId, name);
        MvcResult result = mockMvc.perform(post("/chat/session")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        return extractId(result);
    }

    private void insertConversation(long agentId, long userId, long sessionId,
                                    String userMessage, String assistantMessage) {
        Conversation conversation = new Conversation();
        conversation.setAgentId(agentId);
        conversation.setUserId(userId);
        conversation.setSessionId(sessionId);
        conversation.setUserMessage(userMessage);
        conversation.setAssistantMessage(assistantMessage);
        conversationMapper.insert(conversation);
    }

    private long fetchUserId(String token) throws Exception {
        MvcResult result = mockMvc.perform(get("/auth/me")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode node = objectMapper.readTree(result.getResponse().getContentAsString());
        return node.path("data").path("id").asLong();
    }

    private long extractId(MvcResult result) throws Exception {
        JsonNode node = objectMapper.readTree(result.getResponse().getContentAsString());
        return node.path("data").path("id").asLong();
    }
}
