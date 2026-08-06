package com.agentforge.aigateway.dto;

import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * AI 服务 /rag/preview 响应：只读解析结构 + 按切片配置预览前若干 chunk（手动切片预览）。
 */
@Data
public class AiPreviewResponse {

    /** 来源类型：sqlite / csv */
    private String sourceType;

    /** 总行数（预览上限内） */
    private Integer totalRows;

    /** 表数 */
    private Integer tableCount;

    /** 各表结构 */
    private List<TableInfo> tables;

    /** 按当前切片配置生成的样例 chunk（前若干个） */
    private List<Map<String, Object>> sampleChunks;

    @Data
    public static class TableInfo {
        private String name;
        private List<String> columns;
        private Integer rowCount;
    }
}
