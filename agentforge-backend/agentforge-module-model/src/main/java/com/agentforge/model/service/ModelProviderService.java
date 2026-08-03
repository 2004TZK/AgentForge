package com.agentforge.model.service;

import com.agentforge.model.dto.ProviderRequest;
import com.agentforge.model.entity.ModelProvider;
import com.agentforge.model.vo.ProviderVO;

import java.util.List;

/**
 * 模型 Provider 服务：列表（内置 + 本人）/ 创建 / 更新 / 删除（仅创建者，内置不可删）。
 */
public interface ModelProviderService {

    /** 列表：系统内置（creator_id=0）+ 本人创建的，按启用优先/时间倒序 */
    List<ProviderVO> list(Long viewerId);

    /** 按 ID 查询启用的 Provider（供聊天透传；未找到返回 null，回落内置 Ollama） */
    ModelProvider getEnabledOrNull(Long providerId);

    ProviderVO create(ProviderRequest request, Long creatorId);

    ProviderVO update(Long providerId, ProviderRequest request, Long operatorId);

    void delete(Long providerId, Long operatorId);
}
