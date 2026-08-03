package com.agentforge.workflow.vo;

import lombok.Builder;
import lombok.Data;

import java.util.Map;

/**
 * 工作流节点出参。
 */
@Data
@Builder
public class WorkflowNodeVO {

    private String nodeKey;

    /** llm / tool */
    private String nodeType;

    private Map<String, Object> params;

    /** 下一节点键（NULL=流程结束） */
    private String nextNode;
}
