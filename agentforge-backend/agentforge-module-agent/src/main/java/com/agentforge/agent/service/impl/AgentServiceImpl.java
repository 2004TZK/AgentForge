package com.agentforge.agent.service.impl;

import com.agentforge.agent.dto.AgentCreateRequest;
import com.agentforge.agent.dto.AgentUpdateRequest;
import com.agentforge.agent.dto.ToolConfigRequest;
import com.agentforge.agent.entity.Agent;
import com.agentforge.agent.entity.AgentTool;
import com.agentforge.agent.mapper.AgentMapper;
import com.agentforge.agent.mapper.AgentToolMapper;
import com.agentforge.agent.service.AgentService;
import com.agentforge.agent.vo.AgentDetailVO;
import com.agentforge.agent.vo.AgentToolVO;
import com.agentforge.agent.vo.AgentVO;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 智能体服务实现。
 * 权限规则：仅创建者可修改/删除（FORBIDDEN）；列表与详情对所有登录用户开放。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentServiceImpl implements AgentService {

    private final AgentMapper agentMapper;
    private final AgentToolMapper agentToolMapper;

    @Override
    public PageResult<AgentVO> page(long page, long size, String name) {
        LambdaQueryWrapper<Agent> wrapper = new LambdaQueryWrapper<Agent>()
                .like(StringUtils.hasText(name), Agent::getName, name)
                .orderByDesc(Agent::getId);
        IPage<Agent> result = agentMapper.selectPage(Page.of(page, size), wrapper);
        List<AgentVO> list = result.getRecords().stream().map(this::toVO).toList();
        return PageResult.of(list, result.getTotal(), page, size);
    }

    @Override
    public AgentDetailVO detail(Long agentId) {
        Agent agent = getAgentOrThrow(agentId);
        return toDetailVO(agent);
    }

    @Override
    @Transactional
    public AgentDetailVO create(AgentCreateRequest request, Long creatorId) {
        Agent agent = new Agent();
        agent.setName(request.getName().trim());
        agent.setDescription(request.getDescription());
        agent.setSystemPrompt(request.getSystemPrompt());
        agent.setModelName(request.getModelName());
        agent.setTemperature(request.getTemperature());
        agent.setCreatorId(creatorId);
        agentMapper.insert(agent);
        saveTools(agent.getId(), request.getTools());
        log.info("创建 Agent: id={}, name={}, creatorId={}", agent.getId(), agent.getName(), creatorId);
        return toDetailVO(agent);
    }

    @Override
    @Transactional
    public AgentDetailVO update(Long agentId, AgentUpdateRequest request, Long operatorId) {
        Agent agent = getAgentOrThrow(agentId);
        checkOwner(agent, operatorId);

        agent.setName(request.getName().trim());
        agent.setDescription(request.getDescription());
        agent.setSystemPrompt(request.getSystemPrompt());
        agent.setModelName(request.getModelName());
        agent.setTemperature(request.getTemperature());
        agentMapper.updateById(agent);

        // 工具配置整体替换：旧配置逻辑删除后重新插入
        replaceTools(agentId, request.getTools());
        log.info("更新 Agent: id={}, operatorId={}", agentId, operatorId);
        return toDetailVO(agent);
    }

    @Override
    @Transactional
    public void delete(Long agentId, Long operatorId) {
        Agent agent = getAgentOrThrow(agentId);
        checkOwner(agent, operatorId);

        // 逻辑删除工具配置与 Agent 本体
        agentToolMapper.delete(new LambdaQueryWrapper<AgentTool>().eq(AgentTool::getAgentId, agentId));
        agentMapper.deleteById(agentId);
        log.info("删除 Agent: id={}, operatorId={}", agentId, operatorId);
    }

    // ---------------- 私有方法 ----------------

    private Agent getAgentOrThrow(Long agentId) {
        Agent agent = agentMapper.selectById(agentId);
        if (agent == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "智能体不存在");
        }
        return agent;
    }

    private void checkOwner(Agent agent, Long operatorId) {
        if (!agent.getCreatorId().equals(operatorId)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "仅创建者可修改/删除该智能体");
        }
    }

    /** 批量插入工具配置 */
    private void saveTools(Long agentId, List<ToolConfigRequest> tools) {
        if (tools == null || tools.isEmpty()) {
            return;
        }
        for (ToolConfigRequest tool : tools) {
            AgentTool entity = new AgentTool();
            entity.setAgentId(agentId);
            entity.setToolName(tool.getToolName());
            entity.setToolConfig(tool.getToolConfig());
            entity.setEnabled(tool.getEnabled() == null || tool.getEnabled());
            agentToolMapper.insert(entity);
        }
    }

    /** 整体替换工具配置：逻辑删除旧配置 + 插入新配置 */
    private void replaceTools(Long agentId, List<ToolConfigRequest> tools) {
        agentToolMapper.delete(new LambdaQueryWrapper<AgentTool>().eq(AgentTool::getAgentId, agentId));
        saveTools(agentId, tools);
    }

    private AgentVO toVO(Agent agent) {
        return AgentVO.builder()
                .id(agent.getId())
                .name(agent.getName())
                .description(agent.getDescription())
                .modelName(agent.getModelName())
                .temperature(agent.getTemperature())
                .creatorId(agent.getCreatorId())
                .createdTime(agent.getCreatedTime())
                .build();
    }

    private AgentDetailVO toDetailVO(Agent agent) {
        List<AgentTool> tools = agentToolMapper.selectList(
                new LambdaQueryWrapper<AgentTool>()
                        .eq(AgentTool::getAgentId, agent.getId())
                        .orderByAsc(AgentTool::getId));
        List<AgentToolVO> toolVOs = tools.stream()
                .map(t -> AgentToolVO.builder()
                        .toolName(t.getToolName())
                        .toolConfig(t.getToolConfig() == null ? Map.of() : t.getToolConfig())
                        .enabled(t.getEnabled())
                        .build())
                .collect(Collectors.toList());
        return AgentDetailVO.builder()
                .id(agent.getId())
                .name(agent.getName())
                .description(agent.getDescription())
                .systemPrompt(agent.getSystemPrompt())
                .modelName(agent.getModelName())
                .temperature(agent.getTemperature())
                .creatorId(agent.getCreatorId())
                .createdTime(agent.getCreatedTime())
                .tools(toolVOs)
                .build();
    }
}
