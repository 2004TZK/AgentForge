package com.agentforge.conversation;

import com.agentforge.IntegrationTestBase;
import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiChatRequest;
import com.agentforge.aigateway.dto.AiChatResponse;
import com.agentforge.aigateway.dto.AiSourceItem;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 对话集成测试（AI 服务以 @MockBean 替代，确定性验证）：
 * 同步回答落库、历史分页（含引用来源）、工作流模式触发、私有 Agent 越权校验。
 */
class ChatIntegrationTest extends IntegrationTestBase {

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private AiServiceClient aiServiceClient;

    private void mockChat(String answer) {
        AiChatResponse response = new AiChatResponse();
        response.setAnswer(answer);
        response.setToolCalls(List.of("calculator({\"expression\":\"2+2\"}) → 4"));
        AiSourceItem source = new AiSourceItem();
        source.setFile("rag.md");
        source.setSnippet("片段");
        source.setScore(0.87);
        response.setSources(List.of(source));
        when(aiServiceClient.chat(any(AiChatRequest.class))).thenReturn(response);
    }

    @Test
    @DisplayName("同步聊天：回答 + 工具记录 + 来源引用落库，历史可回溯")
    void chatSyncPersistsHistory() throws Exception {
        String token = registerAndLogin("alice");
        long agentId = createAgent(token);

        mockChat("你好，我是测试助手");
        mockMvc.perform(post("/chat")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"agentId":%d,"message":"你好"}""".formatted(agentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.answer").value("你好，我是测试助手"))
                .andExpect(jsonPath("$.data.toolCalls[0]").value("calculator({\"expression\":\"2+2\"}) → 4"))
                .andExpect(jsonPath("$.data.sources[0].file").value("rag.md"));

        // 历史分页：一问一答一行 + 来源引用可回溯
        mockMvc.perform(get("/chat/history")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId))
                        .param("page", "1").param("size", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.list[0].userMessage").value("你好"))
                .andExpect(jsonPath("$.data.list[0].assistantMessage").value("你好，我是测试助手"))
                .andExpect(jsonPath("$.data.list[0].sources[0].file").value("rag.md"));
    }

    @Test
    @DisplayName("流式聊天：done 事件后落库")
    void chatStreamPersists() throws Exception {
        String token = registerAndLogin("alice");
        long agentId = createAgent(token);

        // mock 流式响应（SSE 字节流：delta 增量 + done 终端事件）
        org.springframework.http.client.ClientHttpResponse streamResp =
                org.mockito.Mockito.mock(org.springframework.http.client.ClientHttpResponse.class);
        String sse = "data: {\"type\":\"delta\",\"content\":\"流式回答内容\"}\n\n"
                + "data: {\"type\":\"done\",\"answer\":\"流式回答内容\",\"sources\":[],\"toolCalls\":[]}\n\n";
        when(streamResp.getBody())
                .thenReturn(new java.io.ByteArrayInputStream(sse.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        when(streamResp.getStatusCode()).thenReturn(org.springframework.http.HttpStatus.OK);
        when(aiServiceClient.openStream(any())).thenReturn(streamResp);

        MvcResult result = mockMvc.perform(post("/chat/stream")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"agentId":%d,"message":"hi"}""".formatted(agentId)))
                .andExpect(request().asyncStarted())
                .andReturn();
        result.getAsyncResult(10_000);  // 等待异步流写完
        MvcResult dispatched = mockMvc.perform(asyncDispatch(result)).andReturn();
        // SSE 为 UTF-8 字节透传，MockMvc 默认 ISO-8859-1 解码会导致中文乱码，需显式指定
        String body = dispatched.getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8);
        org.junit.jupiter.api.Assertions.assertTrue(
                body.contains("流式回答内容"), "SSE 应包含 AI 回答增量");

        // done 事件触发落库
        mockMvc.perform(get("/chat/history")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId))
                        .param("page", "1").param("size", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(1));
    }

    @Test
    @DisplayName("私有 Agent 越权聊天返回 10003；公开 Agent 可聊")
    void privateAgentChatForbidden() throws Exception {
        String ownerToken = registerAndLogin("alice");
        long agentId = createAgent(ownerToken);  // 默认 PRIVATE

        String otherToken = registerAndLogin("bob");
        mockMvc.perform(post("/chat")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"agentId":%d,"message":"hi"}""".formatted(agentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10003));

        // 设为公开后可聊
        mockMvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + ownerToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"公开助手","systemPrompt":"x","visibility":"PUBLIC"}"""))
                .andExpect(status().isOk());
        mockChat("公开回答");
        mockMvc.perform(post("/chat")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"agentId":%d,"message":"hi"}""".formatted(agentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.answer").value("公开回答"));
    }

    private long createAgent(String token) throws Exception {
        MvcResult result = mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"聊天助手","systemPrompt":"测试"}"""))
                .andExpect(status().isOk())
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsString())
                .path("data").path("id").asLong();
    }
}
