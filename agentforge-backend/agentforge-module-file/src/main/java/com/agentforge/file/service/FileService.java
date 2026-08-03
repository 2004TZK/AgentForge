package com.agentforge.file.service;

import com.agentforge.common.core.PageResult;
import com.agentforge.file.vo.DocumentVO;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文件服务：上传（落盘 + RAG 入库编排）、列表、删除、失败重试。
 */
public interface FileService {

    /**
     * 上传文档：校验类型/大小 → 落盘共享卷 → 写 document(PENDING)
     * → 调 AI /rag/ingest → 更新 READY/FAILED。
     */
    DocumentVO upload(Long agentId, MultipartFile file);

    /** 文档列表（按创建时间倒序） */
    PageResult<DocumentVO> list(Long agentId, long page, long size);

    /**
     * 删除文档：删除 Qdrant 向量 → 逻辑删除元数据 → 删除磁盘文件。
     * AI 删除失败仅记录日志，不阻断元数据删除。
     */
    void delete(Long documentId, Long operatorId);

    /** 重试 RAG 入库（PENDING/FAILED 状态），幂等操作支持重试 */
    DocumentVO retryIngest(Long documentId, Long operatorId);
}
