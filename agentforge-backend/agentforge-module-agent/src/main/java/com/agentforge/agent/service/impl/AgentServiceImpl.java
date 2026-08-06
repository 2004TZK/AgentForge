package com.agentforge.agent.service.impl;

import com.agentforge.agent.dto.AgentCreateRequest;
import com.agentforge.agent.dto.AgentUpdateRequest;
import com.agentforge.agent.dto.ToolConfigRequest;
import com.agentforge.agent.entity.Agent;
import com.agentforge.agent.entity.AgentTool;
import com.agentforge.agent.mapper.AgentMapper;
import com.agentforge.agent.mapper.AgentToolMapper;
import com.agentforge.agent.service.AgentService;
import com.agentforge.agent.service.ToolDefinitionService;
import com.agentforge.agent.util.ToolSecretUtil;
import com.agentforge.agent.vo.AgentDetailVO;
import com.agentforge.agent.vo.AgentToolVO;
import com.agentforge.agent.vo.AgentVO;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.framework.security.AesGcmCrypto;
import com.agentforge.workflow.service.WorkflowService;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 智能体服务实现。
 * 权限规则（M4）：PRIVATE 仅创建者可见（列表过滤、详情校验）；PUBLIC 所有人可见；
 * 修改/删除仅创建者（FORBIDDEN）。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentServiceImpl implements AgentService {

    private final AgentMapper agentMapper;
    private final AgentToolMapper agentToolMapper;
    private final WorkflowService workflowService;
    private final ToolDefinitionService toolDefinitionService;
    private final AesGcmCrypto aesGcmCrypto;

    @Override
    public PageResult<AgentVO> page(long page, long size, String name, Long viewerId) {
        LambdaQueryWrapper<Agent> wrapper = new LambdaQueryWrapper<Agent>()
                .and(w -> w.eq(Agent::getVisibility, "PUBLIC")
                        .or(eqCreator(viewerId)))
                .like(StringUtils.hasText(name), Agent::getName, name)
                .orderByDesc(Agent::getId);
        IPage<Agent> result = agentMapper.selectPage(Page.of(page, size), wrapper);
        List<AgentVO> list = result.getRecords().stream().map(this::toVO).toList();
        return PageResult.of(list, result.getTotal(), page, size);
    }

    @Override
    public AgentDetailVO detail(Long agentId, Long viewerId) {
        Agent agent = getAgentOrThrow(agentId);
        checkVisible(agent, viewerId);
        return toDetailVO(agent);
    }

    @Override
    @Transactional
    public AgentDetailVO create(AgentCreateRequest request, Long creatorId) {
        validateMode(request.getMode(), request.getWorkflowId(), creatorId);
        Agent agent = new Agent();
        agent.setName(request.getName().trim());
        agent.setDescription(request.getDescription());
        agent.setSystemPrompt(request.getSystemPrompt());
        agent.setModelName(request.getModelName());
        agent.setProviderId(request.getProviderId());
        agent.setTemperature(request.getTemperature());
        agent.setMode(request.getMode());
        agent.setWorkflowId(request.getWorkflowId());
        agent.setVisibility(normalizeVisibility(request.getVisibility()));
        agent.setCreatorId(creatorId);
        agentMapper.insert(agent);
        saveTools(agent.getId(), request.getTools(), creatorId, null);
        log.info("创建 Agent: id={}, name={}, creatorId={}", agent.getId(), agent.getName(), creatorId);
        return toDetailVO(agent);
    }

    @Override
    @Transactional
    public AgentDetailVO update(Long agentId, AgentUpdateRequest request, Long operatorId) {
        Agent agent = getAgentOrThrow(agentId);
        checkOwner(agent, operatorId);
        validateMode(request.getMode(), request.getWorkflowId(), operatorId);

        agent.setName(request.getName().trim());
        agent.setDescription(request.getDescription());
        agent.setSystemPrompt(request.getSystemPrompt());
        agent.setModelName(request.getModelName());
        agent.setProviderId(request.getProviderId());
        agent.setTemperature(request.getTemperature());
        agent.setMode(request.getMode());
        agent.setWorkflowId(request.getWorkflowId());
        agent.setVisibility(normalizeVisibility(request.getVisibility()));
        agentMapper.updateById(agent);

        // 工具配置整体替换：旧配置逻辑删除后重新插入
        replaceTools(agentId, request.getTools(), operatorId);
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

    /** M4 可见性校验：PRIVATE 非创建者视为不存在（不泄露存在性） */
    private void checkVisible(Agent agent, Long viewerId) {
        if (!"PUBLIC".equals(agent.getVisibility()) && !agent.getCreatorId().equals(viewerId)) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "智能体不存在");
        }
    }

    /** 可见性归一化：非法值回落 PRIVATE */
    private String normalizeVisibility(String visibility) {
        return "PUBLIC".equals(visibility) ? "PUBLIC" : "PRIVATE";
    }

    /** 查询条件：创建者过滤（用于 and 分组：PUBLIC 或 本人） */
    private static java.util.function.Consumer<LambdaQueryWrapper<Agent>> eqCreator(Long creatorId) {
        return w -> w.eq(Agent::getCreatorId, creatorId);
    }

    /** 运行模式校验：workflow 模式必须绑定本人名下的工作流 */
    private void validateMode(String mode, Long workflowId, Long operatorId) {
        if (!"workflow".equals(mode)) {
            return;
        }
        if (workflowId == null) {
            throw new BusinessException(ResultCode.PARAM_ERROR, "工作流模式必须绑定工作流");
        }
        workflowService.getOwned(workflowId, operatorId);
    }

    /**
     * 批量插入工具配置。
     *
     * @param oldConfigs 按工具名索引的旧配置（编辑时掩码合并用；创建传 null）
     */
    private void saveTools(Long agentId, List<ToolConfigRequest> tools, Long operatorId,
                           Map<String, Map<String, Object>> oldConfigs) {
        if (tools == null || tools.isEmpty()) {
            return;
        }
        Set<String> seen = new HashSet<>();
        for (ToolConfigRequest tool : tools) {
            if (!seen.add(tool.getToolName())) {
                throw new BusinessException(ResultCode.PARAM_ERROR,
                        "工具重复绑定: " + tool.getToolName());
            }
            boolean custom = "custom".equals(tool.getToolSource());
            if (custom) {
                // 自定义工具绑定校验：定义存在且有权限（PRIVATE 仅创建者 / PUBLIC 所有人）
                if (tool.getToolDefinitionId() == null) {
                    throw new BusinessException(ResultCode.PARAM_ERROR,
                            "自定义工具必须指定 toolDefinitionId");
                }
                toolDefinitionService.getBindable(tool.getToolDefinitionId(), operatorId);
            }
            AgentTool entity = new AgentTool();
            entity.setAgentId(agentId);
            entity.setToolName(tool.getToolName());
            entity.setToolSource(custom ? "custom" : "builtin");
            entity.setToolDefinitionId(custom ? tool.getToolDefinitionId() : null);
            // 密钥字段：编辑回显掩码合并旧值 → 加密入库
            Map<String, Object> old = oldConfigs == null ? null : oldConfigs.get(tool.getToolName());
            Map<String, Object> merged = ToolSecretUtil.mergeSecrets(old, tool.getToolConfig(), aesGcmCrypto);
            entity.setToolConfig(ToolSecretUtil.encryptSecrets(merged, aesGcmCrypto));
            entity.setEnabled(tool.getEnabled() == null || tool.getEnabled());
            agentToolMapper.insert(entity);
        }
    }

    /** 整体替换工具配置：读取旧配置（掩码合并用）→ 逻辑删除旧配置 + 插入新配置 */
    private void replaceTools(Long agentId, List<ToolConfigRequest> tools, Long operatorId) {
        Map<String, Map<String, Object>> oldConfigs = agentToolMapper.selectList(
                        new LambdaQueryWrapper<AgentTool>().eq(AgentTool::getAgentId, agentId))
                .stream()
                .collect(Collectors.toMap(AgentTool::getToolName,
                        t -> t.getToolConfig() == null ? Map.of() : t.getToolConfig(),
                        (a, b) -> a));
        // 物理删除旧配置：逻辑删除会保留 deleted=1 的旧行，
        // 重插同名工具时撞唯一键 (agent_id, tool_name) → DuplicateKeyException
        agentToolMapper.physicallyDeleteByAgentId(agentId);
        saveTools(agentId, tools, operatorId, oldConfigs);
    }

    private AgentVO toVO(Agent agent) {
        return AgentVO.builder()
                .id(agent.getId())
                .name(agent.getName())
                .description(agent.getDescription())
                .modelName(agent.getModelName())
                .providerId(agent.getProviderId())
                .temperature(agent.getTemperature())
                .mode(agent.getMode())
                .workflowId(agent.getWorkflowId())
                .visibility(agent.getVisibility())
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
                        .toolSource(t.getToolSource() == null ? "builtin" : t.getToolSource())
                        .toolDefinitionId(t.getToolDefinitionId())
                        .toolConfig(ToolSecretUtil.maskSecrets(
                                t.getToolConfig() == null ? Map.of() : t.getToolConfig()))
                        .enabled(t.getEnabled())
                        .build())
                .collect(Collectors.toList());
        return AgentDetailVO.builder()
                .id(agent.getId())
                .name(agent.getName())
                .description(agent.getDescription())
                .systemPrompt(agent.getSystemPrompt())
                .modelName(agent.getModelName())
                .providerId(agent.getProviderId())
                .temperature(agent.getTemperature())
                .mode(agent.getMode())
                .workflowId(agent.getWorkflowId())
                .visibility(agent.getVisibility())
                .creatorId(agent.getCreatorId())
                .createdTime(agent.getCreatedTime())
                .tools(toolVOs)
                .build();
    }
}
