package com.agentforge.workflow.vo;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 工作流出参（含节点明细；仅创建者可见）。
 */
@Data
@Builder
public class WorkflowVO {

    private Long id;

    private String name;

    private String description;

    private Long creatorId;

    /** ACTIVE / DISABLED */
    private String status;

    private LocalDateTime createdTime;

    private List<WorkflowNodeVO> nodes;
}
