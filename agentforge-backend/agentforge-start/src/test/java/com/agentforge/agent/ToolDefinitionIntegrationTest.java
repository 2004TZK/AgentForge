package com.agentforge.agent;

import com.agentforge.IntegrationTestBase;
import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiToolTestResponse;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MvcResult;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 用户自定义工具集成测试：CRUD / 密钥加密脱敏 / 名称校验（含内置重名）/
 * 权限隔离 / Agent 绑定 / 复制 / 测试（AI 服务以 @MockBean 替代）。
 */
class ToolDefinitionIntegrationTest extends IntegrationTestBase {

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @MockBean
    private AiServiceClient aiServiceClient;

    /** 内置工具元数据（Mock：registry 返回 calculator/github 等） */
    private void mockToolMeta() {
        when(aiServiceClient.getToolMeta()).thenReturn(List.of(
                Map.of("name", "calculator", "description", "计算器"),
                Map.of("name", "github", "description", "GitHub 查询")));
    }

    private void mockTestTool() {
        AiToolTestResponse response = AiToolTestResponse.builder()
                .ok(true).result("{\"temp\": 25}").durationMs(12).build();
        when(aiServiceClient.testTool(any())).thenReturn(response);
    }

    private static final String HTTP_TOOL_JSON = """
            {
              "name": "weather_query",
              "displayName": "天气查询",
              "description": "查询指定城市天气",
              "toolType": "http",
              "parameters": {"type":"object","properties":{"city":{"type":"string","description":"城市"}},"required":["city"]},
              "httpConfig": {
                "method": "GET",
                "url": "https://api.example.com/v1/weather?city={city}",
                "auth": {"type": "api_key", "headerName": "X-API-Key", "value": "secret-key-123"},
                "timeoutSeconds": 10
              },
              "visibility": "PRIVATE"
            }
            """;

    private long createHttpTool(String token) throws Exception {
        MvcResult result = mockMvc.perform(post("/tool-definitions")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(HTTP_TOOL_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        return extractId(result);
    }

    @Test
    @DisplayName("创建 HTTP 工具：详情密钥脱敏，数据库为 enc:v1: 密文")
    void createHttpToolEncryptsSecret() throws Exception {
        mockToolMeta();
        String token = registerAndLogin("alice");
        long id = createHttpTool(token);

        // 详情：auth.value 脱敏为掩码
        mockMvc.perform(get("/tool-definitions/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.name").value("weather_query"))
                .andExpect(jsonPath("$.data.httpConfig.auth.value").value("********"));

        // 数据库：密钥字段为密文（enc:v1: 前缀），非明文
        String stored = jdbcTemplate.queryForObject(
                "SELECT http_config FROM tool_definition WHERE id = ?", String.class, id);
        assert stored != null && stored.contains("enc:v1:")
                && !stored.contains("secret-key-123") : "密钥必须加密入库: " + stored;
    }

    @Test
    @DisplayName("名称校验：非法格式 / 与内置工具重名 / 用户级重复均被拒")
    void nameValidation() throws Exception {
        mockToolMeta();
        String token = registerAndLogin("alice");

        // 非法格式（大写开头）
        mockMvc.perform(post("/tool-definitions")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(HTTP_TOOL_JSON.replace("\"weather_query\"", "\"WeatherQuery\"")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10001));

        // 与内置工具重名
        mockMvc.perform(post("/tool-definitions")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(HTTP_TOOL_JSON.replace("\"weather_query\"", "\"calculator\"")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10004));

        // 用户级唯一：同名二次创建被拒
        createHttpTool(token);
        mockMvc.perform(post("/tool-definitions")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(HTTP_TOOL_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10004));
    }

    @Test
    @DisplayName("代码工具：创建成功，scriptConfig 返回代码明文")
    void createScriptTool() throws Exception {
        mockToolMeta();
        String token = registerAndLogin("alice");
        MvcResult result = mockMvc.perform(post("/tool-definitions")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "name": "dedupe",
                                  "displayName": "去重排序",
                                  "toolType": "script",
                                  "parameters": {"type":"object","properties":{"items":{"type":"array"}}},
                                  "scriptConfig": {"language": "python", "source": "def run(args):\\n    return sorted(set(args.get('items', [])))"},
                                  "visibility": "PRIVATE"
                                }"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.toolType").value("script"))
                .andExpect(jsonPath("$.data.scriptConfig.language").value("python"))
                .andExpect(jsonPath("$.data.scriptConfig.source").value(contains("sorted")))
                .andReturn();
        assert result.getResponse().getContentAsString().contains("def run");
    }

    private static org.hamcrest.Matcher<String> contains(String value) {
        return org.hamcrest.CoreMatchers.containsString(value);
    }

    @Test
    @DisplayName("代码大小超过 50KB 被拒")
    void scriptTooLargeRejected() throws Exception {
        mockToolMeta();
        String token = registerAndLogin("alice");
        StringBuilder big = new StringBuilder("def run(args):\n    return ");
        big.append("1 + ".repeat(60 * 1024));
        mockMvc.perform(post("/tool-definitions")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"bigtool","displayName":"大代码","toolType":"script",
                                 "parameters":{},"scriptConfig":{"language":"python","source":"%s"}}"""
                                .formatted(big)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10001));
    }

    @Test
    @DisplayName("权限隔离：PRIVATE 他人不可见；PUBLIC 他人可见但密钥仍脱敏")
    void visibilityIsolation() throws Exception {
        mockToolMeta();
        String ownerToken = registerAndLogin("alice");
        long id = createHttpTool(ownerToken);

        String otherToken = registerAndLogin("bob");
        // PRIVATE：他人详情视为不存在
        mockMvc.perform(get("/tool-definitions/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10003));

        // 设为 PUBLIC
        mockMvc.perform(put("/tool-definitions/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + ownerToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(HTTP_TOOL_JSON.replace("\"PRIVATE\"", "\"PUBLIC\"")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.visibility").value("PUBLIC"));

        // 他人可见，但密钥仍脱敏
        mockMvc.perform(get("/tool-definitions/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.httpConfig.auth.value").value("********"));

        // 他人不可修改/删除
        mockMvc.perform(delete("/tool-definitions/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));
    }

    @Test
    @DisplayName("Agent 绑定自定义工具：toolSource=custom 且带 definitionId")
    void agentBindCustomTool() throws Exception {
        mockToolMeta();
        String token = registerAndLogin("alice");
        long toolId = createHttpTool(token);

        MvcResult result = mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"自定义工具助手","systemPrompt":"x","tools":[
                                  {"toolName":"weather_query","toolSource":"custom","toolDefinitionId":%d,"enabled":true}]}"""
                                .formatted(toolId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.tools[0].toolSource").value("custom"))
                .andExpect(jsonPath("$.data.tools[0].toolDefinitionId").value(toolId))
                .andReturn();
        long agentId = extractId(result);

        // 详情回显一致
        mockMvc.perform(get("/agent/{id}", agentId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.tools[0].toolSource").value("custom"));
    }

    @Test
    @DisplayName("绑定不存在的自定义工具被拒")
    void agentBindMissingCustomToolRejected() throws Exception {
        mockToolMeta();
        String token = registerAndLogin("alice");
        mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"x","systemPrompt":"x","tools":[
                                  {"toolName":"ghost","toolSource":"custom","toolDefinitionId":999999,"enabled":true}]}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10003));
    }

    @Test
    @DisplayName("复制 PUBLIC 工具到本人工具库")
    void copyPublicTool() throws Exception {
        mockToolMeta();
        String ownerToken = registerAndLogin("alice");
        long id = createHttpTool(ownerToken);
        mockMvc.perform(put("/tool-definitions/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + ownerToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(HTTP_TOOL_JSON.replace("\"PRIVATE\"", "\"PUBLIC\"")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));

        String otherToken = registerAndLogin("bob");
        // bob 名下无同名工具 → 复制后名称不变（用户级唯一，不同用户可同名）
        mockMvc.perform(post("/tool-definitions/{id}/copy", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.name").value("weather_query"))
                .andExpect(jsonPath("$.data.creatorId").exists());
        // 再复制一次 → 名称冲突，自动追加 _copy 后缀
        mockMvc.perform(post("/tool-definitions/{id}/copy", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.name").value("weather_query_copy"));
    }

    @Test
    @DisplayName("测试接口：透传 AI 服务执行（Mock 返回成功）")
    void testTool() throws Exception {
        mockToolMeta();
        mockTestTool();
        String token = registerAndLogin("alice");
        mockMvc.perform(post("/tool-definitions/test")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"toolType":"http",
                                 "httpConfig":{"method":"GET","url":"https://api.example.com/v1/weather?city={city}"},
                                 "parameters":{},"args":{"city":"北京"}}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.ok").value(true))
                .andExpect(jsonPath("$.data.result").exists());
    }

    @Test
    @DisplayName("删除后详情返回 10003")
    void deleteTool() throws Exception {
        mockToolMeta();
        String token = registerAndLogin("alice");
        long id = createHttpTool(token);
        mockMvc.perform(delete("/tool-definitions/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));
        mockMvc.perform(get("/tool-definitions/{id}", id)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10003));
    }

    // ---------------- 辅助 ----------------

    private long extractId(MvcResult result) throws Exception {
        JsonNode node = objectMapper.readTree(result.getResponse().getContentAsString());
        return node.path("data").path("id").asLong();
    }
}
