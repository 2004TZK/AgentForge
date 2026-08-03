package com.agentforge.file.vo;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文档出参（不暴露落盘路径给前端）。
 */
@Data
@Builder
public class DocumentVO {

    private Long id;

    private Long agentId;

    /** 原始文件名 */
    private String fileName;

    /** 文件类型 */
    private String fileType;

    /** 状态：PENDING/PROCESSING/READY/FAILED */
    private String status;

    private LocalDateTime createdTime;
}
