package com.agentforge.file.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档元数据实体，对应表 `document`。
 * 文件内容不落库：原始文件在共享卷，Chunk 向量在 Qdrant。
 */
@Data
@TableName("`document`")
public class Document {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 所属智能体 ID */
    private Long agentId;

    /** 原始文件名 */
    private String fileName;

    /** 相对存储路径（agentId/uuid.ext） */
    private String filePath;

    /** 文件类型：pdf/docx/txt/md/db/sqlite/sqlite3/csv */
    private String fileType;

    /** 状态：PENDING/PROCESSING/READY/FAILED */
    private String status;

    /** 切片数（入库完成后回填） */
    private Integer chunkCount;

    /** 切片方式：auto/manual */
    private String slicingMode;

    /** 手动切片参数快照（JSON 字符串，重试沿用） */
    private String slicingConfig;

    /** 已入库 chunk 数（异步入库期间由 AI 服务回写） */
    private Integer processedChunks;

    /** 总 chunk 数（解析切片完成后回写） */
    private Integer totalChunks;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
