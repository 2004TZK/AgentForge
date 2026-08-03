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
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
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
    private final String baseUrl;
    private final String internalToken;
    private final int connectTimeoutMs;
    private final int readTimeoutMs;

    public AiServiceClient(AiGatewayProperties properties, ObjectMapper objectMapper) {
        this.baseUrl = properties.getBaseUrl();
        this.internalToken = properties.getInternalToken();
        this.connectTimeoutMs = properties.getConnectTimeoutMs();
        this.readTimeoutMs = properties.getReadTimeoutMs();
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(connectTimeoutMs);
        factory.setReadTimeout(readTimeoutMs);
        this.objectMapper = objectMapper;
        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(factory)
                .defaultHeader("X-Internal-Token", internalToken)
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
     * 实现说明：不能使用 RestClient.exchange 返回原始响应 —— exchange 在回调返回后会关闭响应流，
     * 调用方读到的是已关闭的流。这里直接使用 HttpURLConnection 并适配为 ClientHttpResponse。
     */
    public ClientHttpResponse openStream(AiChatRequest request) throws IOException {
        try {
            HttpURLConnection connection = (HttpURLConnection) URI.create(baseUrl + "/agent/chat/stream").toURL()
                    .openConnection();
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(connectTimeoutMs);
            connection.setReadTimeout(readTimeoutMs);
            connection.setRequestProperty("Content-Type", MediaType.APPLICATION_JSON_VALUE);
            connection.setRequestProperty("X-Internal-Token", internalToken);
            byte[] body = objectMapper.writeValueAsBytes(buildBody(request));
            connection.setFixedLengthStreamingMode(body.length);
            try (OutputStream out = connection.getOutputStream()) {
                out.write(body);
            }
            return new ConnectionClientHttpResponse(connection);
        } catch (SocketTimeoutException e) {
            throw mapConnectError(new ResourceAccessException("AI 服务连接超时", e), "AI 服务连接超时");
        } catch (IOException e) {
            throw mapConnectError(new ResourceAccessException("AI 服务连接失败", e));
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

    /** 工具元数据：GET /agent/tools/meta（前端按 Schema 渲染工具配置表单） */
    public List<Map<String, Object>> getToolMeta() {
        try {
            return restClient.get()
                    .uri("/agent/tools/meta")
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, res) -> {
                        throw mapAiError(res);
                    })
                    .body(new ParameterizedTypeReference<List<Map<String, Object>>>() {
                    });
        } catch (ResourceAccessException e) {
            throw mapConnectError(e);
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
        String message = "AI 服务返回错误状态: " + statusText(res);
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
            log.warn("AI 服务错误响应解析失败: status={}, body={}", statusText(res), raw);
        }
        return new BusinessException(code, message);
    }

    /** 安全读取 HTTP 状态码（Spring 6 的 getStatusCode 声明抛 IOException） */
    private String statusText(ClientHttpResponse res) {
        try {
            return res.getStatusCode().toString();
        } catch (IOException e) {
            return "unknown";
        }
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
        body.put("userId", request.getUserId());
        body.put("toolConfigs", request.getToolConfigs());
        return body;
    }

    /**
     * HttpURLConnection → ClientHttpResponse 适配器：连接由调用方负责 close（disconnect）。
     * 状态/错误流读取与 Spring 接口语义一致，供 relayStream/mapAiError 复用。
     */
    private static final class ConnectionClientHttpResponse implements ClientHttpResponse {

        private final HttpURLConnection connection;
        private final HttpStatusCode statusCode;
        private final String statusText;

        ConnectionClientHttpResponse(HttpURLConnection connection) throws IOException {
            this.connection = connection;
            this.statusCode = HttpStatusCode.valueOf(connection.getResponseCode());
            String message = connection.getResponseMessage();
            this.statusText = message != null ? message : "";
        }

        @Override
        public HttpStatusCode getStatusCode() {
            return statusCode;
        }

        @Override
        public String getStatusText() {
            return statusText;
        }

        @Override
        public void close() {
            connection.disconnect();
        }

        @Override
        public InputStream getBody() throws IOException {
            InputStream errorStream = connection.getErrorStream();
            return errorStream != null ? errorStream : connection.getInputStream();
        }

        @Override
        public HttpHeaders getHeaders() {
            return new HttpHeaders();
        }
    }
}
