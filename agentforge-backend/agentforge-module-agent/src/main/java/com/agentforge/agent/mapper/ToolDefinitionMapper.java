package com.agentforge.agent.mapper;

import com.agentforge.agent.entity.ToolDefinition;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * 用户自定义工具定义 Mapper。
 */
@Mapper
public interface ToolDefinitionMapper extends BaseMapper<ToolDefinition> {
}
