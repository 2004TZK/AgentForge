package com.agentforge.file.service.impl;

import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiDeleteResponse;
import com.agentforge.aigateway.dto.AiIngestResponse;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.file.entity.Document;
import com.agentforge.file.mapper.DocumentMapper;
import com.agentforge.file.service.FileService;
import com.agentforge.file.vo.DocumentVO;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

/**
 * 文件服务实现。
 * 链路（设计 7.4 节）：校验 → 落盘 /data/uploads/{agentId}/{uuid}.ext
 * → document(PENDING) → AI ingest → READY/FAILED。
 * AI 不可用（30002）时文件保留 PENDING，可通过重试接口恢复。
 */
@Slf4j
@Service
public class FileServiceImpl implements FileService {

    /** 允许的文件类型 */
    private static final Set<String> ALLOWED_TYPES = Set.of("pdf", "docx", "txt", "md");

    /** 文件大小上限（Spring multipart 配置 20MB，此处兜底校验） */
    private static final long MAX_FILE_SIZE = 20L * 1024 * 1024;

    private final DocumentMapper documentMapper;
    private final AiServiceClient aiServiceClient;
    private final Path uploadRoot;

    public FileServiceImpl(DocumentMapper documentMapper, AiServiceClient aiServiceClient,
                           @Value("${agentforge.upload.dir:./data/uploads}") String uploadDir) {
        this.documentMapper = documentMapper;
        this.aiServiceClient = aiServiceClient;
        this.uploadRoot = Paths.get(uploadDir).toAbsolutePath().normalize();
    }

    @Override
    public DocumentVO upload(Long agentId, MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(ResultCode.FILE_EMPTY);
        }
        if (file.getSize() > MAX_FILE_SIZE) {
            throw new BusinessException(ResultCode.FILE_TOO_LARGE);
        }
        String fileType = extractExtension(file.getOriginalFilename());
        if (!ALLOWED_TYPES.contains(fileType)) {
            throw new BusinessException(ResultCode.FILE_TYPE_NOT_ALLOWED,
                    "仅支持: " + String.join("/", ALLOWED_TYPES));
        }

        // 1. 落盘：共享卷 /data/uploads/{agentId}/{uuid}.ext
        String relativePath = agentId + "/" + UUID.randomUUID() + "." + fileType;
        Path target = uploadRoot.resolve(relativePath).normalize();
        // 防目录穿越：确保目标仍在根目录内
        if (!target.startsWith(uploadRoot)) {
            throw new BusinessException(ResultCode.PARAM_ERROR, "非法文件路径");
        }
        try {
            Files.createDirectories(target.getParent());
            file.transferTo(target);
        } catch (IOException e) {
            log.error("文件落盘失败: path={}", relativePath, e);
            throw new BusinessException(ResultCode.SYSTEM_ERROR, "文件保存失败");
        }

        // 2. 写 document 行（PENDING）
        Document document = new Document();
        document.setAgentId(agentId);
        document.setFileName(file.getOriginalFilename());
        document.setFilePath(relativePath);
        document.setFileType(fileType);
        document.setStatus("PENDING");
        documentMapper.insert(document);

        // 3. 调 AI 入库（同步；失败保留 PENDING 可重试）
        try {
            document.setStatus("PROCESSING");
            documentMapper.updateById(document);
            AiIngestResponse response = aiServiceClient.ingest(agentId,
                    file.getOriginalFilename(), relativePath);
            document.setStatus("ok".equalsIgnoreCase(response.getStatus()) ? "READY" : "FAILED");
            log.info("文档入库完成: id={}, fileName={}, chunkCount={}",
                    document.getId(), document.getFileName(),
                    response.getChunkCount() == null ? 0 : response.getChunkCount());
        } catch (BusinessException e) {
            log.warn("文档入库失败，状态保留 PENDING 可重试: id={}, err={}", document.getId(), e.getMessage());
            document.setStatus("PENDING");
        } finally {
            documentMapper.updateById(document);
        }
        return toVO(document);
    }

    @Override
    public PageResult<DocumentVO> list(Long agentId, long page, long size) {
        IPage<Document> result = documentMapper.selectPage(Page.of(page, size),
                new LambdaQueryWrapper<Document>()
                        .eq(Document::getAgentId, agentId)
                        .orderByDesc(Document::getId));
        List<DocumentVO> list = result.getRecords().stream().map(this::toVO).toList();
        return PageResult.of(list, result.getTotal(), page, size);
    }

    @Override
    @Transactional
    public void delete(Long documentId) {
        Document document = getDocumentOrThrow(documentId);
        String relativePath = document.getFilePath();

        // 1. 删除 Qdrant 向量（失败仅记录日志，不阻断元数据删除）
        try {
            AiDeleteResponse response = aiServiceClient.deleteFile(document.getAgentId(), document.getFileName());
            log.info("删除文档向量: id={}, deletedCount={}", documentId,
                    response.getDeletedCount() == null ? 0 : response.getDeletedCount());
        } catch (BusinessException e) {
            log.warn("删除 Qdrant 向量失败（已忽略）: id={}, err={}", documentId, e.getMessage());
        }

        // 2. 逻辑删除元数据
        documentMapper.deleteById(documentId);

        // 3. 删除磁盘文件
        if (StringUtils.hasText(relativePath)) {
            try {
                Files.deleteIfExists(uploadRoot.resolve(relativePath));
            } catch (IOException e) {
                log.warn("删除磁盘文件失败: path={}", relativePath, e);
            }
        }
    }

    @Override
    public DocumentVO retryIngest(Long documentId) {
        Document document = getDocumentOrThrow(documentId);
        if ("READY".equals(document.getStatus())) {
            throw new BusinessException(ResultCode.BUSINESS_ERROR, "该文档已入库完成，无需重试");
        }
        try {
            document.setStatus("PROCESSING");
            documentMapper.updateById(document);
            AiIngestResponse response = aiServiceClient.ingest(document.getAgentId(),
                    document.getFileName(), document.getFilePath());
            document.setStatus("ok".equalsIgnoreCase(response.getStatus()) ? "READY" : "FAILED");
        } catch (BusinessException e) {
            document.setStatus("FAILED");
            throw e;
        } finally {
            documentMapper.updateById(document);
        }
        return toVO(document);
    }

    private Document getDocumentOrThrow(Long documentId) {
        Document document = documentMapper.selectById(documentId);
        if (document == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "文档不存在");
        }
        return document;
    }

    /** 提取小写扩展名（不含点） */
    private String extractExtension(String fileName) {
        if (!StringUtils.hasText(fileName) || !fileName.contains(".")) {
            return "";
        }
        return fileName.substring(fileName.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
    }

    private DocumentVO toVO(Document document) {
        return DocumentVO.builder()
                .id(document.getId())
                .agentId(document.getAgentId())
                .fileName(document.getFileName())
                .fileType(document.getFileType())
                .status(document.getStatus())
                .createdTime(document.getCreatedTime())
                .build();
    }
}
