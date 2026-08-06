package com.agentforge.file.service.impl;

import com.agentforge.agent.mapper.AgentMapper;
import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiDeleteResponse;
import com.agentforge.aigateway.dto.AiIngestResponse;
import com.agentforge.aigateway.dto.AiPreviewResponse;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.file.dto.ProgressRequest;
import com.agentforge.file.entity.Document;
import com.agentforge.file.mapper.DocumentMapper;
import com.agentforge.file.service.FileService;
import com.agentforge.file.vo.DocumentVO;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * 文件服务实现。
 * 链路（设计 v0.2）：校验（类型白名单 + 大小上限 + 内容嗅探）→ 落盘共享卷
 * → document(PENDING) → 后台线程异步 AI ingest（进度经内部接口回写）→ READY/FAILED。
 * 入库异步化后 upload 立即返回，前端轮询收敛状态（设计 11.1 节）。
 */
@Slf4j
@Service
public class FileServiceImpl implements FileService {

    /** 允许的文件类型（第一期：原有文档 + SQLite/CSV；sql/xlsx/xls 后续阶段追加） */
    private static final Set<String> ALLOWED_TYPES =
            Set.of("pdf", "docx", "txt", "md", "db", "sqlite", "sqlite3", "csv");

    /** 数据库/表格类类型（需结构化内容嗅探） */
    private static final Set<String> DATABASE_TYPES = Set.of("db", "sqlite", "sqlite3", "csv");

    /** SQLite 魔数头："SQLite format 3\0" */
    private static final byte[] SQLITE_MAGIC = "SQLite format 3\u0000".getBytes(StandardCharsets.US_ASCII);
    /** PDF 魔数头："%PDF" */
    private static final byte[] PDF_MAGIC = "%PDF".getBytes(StandardCharsets.US_ASCII);
    /** ZIP 魔数头（docx 为 ZIP 容器） */
    private static final byte[] ZIP_MAGIC = {'P', 'K'};

    /** 文件大小上限（默认 50MB，可配置 agentforge.upload.max-size） */
    private final long maxFileSize;

    /** 入库进度回写基础地址（AI 服务回调后端内部接口） */
    private final String progressBaseUrl;

    /** 手动切片参数上限（与 AI 服务 manual_max_chunk_rows/tokens 保持一致，可配置） */
    private final int manualMaxChunkRows;
    private final int manualMaxChunkTokens;

    /** 进行中的入库任务（服务停机时回滚为 PENDING，避免重启后永久 PROCESSING） */
    private final Set<Long> inFlightIngest = ConcurrentHashMap.newKeySet();

    /** 入库异步线程池：大文件解析+Embedding 可能耗时数分钟，不阻塞 HTTP 线程 */
    private final ExecutorService ingestExecutor = Executors.newFixedThreadPool(2, r -> {
        Thread t = new Thread(r, "ingest-worker");
        t.setDaemon(true);
        return t;
    });

    private final DocumentMapper documentMapper;
    private final AiServiceClient aiServiceClient;
    private final AgentMapper agentMapper;
    private final Path uploadRoot;

    public FileServiceImpl(DocumentMapper documentMapper, AiServiceClient aiServiceClient,
                           AgentMapper agentMapper,
                           @Value("${agentforge.upload.dir:./data/uploads}") String uploadDir,
                           @Value("${agentforge.upload.max-size:52428800}") long maxFileSize,
                           @Value("${agentforge.upload.progress-base-url:http://localhost:8080/api}")
                               String progressBaseUrl,
                           @Value("${agentforge.upload.manual-max-chunk-rows:500}") int manualMaxChunkRows,
                           @Value("${agentforge.upload.manual-max-chunk-tokens:2000}") int manualMaxChunkTokens) {
        this.documentMapper = documentMapper;
        this.aiServiceClient = aiServiceClient;
        this.agentMapper = agentMapper;
        this.uploadRoot = Paths.get(uploadDir).toAbsolutePath().normalize();
        this.maxFileSize = maxFileSize;
        this.progressBaseUrl = progressBaseUrl.endsWith("/")
                ? progressBaseUrl.substring(0, progressBaseUrl.length() - 1) : progressBaseUrl;
        this.manualMaxChunkRows = manualMaxChunkRows;
        this.manualMaxChunkTokens = manualMaxChunkTokens;
    }

    @PreDestroy
    void shutdown() {
        ingestExecutor.shutdownNow();
        try {
            if (!ingestExecutor.awaitTermination(5, TimeUnit.SECONDS)) {
                log.warn("入库线程池未在 5s 内终止，存在进行中任务");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        // 兜底：把仍处于 PROCESSING 的进行中任务回滚为 PENDING（重试入口可恢复）
        for (Long id : inFlightIngest) {
            try {
                Document doc = documentMapper.selectById(id);
                if (doc != null && "PROCESSING".equals(doc.getStatus())) {
                    doc.setStatus("PENDING");
                    documentMapper.updateById(doc);
                    log.info("停机回滚进行中任务: id={}", id);
                }
            } catch (Exception e) {
                log.warn("停机回滚任务状态失败: id={}", id, e);
            }
        }
        inFlightIngest.clear();
    }

    @Override
    public DocumentVO upload(Long agentId, MultipartFile file, String slicingMode, String slicingConfig) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(ResultCode.FILE_EMPTY);
        }
        if (file.getSize() > maxFileSize) {
            throw new BusinessException(ResultCode.FILE_TOO_LARGE,
                    "文件大小超出限制（" + (maxFileSize / 1024 / 1024) + "MB）");
        }
        String fileType = extractExtension(file.getOriginalFilename());
        if (!ALLOWED_TYPES.contains(fileType)) {
            throw new BusinessException(ResultCode.FILE_TYPE_NOT_ALLOWED,
                    "仅支持: " + String.join("/", ALLOWED_TYPES));
        }
        // 切片方式校验：auto / manual；manual 时校验 JSON 合法性
        String mode = normalizeSlicingMode(slicingMode);
        String configJson = null;
        if ("manual".equals(mode)) {
            configJson = normalizeSlicingConfig(slicingConfig);
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
            verifyContent(fileType, target);
        } catch (BusinessException e) {
            cleanupFile(target);
            throw e;
        } catch (IOException e) {
            log.error("文件落盘失败: path={}", relativePath, e);
            throw new BusinessException(ResultCode.SYSTEM_ERROR, "文件保存失败");
        }

        // 2. 同名覆盖策略：逻辑删除旧版本并清理旧向量（M2）
        //    先删向量再入库，避免旧 chunk 数多于新文档时残留孤儿向量
        List<Document> existing = documentMapper.selectList(
                new LambdaQueryWrapper<Document>()
                        .eq(Document::getAgentId, agentId)
                        .eq(Document::getFileName, file.getOriginalFilename()));
        for (Document old : existing) {
            try {
                AiDeleteResponse response = aiServiceClient.deleteFile(agentId, old.getFileName());
                log.info("同名覆盖清理旧向量: id={}, deletedCount={}", old.getId(),
                        response.getDeletedCount() == null ? 0 : response.getDeletedCount());
            } catch (BusinessException e) {
                log.warn("同名覆盖清理旧向量失败（旧文档仍删除，向量由新入库覆盖）: id={}, err={}",
                        old.getId(), e.getMessage());
            }
            documentMapper.deleteById(old.getId());
        }

        // 3. 写 document 行（PENDING，携带切片方式与配置快照）
        Document document = new Document();
        document.setAgentId(agentId);
        document.setFileName(file.getOriginalFilename());
        document.setFilePath(relativePath);
        document.setFileType(fileType);
        document.setStatus("PENDING");
        document.setSlicingMode(mode);
        document.setSlicingConfig(configJson);
        documentMapper.insert(document);

        // 4. 异步调 AI 入库（后台线程；进度经内部接口回写，前端轮询列表收敛状态）
        ingestExecutor.execute(() -> ingestAsync(document));
        log.info("文档上传完成，异步入库已提交: id={}, fileName={}, mode={}", document.getId(),
                document.getFileName(), mode);
        return toVO(document);
    }

    /** 后台线程执行入库：PROCESSING → AI ingest（含进度回调）→ READY/FAILED */
    private void ingestAsync(Document document) {
        inFlightIngest.add(document.getId());
        try {
            document.setStatus("PROCESSING");
            documentMapper.updateById(document);
            String progressUrl = progressBaseUrl + "/file/" + document.getId() + "/progress";
            AiIngestResponse response = aiServiceClient.ingest(
                    document.getAgentId(), document.getFileName(), document.getFilePath(),
                    document.getSlicingMode(), document.getSlicingConfig(),
                    document.getId(), progressUrl);
            int chunkCount = response.getChunkCount() == null ? 0 : response.getChunkCount();
            document.setStatus("ok".equalsIgnoreCase(response.getStatus()) ? "READY" : "FAILED");
            document.setChunkCount(chunkCount);
            // AI 服务已在入库过程中经 progressUrl 回写进度，此处兜底保证终态一致
            document.setProcessedChunks(chunkCount);
            document.setTotalChunks(chunkCount);
            log.info("文档入库完成: id={}, fileName={}, chunkCount={}", document.getId(),
                    document.getFileName(), chunkCount);
        } catch (BusinessException e) {
            if (Thread.currentThread().isInterrupted()) {
                document.setStatus("PENDING");
                log.warn("入库任务被中断（服务停机），保留 PENDING 待重试: id={}", document.getId());
            } else {
                document.setStatus("FAILED");
                log.warn("文档入库失败: id={}, err={}", document.getId(), e.getMessage());
            }
        } catch (Exception e) {
            if (Thread.currentThread().isInterrupted()) {
                document.setStatus("PENDING");
                log.warn("入库任务被中断（服务停机），保留 PENDING 待重试: id={}", document.getId());
            } else {
                document.setStatus("FAILED");
                log.error("文档入库异常: id={}", document.getId(), e);
            }
        } finally {
            documentMapper.updateById(document);
            inFlightIngest.remove(document.getId());
        }
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
    public void delete(Long documentId, Long operatorId) {
        Document document = getDocumentOrThrow(documentId);
        checkOwner(document, operatorId);
        String relativePath = document.getFilePath();

        // 1. 删除 Qdrant 向量（失败抛出业务异常，事务回滚元数据删除，
        //    避免"元数据已删、向量残留"的集合不一致；用户可重试删除）
        AiDeleteResponse response = aiServiceClient.deleteFile(document.getAgentId(), document.getFileName());
        log.info("删除文档向量: id={}, deletedCount={}", documentId,
                response.getDeletedCount() == null ? 0 : response.getDeletedCount());

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
    public DocumentVO retryIngest(Long documentId, Long operatorId) {
        Document document = getDocumentOrThrow(documentId);
        checkOwner(document, operatorId);
        if ("READY".equals(document.getStatus())) {
            throw new BusinessException(ResultCode.BUSINESS_ERROR, "该文档已入库完成，无需重试");
        }
        // 重试沿用该文件保存的切片配置（slicing_mode / slicing_config），无需重新填写
        document.setStatus("PENDING");
        document.setProcessedChunks(0);
        documentMapper.updateById(document);
        ingestExecutor.execute(() -> ingestAsync(document));
        return toVO(document);
    }

    @Override
    public AiPreviewResponse preview(MultipartFile file, String slicingMode, String slicingConfig) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(ResultCode.FILE_EMPTY);
        }
        String fileType = extractExtension(file.getOriginalFilename());
        if (!ALLOWED_TYPES.contains(fileType) || !DATABASE_TYPES.contains(fileType)) {
            throw new BusinessException(ResultCode.FILE_TYPE_NOT_ALLOWED,
                    "手动切片预览仅支持数据库/表格类文件: db/sqlite/sqlite3/csv");
        }
        if (file.getSize() > maxFileSize) {
            throw new BusinessException(ResultCode.FILE_TOO_LARGE);
        }
        // 临时落盘（共享卷 preview-tmp 子目录，AI 服务按同一根目录读取）→ 预览 → 清理
        Path tmpDir = uploadRoot.resolve("preview-tmp");
        Path tmp = tmpDir.resolve(UUID.randomUUID() + "." + fileType);
        try {
            Files.createDirectories(tmpDir);
            file.transferTo(tmp);
            verifyContent(fileType, tmp);
            return aiServiceClient.preview(file.getOriginalFilename(),
                    "preview-tmp/" + tmp.getFileName(), slicingMode, slicingConfig);
        } catch (BusinessException e) {
            cleanupFile(tmp);
            throw e;
        } catch (IOException e) {
            log.error("预览文件落盘失败", e);
            throw new BusinessException(ResultCode.SYSTEM_ERROR, "预览文件保存失败");
        } finally {
            cleanupFile(tmp);
        }
    }

    @Override
    public void updateProgress(Long documentId, ProgressRequest request) {
        Document document = documentMapper.selectById(documentId);
        if (document == null) {
            log.warn("进度回写目标文档不存在: id={}", documentId);
            return;
        }
        if (request.getProcessedChunks() != null) {
            document.setProcessedChunks(request.getProcessedChunks());
        }
        if (request.getTotalChunks() != null) {
            document.setTotalChunks(request.getTotalChunks());
        }
        if (request.getChunkCount() != null) {
            document.setChunkCount(request.getChunkCount());
        }
        if (StringUtils.hasText(request.getStatus())) {
            document.setStatus("ok".equalsIgnoreCase(request.getStatus()) ? "READY" : "FAILED");
        }
        if (StringUtils.hasText(request.getError())) {
            log.warn("入库进度回写携带错误: id={}, error={}", documentId, request.getError());
        }
        documentMapper.updateById(document);
    }

    private Document getDocumentOrThrow(Long documentId) {
        Document document = documentMapper.selectById(documentId);
        if (document == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "文档不存在");
        }
        return document;
    }

    /** M4 归属校验：仅文档所属 Agent 的创建者可删除/重试 */
    private void checkOwner(Document document, Long operatorId) {
        com.agentforge.agent.entity.Agent agent = agentMapper.selectById(document.getAgentId());
        if (agent == null || !agent.getCreatorId().equals(operatorId)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "仅智能体创建者可管理文档");
        }
    }

    /** 提取小写扩展名（不含点） */
    private String extractExtension(String fileName) {
        if (!StringUtils.hasText(fileName) || !fileName.contains(".")) {
            return "";
        }
        return fileName.substring(fileName.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
    }

    /** 切片方式归一化：缺省 auto；非法值报错 */
    private String normalizeSlicingMode(String slicingMode) {
        String mode = StringUtils.hasText(slicingMode)
                ? slicingMode.toLowerCase(Locale.ROOT) : "auto";
        if (!"auto".equals(mode) && !"manual".equals(mode)) {
            throw new BusinessException(ResultCode.PARAM_ERROR, "切片方式仅支持 auto / manual");
        }
        return mode;
    }

    /**
     * 手动切片配置归一化：校验 JSON 合法 + 参数范围（与 AI 服务 _resolve_db_config
     * / _resolve_text_config 保持一致，上限可配置），非法立即拒绝，避免入库后才失败。
     */
    private String normalizeSlicingConfig(String slicingConfig) {
        if (!StringUtils.hasText(slicingConfig)) {
            throw new BusinessException(ResultCode.PARAM_ERROR, "手动切片模式必须提供 slicingConfig");
        }
        Object parsed;
        try {
            parsed = new com.fasterxml.jackson.databind.ObjectMapper()
                    .readValue(slicingConfig, Object.class);
        } catch (IOException e) {
            throw new BusinessException(ResultCode.PARAM_ERROR, "slicingConfig 不是合法的 JSON");
        }
        if (!(parsed instanceof java.util.Map<?, ?> map)) {
            throw new BusinessException(ResultCode.PARAM_ERROR, "slicingConfig 必须为 JSON 对象");
        }
        // 数据库类参数（与 AI _resolve_db_config 一致）
        parseIntParam(map, "chunkRows", 1, manualMaxChunkRows);
        requireBoolean(map, "byTable");
        requireBoolean(map, "keepHeader");
        requireStringList(map, "excludeTables");
        requireStringList(map, "excludeColumns");
        // 文本类参数（与 AI _resolve_text_config 一致）
        parseIntParam(map, "chunkSizeTokens", 1, manualMaxChunkTokens);
        parseIntParam(map, "chunkOverlapTokens", 0, manualMaxChunkTokens);
        return slicingConfig;
    }

    /** 校验整数参数范围（未提供时返回 -1，不报错） */
    private int parseIntParam(Map<?, ?> map, String key, int min, int max) {
        Object value = map.get(key);
        if (value == null) {
            return -1;
        }
        int parsed;
        if (value instanceof Number number) {
            parsed = number.intValue();
        } else if (value instanceof String s) {
            try {
                parsed = Integer.parseInt(s.trim());
            } catch (NumberFormatException e) {
                throw new BusinessException(ResultCode.PARAM_ERROR, key + " 必须为整数");
            }
        } else {
            throw new BusinessException(ResultCode.PARAM_ERROR, key + " 必须为整数");
        }
        if (parsed < min || parsed > max) {
            throw new BusinessException(ResultCode.PARAM_ERROR,
                    key + " 需在 " + min + "-" + max + " 之间");
        }
        return parsed;
    }

    /** 校验布尔参数类型（未提供时不报错） */
    private void requireBoolean(Map<?, ?> map, String key) {
        Object value = map.get(key);
        if (value != null && !(value instanceof Boolean)) {
            throw new BusinessException(ResultCode.PARAM_ERROR, key + " 必须为布尔值");
        }
    }

    /** 校验字符串数组参数（未提供时不报错） */
    private void requireStringList(Map<?, ?> map, String key) {
        Object value = map.get(key);
        if (value == null) {
            return;
        }
        if (!(value instanceof java.util.List<?> list)) {
            throw new BusinessException(ResultCode.PARAM_ERROR, key + " 必须为字符串数组");
        }
        for (Object item : list) {
            if (!(item instanceof String)) {
                throw new BusinessException(ResultCode.PARAM_ERROR, key + " 必须为字符串数组");
            }
        }
    }

    /** 内容嗅探（Magic Number）校验：防扩展名伪造（安全 §11.2） */
    private void verifyContent(String fileType, Path path) throws IOException {
        try (InputStream in = Files.newInputStream(path)) {
            byte[] head = in.readNBytes(16);
            switch (fileType) {
                case "pdf":
                    if (!startsWith(head, PDF_MAGIC)) {
                        throw new BusinessException(ResultCode.FILE_CONTENT_INVALID, "文件内容不是有效的 PDF");
                    }
                    break;
                case "docx":
                    if (!startsWith(head, ZIP_MAGIC)) {
                        throw new BusinessException(ResultCode.FILE_CONTENT_INVALID, "文件内容不是有效的 docx");
                    }
                    break;
                case "db", "sqlite", "sqlite3":
                    if (!startsWith(head, SQLITE_MAGIC)) {
                        throw new BusinessException(ResultCode.FILE_CONTENT_INVALID,
                                "文件内容不是有效的 SQLite 数据库");
                    }
                    break;
                case "csv", "txt", "md":
                    if (!isTextReadable(head)) {
                        throw new BusinessException(ResultCode.FILE_CONTENT_INVALID, "文件内容不是可读文本");
                    }
                    break;
                default:
                    break;
            }
        }
    }

    private boolean startsWith(byte[] data, byte[] prefix) {
        if (data.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (data[i] != prefix[i]) {
                return false;
            }
        }
        return true;
    }

    /** 文本可读性：无 NUL 字节且可被 UTF-8/GB18030 严格解码（中文 CSV 常见 GBK） */
    private boolean isTextReadable(byte[] head) {
        if (head.length == 0) {
            return false;
        }
        for (byte b : head) {
            if (b == 0) {
                return false;
            }
        }
        return canDecode(head, StandardCharsets.UTF_8)
                || canDecode(head, Charset.forName("GB18030"));
    }

    /** 严格解码校验：非法字节序列（UTF-8/GB18030）视为不可读，杜绝二进制文件伪装文本 */
    private boolean canDecode(byte[] data, Charset charset) {
        try {
            charset.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(data));
            return true;
        } catch (CharacterCodingException e) {
            return false;
        }
    }

    private void cleanupFile(Path path) {
        try {
            Files.deleteIfExists(path);
        } catch (IOException e) {
            log.warn("清理文件失败: path={}", path, e);
        }
    }

    private DocumentVO toVO(Document document) {
        return DocumentVO.builder()
                .id(document.getId())
                .agentId(document.getAgentId())
                .fileName(document.getFileName())
                .fileType(document.getFileType())
                .status(document.getStatus())
                .chunkCount(document.getChunkCount())
                .slicingMode(document.getSlicingMode())
                .processedChunks(document.getProcessedChunks())
                .totalChunks(document.getTotalChunks())
                .slicingConfig(document.getSlicingConfig())
                .createdTime(document.getCreatedTime())
                .build();
    }
}
