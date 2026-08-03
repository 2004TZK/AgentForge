package com.agentforge.aigateway.dto;

import lombok.Data;

/**
 * AI 服务 /rag/ingest 响应。
 */
@Data
public class AiIngestResponse {

    /** 处理状态：ok / failed */
    private String status;

    /** 切分后的 Chunk 数 */
    private Integer chunkCount;
}
