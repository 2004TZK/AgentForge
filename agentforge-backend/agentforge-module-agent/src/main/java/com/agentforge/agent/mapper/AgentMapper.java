package com.agentforge.agent.mapper;

import com.agentforge.agent.entity.Agent;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * 智能体表 Mapper。
 */
@Mapper
public interface AgentMapper extends BaseMapper<Agent> {
}
