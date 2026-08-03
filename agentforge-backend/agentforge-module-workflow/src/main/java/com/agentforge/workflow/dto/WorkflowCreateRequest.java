package com.agentforge.workflow.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

/**
 * 创建/更新工作流入参（更新复用，节点整体替换）。
 */
@Data
public class WorkflowCreateRequest {

    @NotBlank(message = "工作流名称不能为空")
    @Size(max = 100, message = "工作流名称长度不能超过 100")
    private String name;

    @Size(max = 500, message = "描述长度不能超过 500")
    private String description;

    /** 节点列表（线性链，至少 1 个） */
    @NotEmpty(message = "工作流至少需要一个节点")
    @Valid
    private List<WorkflowNodeRequest> nodes;
}
