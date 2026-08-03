package com.agentforge.aigateway.client;

import com.agentforge.aigateway.config.AiGatewayProperties;
import com.agentforge.aigateway.dto.AiChatRequest;
import com.agentforge.aigateway.dto.AiChatResponse;
import com.agentforge.aigateway.dto.AiDeleteResponse;
import com.agentforge.aigateway.dto.AiIngestResponse;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.util.HashMap;
import java.util.Map;

/**
 * Python AI Service HTTP 客户端。
 * - 所有请求携带 X-Internal-Token 内部鉴权头（与用户 JWT 体系隔离）
 * - 连接超时 5s、读取超时 60s（可配置）；超时返回 30001
 * - chat 不自动重试（避免重复计费）；ingest 等幂等操作由调用方决定重试
 */
@Slf4j
@Component
@EnableConfigurationProperties(AiGatewayProperties.class)
public class AiServiceClient {

    private final RestClient restClient;
    private final String internalToken;

    public AiServiceClient(AiGatewayProperties properties) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(properties.getConnectTimeoutMs());
        factory.setReadTimeout(properties.getReadTimeoutMs());
        this.internalToken = properties.getInternalToken();
        this.restClient = RestClient.builder()
                .baseUrl(properties.getBaseUrl())
                .requestFactory(factory)
                .defaultHeader("X-Internal-Token", properties.getInternalToken())
                .build();
    }

    /** 对话执行：POST /agent/chat */
    public AiChatResponse chat(AiChatRequest request) {
        Map<String, Object> body = new HashMap<>();
        body.put("agentId", request.getAgentId());
        body.put("message", request.getMessage());
        body.put("history", request.getHistory());
        body.put("systemPrompt", request.getSystemPrompt());
        body.put("modelName", request.getModelName());
        body.put("temperature", request.getTemperature());
        body.put("tools", request.getTools());
        try {
            return restClient.post()
                    .uri("/agent/chat")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, res) -> {
                        throw new BusinessException(ResultCode.LLM_ERROR,
                                "AI 服务返回错误状态: " + res.getStatusCode());
                    })
                    .body(AiChatResponse.class);
        } catch (ResourceAccessException e) {
            log.error("调用 AI 服务失败（超时或不可达）: {}", e.getMessage());
            throw new BusinessException(ResultCode.AI_TIMEOUT);
        }
    }

    /** 文档入库：POST /rag/ingest（幂等，调用方可按需重试） */
    public AiIngestResponse ingest(Long agentId, String fileName, String filePath) {
        Map<String, Object> body = new HashMap<>();
        body.put("agentId", agentId);
        body.put("fileName", fileName);
        body.put("filePath", filePath);
        try {
            return restClient.post()
                    .uri("/rag/ingest")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, res) -> {
                        throw new BusinessException(ResultCode.RAG_ERROR,
                                "RAG 入库失败: " + res.getStatusCode());
                    })
                    .body(AiIngestResponse.class);
        } catch (ResourceAccessException e) {
            log.error("RAG 入库调用失败（超时或不可达）: {}", e.getMessage());
            throw new BusinessException(ResultCode.AI_TIMEOUT, "知识库处理超时");
        }
    }

    /** 删除文档向量：DELETE /rag/file */
    public AiDeleteResponse deleteFile(Long agentId, String fileName) {
        try {
            return restClient.delete()
                    .uri("/rag/file?agentId={agentId}&fileName={fileName}", agentId, fileName)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, res) -> {
                        throw new BusinessException(ResultCode.RAG_ERROR,
                                "删除文档向量失败: " + res.getStatusCode());
                    })
                    .body(AiDeleteResponse.class);
        } catch (ResourceAccessException e) {
            log.error("删除文档向量调用失败: {}", e.getMessage());
            throw new BusinessException(ResultCode.AI_TIMEOUT, "删除文档向量超时");
        }
    }
}
