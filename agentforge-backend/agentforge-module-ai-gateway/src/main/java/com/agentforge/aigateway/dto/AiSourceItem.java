package com.agentforge.aigateway.dto;

import lombok.Data;

/**
 * AI 服务返回的知识库来源（M2 起为对象，含可查看的片段）。
 */
@Data
public class AiSourceItem {

    /** 来源文件名 */
    private String file;

    /** 引用片段（截断） */
    private String snippet;

    /** 相似度分数 */
    private double score;

    /** 结构化来源：表名/sheet 名（sqlite/csv 文件） */
    private String table;

    /** 行号区间起点 */
    private Integer rowStart;

    /** 行号区间终点 */
    private Integer rowEnd;

    /** 来源类型：sqlite / csv / pdf / docx / txt / md */
    private String sourceType;
}
