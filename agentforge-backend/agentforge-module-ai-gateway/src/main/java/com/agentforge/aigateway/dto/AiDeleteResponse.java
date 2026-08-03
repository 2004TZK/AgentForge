package com.agentforge.aigateway.dto;

import lombok.Data;

/**
 * AI 服务 DELETE /rag/file 响应。
 */
@Data
public class AiDeleteResponse {

    /** 删除的向量点数量 */
    private Integer deletedCount;
}
