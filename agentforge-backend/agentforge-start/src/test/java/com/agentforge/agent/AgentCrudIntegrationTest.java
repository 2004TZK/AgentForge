package com.agentforge.agent;

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
 * 智能体 CRUD 集成测试：创建 / 详情 / 更新 / 分页 / 删除 / 权限与参数校验。
 */
class AgentCrudIntegrationTest extends IntegrationTestBase {

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("创建 → 详情 → 分页查询全链路")
    void createDetailPage() throws Exception {
        String token = registerAndLogin("alice");
        long agentId = createAgent(token, "测试助手", "你是一个测试助手。");

        // 详情：含 systemPrompt 与工具列表
        mockMvc.perform(get("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.name").value("测试助手"))
                .andExpect(jsonPath("$.data.systemPrompt").value("你是一个测试助手。"))
                .andExpect(jsonPath("$.data.tools").isArray());

        // 分页：名称模糊命中
        mockMvc.perform(get("/agent/page")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("name", "测试"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.list[0].name").value("测试助手"));
    }

    @Test
    @DisplayName("创建时携带工具配置，详情中可见")
    void createWithTools() throws Exception {
        String token = registerAndLogin("alice");
        MvcResult result = mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"工具助手","systemPrompt":"测试","tools":[
                                  {"toolName":"calculator","enabled":true}]}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.tools[0].toolName").value("calculator"))
                .andReturn();
        long agentId = extractId(result);

        mockMvc.perform(get("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.tools[0].toolName").value("calculator"))
                .andExpect(jsonPath("$.data.tools[0].enabled").value(true));
    }

    @Test
    @DisplayName("更新：仅创建者可操作，非创建者返回 20003")
    void updateOwnerCheck() throws Exception {
        String ownerToken = registerAndLogin("alice");
        long agentId = createAgent(ownerToken, "原始名称", "提示词");

        // 创建者更新成功
        mockMvc.perform(put("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + ownerToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"新名称","systemPrompt":"新提示词"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.name").value("新名称"));

        // 非创建者更新被拒
        String otherToken = registerAndLogin("bob");
        mockMvc.perform(put("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"篡改","systemPrompt":"x"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));
    }

    @Test
    @DisplayName("删除后详情返回 10003（逻辑删除）")
    void deleteAgent() throws Exception {
        String token = registerAndLogin("alice");
        long agentId = createAgent(token, "待删除", "提示词");

        mockMvc.perform(delete("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));

        mockMvc.perform(get("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10003));
    }

    @Test
    @DisplayName("参数校验：缺少名称/系统提示词返回 10001")
    void createValidation() throws Exception {
        String token = registerAndLogin("alice");
        mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"systemPrompt":"有提示词但缺名称"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10001));
    }

    @Test
    @DisplayName("未登录创建返回 HTTP 401")
    void createWithoutToken() throws Exception {
        mockMvc.perform(post("/agent")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"x","systemPrompt":"x"}"""))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(20001));
    }

    @Test
    @DisplayName("查询不存在的智能体返回 10003")
    void detailNotFound() throws Exception {
        String token = registerAndLogin("alice");
        mockMvc.perform(get("/agent/{id}", 999999L)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10003));
    }

    // ---------------- M4 可见性 ----------------

    @Test
    @DisplayName("默认私有：创建后 visibility=PRIVATE")
    void defaultVisibility() throws Exception {
        String token = registerAndLogin("alice");
        MvcResult result = mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"默认可见性","systemPrompt":"x"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.visibility").value("PRIVATE"))
                .andReturn();
        long agentId = extractId(result);

        mockMvc.perform(get("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.visibility").value("PRIVATE"));
    }

    @Test
    @DisplayName("私有仅创建者可见：他人列表不出现、详情返回 10003")
    void privateAgentHiddenFromOthers() throws Exception {
        String ownerToken = registerAndLogin("alice");
        long agentId = createAgent(ownerToken, "私有助手", "x");

        String otherToken = registerAndLogin("bob");
        mockMvc.perform(get("/agent/page")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(0));
        mockMvc.perform(get("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10003));
    }

    @Test
    @DisplayName("公开后他人可见：列表出现且详情可访问")
    void publicAgentVisibleToOthers() throws Exception {
        String ownerToken = registerAndLogin("alice");
        long agentId = createAgent(ownerToken, "公开助手", "x");

        // 设为公开
        mockMvc.perform(put("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + ownerToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"公开助手","systemPrompt":"x","visibility":"PUBLIC"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.visibility").value("PUBLIC"));

        String otherToken = registerAndLogin("bob");
        mockMvc.perform(get("/agent/page")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken)
                        .param("name", "公开"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.list[0].id").value(agentId));
        mockMvc.perform(get("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.visibility").value("PUBLIC"));
    }

    @Test
    @DisplayName("非法可见性值回落 PRIVATE")
    void invalidVisibilityFallsBack() throws Exception {
        String token = registerAndLogin("alice");
        mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"异常值","systemPrompt":"x","visibility":"SECRET"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.visibility").value("PRIVATE"));
    }

    // ---------------- 辅助 ----------------

    private long createAgent(String token, String name, String systemPrompt) throws Exception {
        MvcResult result = mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"%s","systemPrompt":"%s"}""".formatted(name, systemPrompt)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        return extractId(result);
    }

    private long extractId(MvcResult result) throws Exception {
        JsonNode node = objectMapper.readTree(result.getResponse().getContentAsString());
        return node.path("data").path("id").asLong();
    }
}
