package com.agentforge.agent.mapper;

import com.agentforge.agent.entity.AgentTool;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * 工具配置表 Mapper。
 */
@Mapper
public interface AgentToolMapper extends BaseMapper<AgentTool> {

    /**
     * 物理删除某智能体的全部工具配置（整体替换语义）。
     * 注意：不能走 @TableLogic 逻辑删除——agent_tool 唯一键 (agent_id, tool_name)
     * 不区分 deleted，逻辑删除后重插同名工具会触发 DuplicateKeyException。
     */
    @Delete("DELETE FROM agent_tool WHERE agent_id = #{agentId}")
    int physicallyDeleteByAgentId(@Param("agentId") Long agentId);
}
