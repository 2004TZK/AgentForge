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

    /** 文件类型：pdf/docx/txt/md */
    private String fileType;

    /** 状态：PENDING/PROCESSING/READY/FAILED */
    private String status;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
