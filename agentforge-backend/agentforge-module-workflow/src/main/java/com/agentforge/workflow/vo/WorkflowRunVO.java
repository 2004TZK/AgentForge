package com.agentforge.workflow.vo;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 工作流运行记录出参（含节点级日志）。
 */
@Data
@Builder
public class WorkflowRunVO {

    private Long id;

    private Long workflowId;

    /** 触发 Agent（对话模式触发时） */
    private Long agentId;

    /** RUNNING / SUCCESS / FAILED */
    private String status;

    private Map<String, Object> input;

    private String output;

    /** 节点级日志 [{node,type,status,output,error,durationMs}] */
    private List<Map<String, Object>> nodeLogs;

    private String error;

    private LocalDateTime startedTime;

    private LocalDateTime finishedTime;
}
