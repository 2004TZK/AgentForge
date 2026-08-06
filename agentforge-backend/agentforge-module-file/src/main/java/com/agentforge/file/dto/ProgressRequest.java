package com.agentforge.file.dto;

import lombok.Data;

/**
 * AI 服务入库进度回调请求体（内部接口 POST /file/{id}/progress，X-Internal-Token 校验）。
 * 字段均可选：AI 服务分批回写 processedChunks/totalChunks，完成/失败时回写 status。
 */
@Data
public class ProgressRequest {

    /** 文档 ID（与 URL 路径一致，双重校验） */
    private Long documentId;

    /** 处理状态：ok / failed（完成或失败时回写） */
    private String status;

    /** 总切片数（完成时回写） */
    private Integer chunkCount;

    /** 已入库 chunk 数 */
    private Integer processedChunks;

    /** 总 chunk 数（解析完成后回写） */
    private Integer totalChunks;

    /** 失败原因（status=failed 时） */
    private String error;
}
