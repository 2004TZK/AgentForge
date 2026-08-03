package com.agentforge.workflow.dto;

import lombok.Data;

import java.util.HashMap;
import java.util.Map;

/**
 * 触发工作流运行入参。
 */
@Data
public class WorkflowRunRequest {

    /** 运行输入变量 {key: value}（模板引用 {var}） */
    private Map<String, Object> input = new HashMap<>();
}
