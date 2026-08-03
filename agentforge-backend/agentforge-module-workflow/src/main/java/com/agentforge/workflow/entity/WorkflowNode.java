package com.agentforge.workflow.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 工作流节点实体，对应表 `workflow_node`（params 为 JSON 列）。
 */
@Data
@TableName(value = "`workflow_node`", autoResultMap = true)
public class WorkflowNode {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 工作流 ID */
    private Long workflowId;

    /** 节点键（变量引用/日志标识） */
    private String nodeKey;

    /** 节点类型 llm / tool */
    private String nodeType;

    /** 节点参数（JSON；含 {var} 模板） */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> params;

    /** 下一节点键（NULL=流程结束） */
    private String nextNode;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
