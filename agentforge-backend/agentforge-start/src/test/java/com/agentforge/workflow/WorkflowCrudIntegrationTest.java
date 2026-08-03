package com.agentforge.workflow;

import com.agentforge.IntegrationTestBase;
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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 工作流定义 CRUD 集成测试：创建（含节点）/ 详情 / 分页 / 更新 / 删除 / 权限隔离。
 */
class WorkflowCrudIntegrationTest extends IntegrationTestBase {

    @Autowired
    private ObjectMapper objectMapper;

    /** 创建三节点工作流（查仓库 → 算指标 → 报告），返回 ID */
    private long createWorkflow(String token, String name) throws Exception {
        MvcResult result = mockMvc.perform(post("/workflows")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"%s","description":"演示流程","nodes":[
                                  {"nodeKey":"fetch","nodeType":"tool",
                                   "params":{"tool":"github","payload":{"repo":"spring-projects/spring-boot"}},
                                   "nextNode":"report"},
                                  {"nodeKey":"report","nodeType":"llm",
                                   "params":{"prompt":"生成报告：{message}"},
                                   "nextNode":null}]}""".formatted(name)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        return extractId(result);
    }

    private long extractId(MvcResult result) throws Exception {
        JsonNode node = objectMapper.readTree(result.getResponse().getContentAsString());
        return node.path("data").path("id").asLong();
    }

    @Test
    @DisplayName("创建 → 详情（含节点）→ 分页全链路")
    void createDetailPage() throws Exception {
        String token = registerAndLogin("alice");
        long id = createWorkflow(token, "仓库报告");

        mockMvc.perform(get("/workflows/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.name").value("仓库报告"))
                .andExpect(jsonPath("$.data.nodes.length()").value(2))
                .andExpect(jsonPath("$.data.nodes[0].nodeKey").value("fetch"))
                .andExpect(jsonPath("$.data.nodes[0].params.tool").value("github"))
                .andExpect(jsonPath("$.data.nodes[0].nextNode").value("report"));

        mockMvc.perform(get("/workflows")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("page", "1").param("size", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.total").value(1));
    }

    @Test
    @DisplayName("更新：节点整体替换")
    void updateReplacesNodes() throws Exception {
        String token = registerAndLogin("alice");
        long id = createWorkflow(token, "原流程");

        mockMvc.perform(put("/workflows/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"新流程","nodes":[
                                  {"nodeKey":"calc","nodeType":"tool",
                                   "params":{"tool":"calculator","payload":{"expression":"{stars} * 2"}},
                                   "nextNode":null}]}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.name").value("新流程"));

        mockMvc.perform(get("/workflows/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.nodes.length()").value(1))
                .andExpect(jsonPath("$.data.nodes[0].nodeKey").value("calc"));
    }

    @Test
    @DisplayName("权限：非创建者不可查看/修改/删除（20003）")
    void ownerCheck() throws Exception {
        String ownerToken = registerAndLogin("alice");
        String otherToken = registerAndLogin("bob");
        long id = createWorkflow(ownerToken, "私有流程");

        mockMvc.perform(get("/workflows/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));

        mockMvc.perform(delete("/workflows/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));

        // 创建者删除成功，他人分页不可见
        mockMvc.perform(delete("/workflows/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + ownerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));
        mockMvc.perform(get("/workflows")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    @DisplayName("参数校验：非法节点类型 / 空节点列表被拒")
    void validation() throws Exception {
        String token = registerAndLogin("alice");

        mockMvc.perform(post("/workflows")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"非法流程","nodes":[
                                  {"nodeKey":"a","nodeType":"notify","params":{}}]}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10001));

        mockMvc.perform(post("/workflows")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"空流程","nodes":[]}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10001));
    }

    @Test
    @DisplayName("Agent 工作流模式绑定校验：未绑定工作流 / 绑定他人工作流被拒")
    void agentWorkflowBindingValidation() throws Exception {
        String aliceToken = registerAndLogin("alice");
        String bobToken = registerAndLogin("bob");
        long workflowId = createWorkflow(aliceToken, "Alice 流程");

        // 工作流模式未绑定工作流 → 10001
        mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + aliceToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"缺失绑定","systemPrompt":"测试","mode":"workflow"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10001));

        // 绑定他人工作流 → 20003
        mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + bobToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"越权绑定","systemPrompt":"测试","mode":"workflow",
                                 "workflowId":%d}""".formatted(workflowId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));

        // 正确绑定 → 成功且回显 mode/workflowId
        mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + aliceToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"流程助手","systemPrompt":"测试","mode":"workflow",
                                 "workflowId":%d}""".formatted(workflowId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.mode").value("workflow"))
                .andExpect(jsonPath("$.data.workflowId").value(workflowId));
    }
}
