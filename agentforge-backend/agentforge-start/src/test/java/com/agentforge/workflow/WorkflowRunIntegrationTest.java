package com.agentforge.workflow;

import com.agentforge.IntegrationTestBase;
import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiWorkflowRunResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 工作流运行集成测试：AI 服务以 @MockBean 替代（确定性），验证运行记录落库、
 * 节点日志回填、Agent 工作流模式对话触发执行。
 */
class WorkflowRunIntegrationTest extends IntegrationTestBase {

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private AiServiceClient aiServiceClient;

    private void mockWorkflowRun() {
        AiWorkflowRunResponse response = new AiWorkflowRunResponse();
        response.setStatus("SUCCESS");
        response.setOutput("Spring Boot 仓库指标报告：Star 76000");
        response.setNodeLogs(List.of(
                Map.of("node", "fetch", "type", "tool", "status", "SUCCESS",
                        "output", "{\"fullName\": \"spring-projects/spring-boot\"}",
                        "error", "", "durationMs", 120),
                Map.of("node", "report", "type", "llm", "status", "SUCCESS",
                        "output", "Spring Boot 仓库指标报告：Star 76000",
                        "error", "", "durationMs", 800)));
        when(aiServiceClient.runWorkflow(any())).thenReturn(response);
    }

    private long createWorkflow(String token) throws Exception {
        MvcResult result = mockMvc.perform(post("/workflows")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"仓库报告流程","nodes":[
                                  {"nodeKey":"fetch","nodeType":"tool",
                                   "params":{"tool":"github","payload":{"repo":"spring-projects/spring-boot"}},
                                   "nextNode":"report"},
                                  {"nodeKey":"report","nodeType":"llm",
                                   "params":{"prompt":"生成报告：{message}"},
                                   "nextNode":null}]}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsString())
                .path("data").path("id").asLong();
    }

    @Test
    @DisplayName("手动运行：输入变量透传，运行记录含输出与节点日志")
    void runWorkflow() throws Exception {
        mockWorkflowRun();
        String token = registerAndLogin("alice");
        long workflowId = createWorkflow(token);

        MvcResult result = mockMvc.perform(post("/workflows/{id}/run", workflowId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"input":{"message":"生成仓库报告"}}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.status").value("SUCCESS"))
                .andExpect(jsonPath("$.data.output").value("Spring Boot 仓库指标报告：Star 76000"))
                .andExpect(jsonPath("$.data.nodeLogs.length()").value(2))
                .andExpect(jsonPath("$.data.nodeLogs[0].node").value("fetch"))
                .andReturn();
        long runId = objectMapper.readTree(result.getResponse().getContentAsString())
                .path("data").path("id").asLong();

        // 运行记录详情 + 分页
        mockMvc.perform(get("/workflows/runs/{runId}", runId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.nodeLogs[1].status").value("SUCCESS"));
        mockMvc.perform(get("/workflows/{id}/runs", workflowId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(1));
    }

    @Test
    @DisplayName("AI 服务异常：运行记录标记 FAILED 并含错误（不抛未处理异常）")
    void runFailureMarked() throws Exception {
        when(aiServiceClient.runWorkflow(any()))
                .thenThrow(new RuntimeException("AI 服务不可达"));
        String token = registerAndLogin("alice");
        long workflowId = createWorkflow(token);

        mockMvc.perform(post("/workflows/{id}/run", workflowId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.status").value("FAILED"))
                .andExpect(jsonPath("$.data.error").isNotEmpty());
    }

    @Test
    @DisplayName("Agent 工作流模式：聊天消息作为 {message} 触发工作流，答案落库")
    void workflowAgentChat() throws Exception {
        mockWorkflowRun();
        String token = registerAndLogin("alice");
        long workflowId = createWorkflow(token);

        // 创建工作流模式 Agent
        MvcResult agentResult = mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"流程助手","systemPrompt":"测试","mode":"workflow",
                                 "workflowId":%d}""".formatted(workflowId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        long agentId = objectMapper.readTree(agentResult.getResponse().getContentAsString())
                .path("data").path("id").asLong();

        // 对话 → 返回工作流输出
        MvcResult chatResult = mockMvc.perform(post("/chat")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"agentId":%d,"message":"生成仓库报告"}""".formatted(agentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.answer").value("Spring Boot 仓库指标报告：Star 76000"))
                .andReturn();
        // 答案已落库（历史可查）
        mockMvc.perform(get("/chat/history")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.list[0].assistantMessage")
                        .value("Spring Boot 仓库指标报告：Star 76000"));

        // 运行记录存在且记录了触发 Agent
        mockMvc.perform(get("/workflows/{id}/runs", workflowId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.list[0].agentId").value(agentId));
    }
}
