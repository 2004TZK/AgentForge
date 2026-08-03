package com.agentforge.aigateway.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * AI 服务 /agent/workflow/run 响应。
 */
@Data
public class AiWorkflowRunResponse {

    /** SUCCESS / FAILED */
    private String status;

    private String output;

    /** 节点级日志 [{node,type,status,output,error,durationMs}] */
    private List<Map<String, Object>> nodeLogs = new ArrayList<>();

    private String error;
}
