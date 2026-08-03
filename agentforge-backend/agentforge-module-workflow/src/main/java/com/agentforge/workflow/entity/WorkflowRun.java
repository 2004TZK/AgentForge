package com.agentforge.workflow.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 工作流运行记录实体，对应表 `workflow_run`（input/node_logs 为 JSON 列）。
 */
@Data
@TableName(value = "`workflow_run`", autoResultMap = true)
public class WorkflowRun {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 工作流 ID */
    private Long workflowId;

    /** 触发 Agent（对话模式触发时） */
    private Long agentId;

    /** 触发用户 ID */
    private Long userId;

    /** 运行输入 {key: value} */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> input;

    /** RUNNING / SUCCESS / FAILED */
    private String status;

    /** 最终输出 */
    private String output;

    /** 节点级日志 [{node,type,status,output,error,durationMs}] */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<Map<String, Object>> nodeLogs;

    /** 失败原因 */
    private String error;

    private LocalDateTime startedTime;

    private LocalDateTime finishedTime;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
