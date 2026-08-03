package com.agentforge.model.service.impl;

import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.model.dto.ProviderRequest;
import com.agentforge.model.entity.ModelProvider;
import com.agentforge.model.mapper.ModelProviderMapper;
import com.agentforge.model.service.ModelProviderService;
import com.agentforge.model.vo.ProviderVO;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 模型 Provider 服务实现。
 * 可见规则：内置（creator_id=0）全局可见但不可改删；用户自定义仅创建者可改删。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ModelProviderServiceImpl implements ModelProviderService {

    private static final long SYSTEM_OWNER = 0L;

    private final ModelProviderMapper providerMapper;

    @Override
    public List<ProviderVO> list(Long viewerId) {
        return providerMapper.selectList(new LambdaQueryWrapper<ModelProvider>()
                        .and(w -> w.eq(ModelProvider::getCreatorId, SYSTEM_OWNER)
                                .or(eqCreator(viewerId)))
                        .orderByDesc(ModelProvider::getEnabled)
                        .orderByDesc(ModelProvider::getId))
                .stream().map(this::toVO).toList();
    }

    @Override
    public ModelProvider getEnabledOrNull(Long providerId) {
        if (providerId == null) {
            return null;
        }
        return providerMapper.selectOne(new LambdaQueryWrapper<ModelProvider>()
                .eq(ModelProvider::getId, providerId)
                .eq(ModelProvider::getEnabled, true));
    }

    @Override
    @Transactional
    public ProviderVO create(ProviderRequest request, Long creatorId) {
        ModelProvider entity = new ModelProvider();
        fill(entity, request);
        entity.setCreatorId(creatorId);
        providerMapper.insert(entity);
        log.info("创建 Provider: id={}, name={}, type={}, creatorId={}",
                entity.getId(), entity.getName(), entity.getProviderType(), creatorId);
        return toVO(entity);
    }

    @Override
    @Transactional
    public ProviderVO update(Long providerId, ProviderRequest request, Long operatorId) {
        ModelProvider entity = getOrThrow(providerId);
        checkOwner(entity, operatorId);
        fill(entity, request);
        providerMapper.updateById(entity);
        log.info("更新 Provider: id={}, operatorId={}", providerId, operatorId);
        return toVO(entity);
    }

    @Override
    @Transactional
    public void delete(Long providerId, Long operatorId) {
        ModelProvider entity = getOrThrow(providerId);
        checkOwner(entity, operatorId);
        providerMapper.deleteById(providerId);
        log.info("删除 Provider: id={}, operatorId={}", providerId, operatorId);
    }

    // ---------------- 私有方法 ----------------

    private ModelProvider getOrThrow(Long providerId) {
        ModelProvider entity = providerMapper.selectById(providerId);
        if (entity == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "Provider 不存在");
        }
        return entity;
    }

    private void checkOwner(ModelProvider entity, Long operatorId) {
        if (entity.getCreatorId() == null || entity.getCreatorId() == SYSTEM_OWNER) {
            throw new BusinessException(ResultCode.FORBIDDEN, "系统内置 Provider 不可修改/删除");
        }
        if (!entity.getCreatorId().equals(operatorId)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "仅创建者可修改/删除该 Provider");
        }
    }

    private void fill(ModelProvider entity, ProviderRequest request) {
        entity.setName(request.getName().trim());
        entity.setProviderType(request.getProviderType());
        entity.setBaseUrl(request.getBaseUrl().trim());
        entity.setApiKey(request.getApiKey() == null ? null : request.getApiKey().trim());
        entity.setModels(request.getModels());
        entity.setEnabled(request.getEnabled() == null || request.getEnabled());
    }

    private ProviderVO toVO(ModelProvider entity) {
        return ProviderVO.builder()
                .id(entity.getId())
                .name(entity.getName())
                .providerType(entity.getProviderType())
                .baseUrl(entity.getBaseUrl())
                .apiKey(entity.getApiKey())
                .models(entity.getModels() == null ? List.of() : entity.getModels())
                .enabled(entity.getEnabled())
                .creatorId(entity.getCreatorId())
                .createdTime(entity.getCreatedTime())
                .build();
    }

    private static java.util.function.Consumer<LambdaQueryWrapper<ModelProvider>> eqCreator(Long creatorId) {
        return w -> w.eq(ModelProvider::getCreatorId, creatorId);
    }
}
