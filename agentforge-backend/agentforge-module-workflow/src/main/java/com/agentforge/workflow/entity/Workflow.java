package com.agentforge.workflow.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 工作流定义实体，对应表 `workflow`（节点明细在 workflow_node）。
 */
@Data
@TableName("`workflow`")
public class Workflow {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 工作流名称 */
    private String name;

    /** 描述 */
    private String description;

    /** 创建者 ID */
    private Long creatorId;

    /** 状态 ACTIVE / DISABLED */
    private String status;

    @TableLogic
    private Integer deleted;

    private LocalDateTime createdTime;

    private LocalDateTime updatedTime;
}
