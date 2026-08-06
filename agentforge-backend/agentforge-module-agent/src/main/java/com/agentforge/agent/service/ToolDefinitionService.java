package com.agentforge.agent.service;

import com.agentforge.agent.dto.ToolDefinitionRequest;
import com.agentforge.agent.dto.ToolTestRequest;
import com.agentforge.agent.entity.ToolDefinition;
import com.agentforge.agent.vo.ToolDefinitionVO;
import com.agentforge.agent.vo.ToolTestResult;
import com.agentforge.common.core.PageResult;

/**
 * 用户自定义工具定义服务（工具定义开发文档 v3.0 §7 阶段一）。
 * 权限规则：PRIVATE 仅创建者可见/绑定/测试；PUBLIC 所有人可见与绑定，
 * 但密钥明文不返回（详情脱敏），修改/删除仅创建者。
 */
public interface ToolDefinitionService {

    /** 分页：创建者本人 + PUBLIC（按创建时间倒序） */
    PageResult<ToolDefinitionVO> page(long page, long size, String keyword, Long viewerId);

    /** 详情：PRIVATE 非创建者视为不存在；http_config 密钥脱敏 */
    ToolDefinitionVO detail(Long id, Long viewerId);

    /** 创建（密钥加密入库；名称校验：格式/用户级唯一/不与内置工具重名） */
    ToolDefinitionVO create(ToolDefinitionRequest request, Long creatorId);

    /** 更新（仅创建者；掩码回传视为不修改，合并库中原值） */
    ToolDefinitionVO update(Long id, ToolDefinitionRequest request, Long operatorId);

    /** 删除（仅创建者，逻辑删除） */
    void delete(Long id, Long operatorId);

    /** 复制 PUBLIC 工具到本人工具库（名称自动去冲突） */
    ToolDefinitionVO copy(Long id, Long operatorId);

    /** 测试：校验权限后透传 AI 服务真实执行一次 */
    ToolTestResult test(ToolTestRequest request, Long operatorId);

    /** Agent 绑定校验：返回定义实体（含密文，供装配链路解密）；PRIVATE 非创建者视为不存在 */
    ToolDefinition getBindable(Long id, Long userId);

    /** 装配链路加载：工具定义 ID → 实体（权限已由 Agent 归属校验覆盖） */
    ToolDefinition loadForAssembly(Long id);
}
