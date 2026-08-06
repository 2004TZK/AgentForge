package com.agentforge.file.service;

import com.agentforge.aigateway.dto.AiPreviewResponse;
import com.agentforge.common.core.PageResult;
import com.agentforge.file.dto.ProgressRequest;
import com.agentforge.file.vo.DocumentVO;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文件服务：上传（落盘 + 异步入库编排）、列表、删除、失败重试、切片预览、进度回写。
 */
public interface FileService {

    /**
     * 上传文档：校验类型/大小/内容 → 落盘共享卷 → 写 document(PENDING)
     * → 异步调 AI /rag/ingest（后台线程执行，避免大文件同步阻塞 HTTP）。
     * slicingMode=manual 时 slicingConfig（JSON）随 document 持久化，重试沿用。
     */
    DocumentVO upload(Long agentId, MultipartFile file, String slicingMode, String slicingConfig);

    /** 文档列表（按创建时间倒序） */
    PageResult<DocumentVO> list(Long agentId, long page, long size);

    /**
     * 删除文档：删除 Qdrant 向量 → 逻辑删除元数据 → 删除磁盘文件。
     * AI 删除失败仅记录日志，不阻断元数据删除。
     */
    void delete(Long documentId, Long operatorId);

    /** 重试 RAG 入库（PENDING/FAILED 状态），沿用已保存的切片配置，异步执行 */
    DocumentVO retryIngest(Long documentId, Long operatorId);

    /**
     * 手动切片预览（内部接口调用链）：临时落盘 → AI /rag/preview → 清理临时文件。
     * 只读解析结构 + 样例 chunk，不入库。
     */
    AiPreviewResponse preview(MultipartFile file, String slicingMode, String slicingConfig);

    /** 入库进度回写（AI 服务回调内部接口，X-Internal-Token 校验在 Controller 层） */
    void updateProgress(Long documentId, ProgressRequest request);
}
