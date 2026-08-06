package com.agentforge.file;

import com.agentforge.IntegrationTestBase;
import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiDeleteResponse;
import com.agentforge.aigateway.dto.AiIngestResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MvcResult;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 文件管理集成测试（AI 服务 @MockBean）：上传触发入库、列表、删除、越权校验。
 */
class FileCrudIntegrationTest extends IntegrationTestBase {

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private AiServiceClient aiServiceClient;

    private void mockIngest() {
        AiIngestResponse response = new AiIngestResponse();
        response.setStatus("ok");
        response.setChunkCount(3);
        // 上传/重试走 7 参 ingest 重载（含切片模式与进度回调）；doReturn 风格避免 thenThrow 后旧 stub 被触发
        org.mockito.BDDMockito.doReturn(response)
                .when(aiServiceClient).ingest(anyLong(), anyString(), anyString(),
                        any(), any(), anyLong(), anyString());
        AiDeleteResponse delete = new AiDeleteResponse();
        delete.setDeletedCount(3);
        org.mockito.BDDMockito.doReturn(delete)
                .when(aiServiceClient).deleteFile(anyLong(), anyString());
    }

    /** 轮询文件列表直至终态（READY/FAILED），规避异步 ingest 的竞态 */
    private String awaitStatus(String token, long agentId, int maxMs) throws Exception {
        long deadline = System.currentTimeMillis() + maxMs;
        while (System.currentTimeMillis() < deadline) {
            MvcResult result = mockMvc.perform(get("/file/list")
                            .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                            .param("agentId", String.valueOf(agentId)))
                    .andExpect(status().isOk())
                    .andReturn();
            String status = objectMapper.readTree(result.getResponse().getContentAsString())
                    .path("data").path("list").path(0).path("status").asText("");
            if ("READY".equals(status) || "FAILED".equals(status)) {
                return status;
            }
            Thread.sleep(50);
        }
        throw new AssertionError("等待文件状态超时（> " + maxMs + "ms）");
    }

    @Test
    @DisplayName("上传 → 入库成功 → 列表可见 → 删除")
    void uploadListDelete() throws Exception {
        String token = registerAndLogin("alice");
        long agentId = createAgent(token);
        mockIngest();

        MockMultipartFile file = new MockMultipartFile(
                "file", "rag.md", "text/markdown", "# 测试知识".getBytes());
        MvcResult uploaded = mockMvc.perform(multipart("/file/upload")
                        .file(file)
                        .param("agentId", String.valueOf(agentId))
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.fileName").value("rag.md"))
                .andReturn();
        long docId = objectMapper.readTree(uploaded.getResponse().getContentAsString())
                .path("data").path("id").asLong();
        // 上传为异步 ingest：轮询至 READY 后再断言列表/删除
        assertEquals("READY", awaitStatus(token, agentId, 3000));

        // 列表
        mockMvc.perform(get("/file/list")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.list[0].fileName").value("rag.md"));

        // 删除
        mockMvc.perform(delete("/file/{id}", docId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));

        // 删除后列表为空
        mockMvc.perform(get("/file/list")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .param("agentId", String.valueOf(agentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    @DisplayName("AI 不可用时上传保留 PENDING，重试后入库")
    void uploadPendingThenRetry() throws Exception {
        String token = registerAndLogin("alice");
        long agentId = createAgent(token);

        // 首次 ingest 抛业务异常（模拟 AI 不可用）→ 异步线程将文档标记 FAILED
        org.mockito.BDDMockito.willThrow(
                        new com.agentforge.common.exception.BusinessException(
                                com.agentforge.common.core.ResultCode.AI_UNAVAILABLE, "AI 不可用"))
                .given(aiServiceClient).ingest(anyLong(), anyString(), anyString(),
                        any(), any(), anyLong(), anyString());
        MockMultipartFile file = new MockMultipartFile(
                "file", "note.txt", "text/plain", "内容".getBytes());
        MvcResult uploaded = mockMvc.perform(multipart("/file/upload")
                        .file(file)
                        .param("agentId", String.valueOf(agentId))
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andReturn();
        long docId = objectMapper.readTree(uploaded.getResponse().getContentAsString())
                .path("data").path("id").asLong();
        assertEquals("FAILED", awaitStatus(token, agentId, 3000));

        // 重试成功 → 异步 ingest → READY
        mockIngest();
        mockMvc.perform(post("/file/{id}/retry", docId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk());
        assertEquals("READY", awaitStatus(token, agentId, 3000));
    }

    @Test
    @DisplayName("他人不可删除/重试我的文档（20003）")
    void ownershipCheck() throws Exception {
        String ownerToken = registerAndLogin("alice");
        long agentId = createAgent(ownerToken);
        mockIngest();
        MockMultipartFile file = new MockMultipartFile(
                "file", "private.md", "text/markdown", "x".getBytes());
        MvcResult uploaded = mockMvc.perform(multipart("/file/upload")
                        .file(file)
                        .param("agentId", String.valueOf(agentId))
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + ownerToken))
                .andExpect(status().isOk())
                .andReturn();
        long docId = objectMapper.readTree(uploaded.getResponse().getContentAsString())
                .path("data").path("id").asLong();

        String otherToken = registerAndLogin("bob");
        mockMvc.perform(delete("/file/{id}", docId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));
        mockMvc.perform(post("/file/{id}/retry", docId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + otherToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20003));

        // 创建者仍可删除
        mockMvc.perform(delete("/file/{id}", docId)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + ownerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));
    }

    @Test
    @DisplayName("非法文件类型返回 40001，空文件返回 40003")
    void validation() throws Exception {
        String token = registerAndLogin("alice");
        long agentId = createAgent(token);

        MockMultipartFile bad = new MockMultipartFile(
                "file", "evil.exe", "application/octet-stream", "x".getBytes());
        mockMvc.perform(multipart("/file/upload")
                        .file(bad)
                        .param("agentId", String.valueOf(agentId))
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(40001));

        MockMultipartFile empty = new MockMultipartFile(
                "file", "empty.md", "text/markdown", new byte[0]);
        mockMvc.perform(multipart("/file/upload")
                        .file(empty)
                        .param("agentId", String.valueOf(agentId))
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(40003));
    }

    private long createAgent(String token) throws Exception {
        MvcResult result = mockMvc.perform(post("/agent")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"文档助手","systemPrompt":"测试"}"""))
                .andExpect(status().isOk())
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsString())
                .path("data").path("id").asLong();
    }
}
