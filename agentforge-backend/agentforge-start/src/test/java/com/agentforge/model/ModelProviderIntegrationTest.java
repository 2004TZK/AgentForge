package com.agentforge.model;

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
 * 模型 Provider 集成测试（M4 多模型配置）：内置可见不可改删 / 创建更新删除 / 越权。
 */
class ModelProviderIntegrationTest extends IntegrationTestBase {

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("列表包含系统内置 Ollama，创建后本人可见")
    void listContainsBuiltin() throws Exception {
        String token = registerAndLogin("alice");
        mockMvc.perform(get("/model/providers")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data[0].name").value("本地 Ollama"))
                .andExpect(jsonPath("$.data[0].providerType").value("ollama"))
                .andExpect(jsonPath("$.data[0].creatorId").value(0));
    }

    @Test
    @DisplayName("创建 → 更新 → 删除；内置不可改删")
    void crudProvider() throws Exception {
        String token = registerAndLogin("alice");
        MvcResult created = mockMvc.perform(post("/model/providers")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"DeepSeek 云端","providerType":"openai",
                                 "baseUrl":"https://api.deepseek.com/v1","apiKey":"sk-test",
                                 "models":["deepseek-chat"],"enabled":true}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.providerType").value("openai"))
                .andReturn();
        long id = objectMapper.readTree(created.getResponse().getContentAsString())
                .path("data").path("id").asLong();

        // 更新
        mockMvc.perform(put("/model/providers/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"DeepSeek 云端","providerType":"openai",
                                 "baseUrl":"https://api.deepseek.com/v1","apiKey":"sk-new",
                                 "models":["deepseek-chat","deepseek-reasoner"],"enabled":true}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.apiKey").value("****"))
                .andExpect(jsonPath("$.data.models[1]").value("deepseek-reasoner"));

        // 删除
        mockMvc.perform(delete("/model/providers/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));

        // 删除后列表只剩内置
        mockMvc.perform(get("/model/providers")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(1));
    }

    @Test
    @DisplayName("系统内置 Provider 不可修改/删除（20003）")
    void builtinImmutable() throws Exception {
        String token = registerAndLogin("alice");
        // 内置 id=1（schema-h2 首条插入）
        mockMvc.perform(put("/model/providers/{id}", 1L)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"篡改","providerType":"ollama","baseUrl":"http://x"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));
        mockMvc.perform(delete("/model/providers/{id}", 1L)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));
    }

    @Test
    @DisplayName("他人创建的 Provider 不可修改/删除（20003）")
    void ownerCheck() throws Exception {
        String ownerToken = registerAndLogin("alice");
        MvcResult created = mockMvc.perform(post("/model/providers")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + ownerToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"我的 Provider","providerType":"openai","baseUrl":"http://x"}"""))
                .andExpect(status().isOk())
                .andReturn();
        long id = objectMapper.readTree(created.getResponse().getContentAsString())
                .path("data").path("id").asLong();

        String otherToken = registerAndLogin("bob");
        mockMvc.perform(put("/model/providers/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"篡改","providerType":"openai","baseUrl":"http://x"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));
        mockMvc.perform(delete("/model/providers/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));
    }

    @Test
    @DisplayName("非法 Provider 类型返回 10001")
    void invalidType() throws Exception {
        String token = registerAndLogin("alice");
        mockMvc.perform(post("/model/providers")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"x","providerType":"bad","baseUrl":"http://x"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10001));
    }

    @Test
    @DisplayName("API Key 脱敏回显；留空/掩码更新不覆盖原 Key")
    void apiKeyMaskedAndKeptOnUpdate() throws Exception {
        String token = registerAndLogin("alice");
        MvcResult created = mockMvc.perform(post("/model/providers")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"DeepSeek 云端","providerType":"openai",
                                 "baseUrl":"https://api.deepseek.com/v1","apiKey":"sk-abcdef1234567890",
                                 "models":["deepseek-chat"],"enabled":true}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.apiKey").value("sk-****7890"))
                .andReturn();
        long id = extractId(created);

        // 留空更新（未传 apiKey）：密钥保留，回显仍为掩码
        mockMvc.perform(put("/model/providers/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"DeepSeek 云端","providerType":"openai",
                                 "baseUrl":"https://api.deepseek.com/v1",
                                 "models":["deepseek-chat","deepseek-reasoner"],"enabled":true}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.apiKey").value("sk-****7890"))
                .andExpect(jsonPath("$.data.models[1]").value("deepseek-reasoner"));

        // 用掩码回显值更新：视为未修改，密钥保留
        mockMvc.perform(put("/model/providers/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"DeepSeek 云端","providerType":"openai",
                                 "baseUrl":"https://api.deepseek.com/v1","apiKey":"sk-****7890",
                                 "models":["deepseek-chat"],"enabled":true}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.apiKey").value("sk-****7890"));

        // 传真实新 Key：覆盖并返回新掩码
        mockMvc.perform(put("/model/providers/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"DeepSeek 云端","providerType":"openai",
                                 "baseUrl":"https://api.deepseek.com/v1","apiKey":"sk-realnewkey12345",
                                 "models":["deepseek-chat"],"enabled":true}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.apiKey").value("sk-****2345"));
    }

    @Test
    @DisplayName("Agent 绑定 Provider：创建/详情回显 providerId")
    void agentBindsProvider() throws Exception {
        String token = registerAndLogin("alice");
        MvcResult created = mockMvc.perform(post("/model/providers")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"DeepSeek","providerType":"openai",
                                 "baseUrl":"https://api.deepseek.com/v1","models":["deepseek-chat"]}"""))
                .andExpect(status().isOk())
                .andReturn();
        long providerId = objectMapper.readTree(created.getResponse().getContentAsString())
                .path("data").path("id").asLong();

        MvcResult agent = mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"云端助手","systemPrompt":"x","modelName":"deepseek-chat",
                                 "providerId":%d}""".formatted(providerId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.providerId").value(providerId))
                .andReturn();
        long agentId = objectMapper.readTree(agent.getResponse().getContentAsString())
                .path("data").path("id").asLong();

        mockMvc.perform(get("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.providerId").value(providerId))
                .andExpect(jsonPath("$.data.modelName").value("deepseek-chat"));
    }

    private long extractId(MvcResult result) throws Exception {
        JsonNode node = objectMapper.readTree(result.getResponse().getContentAsString());
        return node.path("data").path("id").asLong();
    }
}
