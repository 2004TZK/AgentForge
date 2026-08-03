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
}
