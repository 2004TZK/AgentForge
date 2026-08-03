package com.agentforge.agent.service;

import com.agentforge.agent.dto.AgentCreateRequest;
import com.agentforge.agent.dto.AgentUpdateRequest;
import com.agentforge.agent.vo.AgentDetailVO;
import com.agentforge.agent.vo.AgentVO;
import com.agentforge.common.core.PageResult;

/**
 * 智能体服务：分页查询 / 详情 / 创建 / 更新 / 删除（仅创建者可改删）。
 * M4 可见性：PRIVATE 私有仅创建者可见（列表过滤、详情与聊天校验）；PUBLIC 公开所有人可见。
 */
public interface AgentService {

    /** 分页查询（名称模糊检索；PRIVATE 仅创建者可见，PUBLIC 所有人可见） */
    PageResult<AgentVO> page(long page, long size, String name, Long viewerId);

    /** 详情（含系统提示词与工具配置；PRIVATE 非创建者视为不存在） */
    AgentDetailVO detail(Long agentId, Long viewerId);

    /** 创建（创建者即当前登录用户） */
    AgentDetailVO create(AgentCreateRequest request, Long creatorId);

    /** 更新（仅创建者） */
    AgentDetailVO update(Long agentId, AgentUpdateRequest request, Long operatorId);

    /** 删除（仅创建者，逻辑删除 Agent 及其工具配置） */
    void delete(Long agentId, Long operatorId);
}
