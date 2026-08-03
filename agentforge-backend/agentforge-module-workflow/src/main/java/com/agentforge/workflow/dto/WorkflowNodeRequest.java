package com.agentforge.workflow.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.Map;

/**
 * 工作流节点入参。
 */
@Data
public class WorkflowNodeRequest {

    @NotBlank(message = "节点键不能为空")
    @Size(max = 100, message = "节点键长度不能超过 100")
    private String nodeKey;

    /** 节点类型：llm / tool */
    @NotBlank(message = "节点类型不能为空")
    @Pattern(regexp = "llm|tool", message = "节点类型仅支持 llm/tool")
    private String nodeType;

    /** 节点参数（tool 名与 payload / llm 提示词模板；支持 {var} 模板） */
    private Map<String, Object> params;

    /** 下一节点键（NULL=流程结束） */
    private String nextNode;
}
