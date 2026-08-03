package com.agentforge.aigateway.client;

import com.agentforge.aigateway.config.AiGatewayProperties;
import com.agentforge.aigateway.dto.AiChatRequest;
import com.agentforge.aigateway.dto.AiChatResponse;
import com.agentforge.aigateway.dto.AiDeleteResponse;
import com.agentforge.aigateway.dto.AiIngestResponse;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.io.InputStream;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * Python AI Service HTTP 客户端。
 * - 所有请求携带 X-Internal-Token 内部鉴权头（与用户 JWT 体系隔离）
 * - 错误映射（与 AI 服务结构化错误码 {"code","message"} 对齐）：
 *   30001 超时         → ResultCode.AI_TIMEOUT
 *   30002 服务不可用   → ResultCode.AI_UNAVAILABLE（连接失败/服务未启动）
 *   30003 模型错误     → ResultCode.LLM_ERROR（模型未拉取、返回异常等）
 * - chat 不自动重试（避免重复计费）；ingest 等幂等操作由调用方决定重试
 */
@Slf4j
@Component
@EnableConfigurationProperties(AiGatewayProperties.class)
public class AiServiceClient {

    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public AiServiceClient(AiGatewayProperties properties, ObjectMapper objectMapper) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(properties.getConnectTimeoutMs());
        factory.setReadTimeout(properties.getReadTimeoutMs());
        this.objectMapper = objectMapper;
        this.restClient = RestClient.builder()
                .baseUrl(properties.getBaseUrl())
                .requestFactory(factory)
                .defaultHeader("X-Internal-Token", properties.getInternalToken())
                .build();
    }

    /** 对话执行：POST /agent/chat */
    public AiChatResponse chat(AiChatRequest request) {
        try {
            return restClient.post()
                    .uri("/agent/chat")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(buildBody(request))
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, res) -> {
                        throw mapAiError(res);
                    })
                    .body(AiChatResponse.class);
        } catch (ResourceAccessException e) {
            throw mapConnectError(e);
        }
    }

    /**
     * 打开流式对话连接：POST /agent/chat/stream。
     * 返回原始响应（SSE 字节流由调用方透传）；连接失败抛出映射后的业务异常。
     * 注意：exchange 不会对错误状态码抛异常，调用方需自行检查状态并调用 {@link #mapAiError}。
     */
    public ClientHttpResponse openStream(AiChatRequest request) {
        try {
            return restClient.post()
                    .uri("/agent/chat/stream")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(buildBody(request))
                    .exchange((req, res) -> res);
        } catch (ResourceAccessException e) {
            throw mapConnectError(e);
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
                        throw mapAiError(res, ResultCode.RAG_ERROR);
                    })
                    .body(AiIngestResponse.class);
        } catch (ResourceAccessException e) {
            throw mapConnectError(e, "知识库处理超时");
        }
    }

    /** 删除文档向量：DELETE /rag/file */
    public AiDeleteResponse deleteFile(Long agentId, String fileName) {
        try {
            return restClient.delete()
                    .uri("/rag/file?agentId={agentId}&fileName={fileName}", agentId, fileName)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, res) -> {
                        throw mapAiError(res, ResultCode.RAG_ERROR);
                    })
                    .body(AiDeleteResponse.class);
        } catch (ResourceAccessException e) {
            throw mapConnectError(e, "删除文档向量超时");
        }
    }

    // ---------------- 错误映射 ----------------

    /**
     * 将 AI 服务错误响应映射为业务异常：优先读取结构化错误体 {"code", "message"}，
     * 未知响应默认按模型错误（30003）处理。
     */
    public BusinessException mapAiError(ClientHttpResponse res) {
        return mapAiError(res, ResultCode.LLM_ERROR);
    }

    /**
     * 将 AI 服务错误响应映射为业务异常（可指定未知错误的兜底码，如 RAG 接口用 40004）。
     */
    public BusinessException mapAiError(ClientHttpResponse res, ResultCode fallback) {
        String raw = readBody(res);
        ResultCode code = fallback;
        String message = "AI 服务返回错误状态: " + res.getStatusCode();
        try {
            JsonNode node = objectMapper.readTree(raw);
            int c = node.path("code").asInt(0);
            if (c > 0) {
                code = switch (c) {
                    case 30001 -> ResultCode.AI_TIMEOUT;
                    case 30002 -> ResultCode.AI_UNAVAILABLE;
                    default -> fallback;
                };
            }
            String m = node.path("message").asText("");
            if (StringUtils.hasText(m)) {
                message = m;
            }
        } catch (IOException e) {
            log.warn("AI 服务错误响应解析失败: status={}, body={}", res.getStatusCode(), raw);
        }
        return new BusinessException(code, message);
    }

    private BusinessException mapConnectError(ResourceAccessException e) {
        return mapConnectError(e, "AI 服务响应超时");
    }

    private BusinessException mapConnectError(ResourceAccessException e, String timeoutMessage) {
        // 超时（连接/读取）抛 SocketTimeoutException；其余（拒绝连接、DNS 失败）视为服务不可用
        if (e.getCause() instanceof SocketTimeoutException) {
            log.error("调用 AI 服务超时: {}", e.getMessage());
            return new BusinessException(ResultCode.AI_TIMEOUT, timeoutMessage);
        }
        log.error("调用 AI 服务不可达: {}", e.getMessage());
        return new BusinessException(ResultCode.AI_UNAVAILABLE, "AI 服务不可用，请确认服务已启动");
    }

    private String readBody(ClientHttpResponse res) {
        try (InputStream in = res.getBody()) {
            if (in == null) {
                return "";
            }
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            log.warn("读取 AI 服务错误响应失败", e);
            return "";
        }
    }

    private Map<String, Object> buildBody(AiChatRequest request) {
        Map<String, Object> body = new HashMap<>();
        body.put("agentId", request.getAgentId());
        body.put("message", request.getMessage());
        body.put("history", request.getHistory());
        body.put("systemPrompt", request.getSystemPrompt());
        body.put("modelName", request.getModelName());
        body.put("temperature", request.getTemperature());
        body.put("tools", request.getTools());
        return body;
    }
}
