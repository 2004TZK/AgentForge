package com.agentforge.workflow.service.impl;

import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiWorkflowRunRequest;
import com.agentforge.aigateway.dto.AiWorkflowRunResponse;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.workflow.dto.WorkflowCreateRequest;
import com.agentforge.workflow.dto.WorkflowNodeRequest;
import com.agentforge.workflow.dto.WorkflowRunRequest;
import com.agentforge.workflow.entity.Workflow;
import com.agentforge.workflow.entity.WorkflowNode;
import com.agentforge.workflow.entity.WorkflowRun;
import com.agentforge.workflow.mapper.WorkflowMapper;
import com.agentforge.workflow.mapper.WorkflowNodeMapper;
import com.agentforge.workflow.mapper.WorkflowRunMapper;
import com.agentforge.workflow.service.WorkflowService;
import com.agentforge.workflow.vo.WorkflowNodeVO;
import com.agentforge.workflow.vo.WorkflowRunVO;
import com.agentforge.workflow.vo.WorkflowVO;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 工作流服务实现。
 * 权限规则：仅创建者可查看/修改/删除（本机演示环境按创建者隔离）；
 * 运行记录按触发用户隔离；AI 服务不直连 MySQL，执行时透传定义 JSON。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class WorkflowServiceImpl implements WorkflowService {

    private final WorkflowMapper workflowMapper;
    private final WorkflowNodeMapper workflowNodeMapper;
    private final WorkflowRunMapper workflowRunMapper;
    private final AiServiceClient aiServiceClient;

    @Override
    @Transactional
    public WorkflowVO create(WorkflowCreateRequest request, Long creatorId) {
        Workflow workflow = new Workflow();
        workflow.setName(request.getName().trim());
        workflow.setDescription(request.getDescription());
        workflow.setCreatorId(creatorId);
        workflow.setStatus("ACTIVE");
        workflowMapper.insert(workflow);
        saveNodes(workflow.getId(), request.getNodes());
        log.info("创建工作流: id={}, name={}, creatorId={}", workflow.getId(), workflow.getName(), creatorId);
        return toVO(workflow);
    }

    @Override
    @Transactional
    public WorkflowVO update(Long workflowId, WorkflowCreateRequest request, Long operatorId) {
        Workflow workflow = getOwned(workflowId, operatorId);
        workflow.setName(request.getName().trim());
        workflow.setDescription(request.getDescription());
        workflowMapper.updateById(workflow);
        // 节点整体替换：逻辑删除旧节点后重新插入
        workflowNodeMapper.delete(new LambdaQueryWrapper<WorkflowNode>()
                .eq(WorkflowNode::getWorkflowId, workflowId));
        saveNodes(workflowId, request.getNodes());
        log.info("更新工作流: id={}, operatorId={}", workflowId, operatorId);
        return toVO(workflow);
    }

    @Override
    public WorkflowVO detail(Long workflowId, Long userId) {
        Workflow workflow = getOwned(workflowId, userId);
        return toVO(workflow);
    }

    @Override
    public PageResult<WorkflowVO> page(long page, long size, Long userId) {
        IPage<Workflow> result = workflowMapper.selectPage(Page.of(page, size),
                new LambdaQueryWrapper<Workflow>()
                        .eq(Workflow::getCreatorId, userId)
                        .orderByDesc(Workflow::getId));
        List<WorkflowVO> list = result.getRecords().stream().map(this::toVO).toList();
        return PageResult.of(list, result.getTotal(), page, size);
    }

    @Override
    @Transactional
    public void delete(Long workflowId, Long operatorId) {
        Workflow workflow = getOwned(workflowId, operatorId);
        workflowNodeMapper.delete(new LambdaQueryWrapper<WorkflowNode>()
                .eq(WorkflowNode::getWorkflowId, workflowId));
        workflowMapper.deleteById(workflowId);
        log.info("删除工作流: id={}, operatorId={}", workflowId, operatorId);
    }

    @Override
    public WorkflowRunVO run(Long workflowId, WorkflowRunRequest request, Long userId) {
        Workflow workflow = getOwned(workflowId, userId);
        return doRun(workflow, null, request.getInput() == null ? Map.of() : request.getInput(), userId);
    }

    @Override
    public WorkflowRunVO runForAgent(Workflow agentWorkflow, Long agentId, String message, Long userId) {
        Map<String, Object> input = new HashMap<>();
        input.put("message", message);
        return doRun(agentWorkflow, agentId, input, userId);
    }

    /**
     * 执行核心：落库 RUNNING → AI 服务执行（透传定义）→ 回填结果与节点日志。
     * 同步执行（CPU 推理可能数十秒，AI 服务超时已放宽）；AI 调用失败不抛异常，
     * 运行记录标记 FAILED（对话主链路不受影响）。
     */
    private WorkflowRunVO doRun(Workflow workflow, Long agentId, Map<String, Object> input, Long userId) {
        WorkflowRun run = new WorkflowRun();
        run.setWorkflowId(workflow.getId());
        run.setAgentId(agentId);
        run.setUserId(userId);
        run.setInput(input);
        run.setStatus("RUNNING");
        run.setStartedTime(LocalDateTime.now());
        workflowRunMapper.insert(run);

        AiWorkflowRunResponse aiResponse;
        try {
            AiWorkflowRunRequest aiRequest = AiWorkflowRunRequest.builder()
                    .definition(buildDefinition(workflow.getId()))
                    .input(input)
                    .build();
            aiResponse = aiServiceClient.runWorkflow(aiRequest);
        } catch (Exception e) {
            log.error("工作流执行失败（AI 服务）: workflowId={}, runId={}", workflow.getId(), run.getId(), e);
            aiResponse = null;
        }

        WorkflowRun update = new WorkflowRun();
        update.setId(run.getId());
        update.setFinishedTime(LocalDateTime.now());
        if (aiResponse != null) {
            update.setStatus("SUCCESS".equals(aiResponse.getStatus()) ? "SUCCESS" : "FAILED");
            update.setOutput(aiResponse.getOutput());
            update.setNodeLogs(aiResponse.getNodeLogs());
            update.setError(aiResponse.getError());
        } else {
            update.setStatus("FAILED");
            update.setError("AI 服务执行失败，请稍后重试");
        }
        workflowRunMapper.updateById(update);
        log.info("工作流运行结束: runId={}, status={}", run.getId(), update.getStatus());
        return toRunVO(run.getId(), userId);
    }

    @Override
    public WorkflowRunVO getRun(Long runId, Long userId) {
        return toRunVO(runId, userId);
    }

    @Override
    public PageResult<WorkflowRunVO> listRuns(Long workflowId, long page, long size, Long userId) {
        getOwned(workflowId, userId);
        IPage<WorkflowRun> result = workflowRunMapper.selectPage(Page.of(page, size),
                new LambdaQueryWrapper<WorkflowRun>()
                        .eq(WorkflowRun::getWorkflowId, workflowId)
                        .eq(WorkflowRun::getUserId, userId)
                        .orderByDesc(WorkflowRun::getId));
        List<WorkflowRunVO> list = result.getRecords().stream()
                .map(this::toRunVO).toList();
        return PageResult.of(list, result.getTotal(), page, size);
    }

    @Override
    public Workflow getOwned(Long workflowId, Long userId) {
        Workflow workflow = workflowMapper.selectById(workflowId);
        if (workflow == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "工作流不存在");
        }
        if (!workflow.getCreatorId().equals(userId)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "仅创建者可访问该工作流");
        }
        return workflow;
    }

    // ---------------- 私有方法 ----------------

    /** 批量插入节点 */
    private void saveNodes(Long workflowId, List<WorkflowNodeRequest> nodes) {
        for (WorkflowNodeRequest node : nodes) {
            WorkflowNode entity = new WorkflowNode();
            entity.setWorkflowId(workflowId);
            entity.setNodeKey(node.getNodeKey());
            entity.setNodeType(node.getNodeType());
            entity.setParams(node.getParams());
            entity.setNextNode(node.getNextNode());
            workflowNodeMapper.insert(entity);
        }
    }

    /** 组装 AI 服务可执行的流程定义 JSON（节点按 id 排序保证定义顺序稳定） */
    private Map<String, Object> buildDefinition(Long workflowId) {
        List<WorkflowNode> nodes = workflowNodeMapper.selectList(
                new LambdaQueryWrapper<WorkflowNode>()
                        .eq(WorkflowNode::getWorkflowId, workflowId)
                        .orderByAsc(WorkflowNode::getId));
        List<Map<String, Object>> nodeDefs = new ArrayList<>();
        for (WorkflowNode node : nodes) {
            Map<String, Object> def = new HashMap<>();
            def.put("nodeKey", node.getNodeKey());
            def.put("type", node.getNodeType());
            def.put("params", node.getParams() == null ? Map.of() : node.getParams());
            def.put("next", node.getNextNode());
            nodeDefs.add(def);
        }
        Map<String, Object> definition = new HashMap<>();
        definition.put("nodes", nodeDefs);
        return definition;
    }

    private WorkflowVO toVO(Workflow workflow) {
        List<WorkflowNode> nodes = workflowNodeMapper.selectList(
                new LambdaQueryWrapper<WorkflowNode>()
                        .eq(WorkflowNode::getWorkflowId, workflow.getId())
                        .orderByAsc(WorkflowNode::getId));
        List<WorkflowNodeVO> nodeVOs = nodes.stream()
                .map(n -> WorkflowNodeVO.builder()
                        .nodeKey(n.getNodeKey())
                        .nodeType(n.getNodeType())
                        .params(n.getParams() == null ? Map.of() : n.getParams())
                        .nextNode(n.getNextNode())
                        .build())
                .toList();
        return WorkflowVO.builder()
                .id(workflow.getId())
                .name(workflow.getName())
                .description(workflow.getDescription())
                .creatorId(workflow.getCreatorId())
                .status(workflow.getStatus())
                .createdTime(workflow.getCreatedTime())
                .nodes(nodeVOs)
                .build();
    }

    private WorkflowRunVO toRunVO(Long runId, Long userId) {
        WorkflowRun run = workflowRunMapper.selectById(runId);
        if (run == null || !run.getUserId().equals(userId)) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "运行记录不存在");
        }
        return toRunVO(run);
    }

    private WorkflowRunVO toRunVO(WorkflowRun run) {
        return WorkflowRunVO.builder()
                .id(run.getId())
                .workflowId(run.getWorkflowId())
                .agentId(run.getAgentId())
                .status(run.getStatus())
                .input(run.getInput() == null ? Map.of() : run.getInput())
                .output(run.getOutput())
                .nodeLogs(run.getNodeLogs() == null ? List.of() : run.getNodeLogs())
                .error(run.getError())
                .startedTime(run.getStartedTime())
                .finishedTime(run.getFinishedTime())
                .build();
    }
}
