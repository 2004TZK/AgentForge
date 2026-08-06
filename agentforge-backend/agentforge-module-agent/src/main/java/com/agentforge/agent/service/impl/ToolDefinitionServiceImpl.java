package com.agentforge.agent.service.impl;

import com.agentforge.agent.dto.ToolDefinitionRequest;
import com.agentforge.agent.dto.ToolTestRequest;
import com.agentforge.agent.entity.ToolDefinition;
import com.agentforge.agent.mapper.ToolDefinitionMapper;
import com.agentforge.agent.service.ToolDefinitionService;
import com.agentforge.agent.util.ToolSecretUtil;
import com.agentforge.agent.vo.ToolDefinitionVO;
import com.agentforge.agent.vo.ToolTestResult;
import com.agentforge.aigateway.client.AiServiceClient;
import com.agentforge.aigateway.dto.AiToolTestRequest;
import com.agentforge.aigateway.dto.AiToolTestResponse;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.framework.security.AesGcmCrypto;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 用户自定义工具定义服务实现。
 * 安全要点（文档 v3.0 §6）：密钥 AES-GCM 加密入库、详情脱敏、掩码合并不修改、
 * 名称不得与内置注册表工具重名、PRIVATE 权限隔离。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ToolDefinitionServiceImpl implements ToolDefinitionService {

    /** 代码工具源码大小上限（50KB，与 AI 服务/sandbox 双重校验一致） */
    private static final int SCRIPT_MAX_CHARS = 50 * 1024;

    /** 复制名称冲突时追加的后缀 */
    private static final String COPY_SUFFIX = "_copy";

    private final ToolDefinitionMapper toolDefinitionMapper;
    private final AiServiceClient aiServiceClient;
    private final AesGcmCrypto aesGcmCrypto;

    // ---------------- 查询 ----------------

    @Override
    public PageResult<ToolDefinitionVO> page(long page, long size, String keyword, Long viewerId) {
        LambdaQueryWrapper<ToolDefinition> wrapper = new LambdaQueryWrapper<ToolDefinition>()
                .and(w -> w.eq(ToolDefinition::getVisibility, "PUBLIC")
                        .or(eqCreator(viewerId)))
                .like(StringUtils.hasText(keyword), ToolDefinition::getName, keyword)
                .orderByDesc(ToolDefinition::getId);
        IPage<ToolDefinition> result = toolDefinitionMapper.selectPage(Page.of(page, size), wrapper);
        List<ToolDefinitionVO> list = result.getRecords().stream().map(this::toVO).toList();
        return PageResult.of(list, result.getTotal(), page, size);
    }

    @Override
    public ToolDefinitionVO detail(Long id, Long viewerId) {
        ToolDefinition definition = getOrThrow(id);
        checkVisible(definition, viewerId);
        return toVO(definition);
    }

    // ---------------- 写操作 ----------------

    @Override
    @Transactional
    public ToolDefinitionVO create(ToolDefinitionRequest request, Long creatorId) {
        validateName(request.getName(), creatorId, null);
        validateConfig(request, null);

        ToolDefinition entity = new ToolDefinition();
        entity.setCreatorId(creatorId);
        entity.setName(request.getName().trim());
        entity.setDisplayName(request.getDisplayName().trim());
        entity.setDescription(request.getDescription());
        entity.setToolType(request.getToolType());
        entity.setParameters(request.getParameters() == null ? new HashMap<>() : request.getParameters());
        // 密钥字段加密后入库
        entity.setHttpConfig(ToolSecretUtil.encryptSecrets(request.getHttpConfig(), aesGcmCrypto));
        entity.setScriptConfig(request.getScriptConfig());
        entity.setVisibility(normalizeVisibility(request.getVisibility()));
        toolDefinitionMapper.insert(entity);
        log.info("创建自定义工具: id={}, name={}, type={}, creatorId={}",
                entity.getId(), entity.getName(), entity.getToolType(), creatorId);
        return toVO(entity);
    }

    @Override
    @Transactional
    public ToolDefinitionVO update(Long id, ToolDefinitionRequest request, Long operatorId) {
        ToolDefinition existing = getOrThrow(id);
        checkOwner(existing, operatorId);
        validateName(request.getName(), operatorId, id);
        validateConfig(request, existing);

        ToolDefinition entity = new ToolDefinition();
        entity.setId(id);
        entity.setName(request.getName().trim());
        entity.setDisplayName(request.getDisplayName().trim());
        entity.setDescription(request.getDescription());
        entity.setToolType(request.getToolType());
        entity.setParameters(request.getParameters() == null ? new HashMap<>() : request.getParameters());
        // 掩码合并：回显的 ******** 视为"不修改"，保留库中原值（可能为密文）
        Map<String, Object> mergedHttp = ToolSecretUtil.mergeSecrets(
                existing.getHttpConfig(), request.getHttpConfig(), aesGcmCrypto);
        entity.setHttpConfig(ToolSecretUtil.encryptSecrets(mergedHttp, aesGcmCrypto));
        entity.setScriptConfig(request.getScriptConfig());
        entity.setVisibility(normalizeVisibility(request.getVisibility()));
        toolDefinitionMapper.updateById(entity);
        log.info("更新自定义工具: id={}, operatorId={}", id, operatorId);
        return toVO(entity);
    }

    @Override
    @Transactional
    public void delete(Long id, Long operatorId) {
        ToolDefinition definition = getOrThrow(id);
        checkOwner(definition, operatorId);
        toolDefinitionMapper.deleteById(id);
        log.info("删除自定义工具: id={}, operatorId={}", id, operatorId);
    }

    @Override
    @Transactional
    public ToolDefinitionVO copy(Long id, Long operatorId) {
        ToolDefinition source = getOrThrow(id);
        checkVisible(source, operatorId); // PUBLIC 或本人可复制；PRIVATE 非创建者视为不存在
        ToolDefinition copy = new ToolDefinition();
        copy.setCreatorId(operatorId);
        copy.setName(uniqueCopyName(source.getName(), operatorId));
        copy.setDisplayName(source.getDisplayName() + "（副本）");
        copy.setDescription(source.getDescription());
        copy.setToolType(source.getToolType());
        copy.setParameters(source.getParameters());
        // 复制保留加密后的密文（PUBLIC 工具本人可复制自己的；他人复制拿不到明文，密文直接复制可被本人解密）
        copy.setHttpConfig(source.getHttpConfig());
        copy.setScriptConfig(source.getScriptConfig());
        copy.setVisibility("PRIVATE");
        toolDefinitionMapper.insert(copy);
        log.info("复制自定义工具: sourceId={}, newId={}, operatorId={}", id, copy.getId(), operatorId);
        return toVO(copy);
    }

    // ---------------- 测试 / 绑定 ----------------

    @Override
    public ToolTestResult test(ToolTestRequest request, Long operatorId) {
        if (request.getArgs() == null) {
            throw new BusinessException(ResultCode.PARAM_ERROR, "测试参数 args 不能为空");
        }
        AiToolTestRequest aiRequest = AiToolTestRequest.builder()
                .toolType(request.getToolType())
                // 测试入口来自工具库页面：httpConfig 为前端回显（已脱敏），密钥字段无需解密
                // （由用户临时填入或回填掩码；掩码值在 AI 侧按字面发送 —— 测试场景可接受，
                // 如需真实密钥测试请在表单中重新输入）
                .httpConfig(request.getHttpConfig())
                .scriptConfig(request.getScriptConfig())
                .parameters(request.getParameters())
                .args(request.getArgs())
                .build();
        AiToolTestResponse response = aiServiceClient.testTool(aiRequest);
        return ToolTestResult.builder()
                .ok(response.isOk())
                .result(response.getResult())
                .stdout(response.getStdout())
                .error(response.getError())
                .durationMs(response.getDurationMs())
                .build();
    }

    @Override
    public ToolDefinition getBindable(Long id, Long userId) {
        ToolDefinition definition = getOrThrow(id);
        checkVisible(definition, userId);
        return definition;
    }

    @Override
    public ToolDefinition loadForAssembly(Long id) {
        return getOrThrow(id);
    }

    // ---------------- 校验 ----------------

    /** 名称校验：格式 + 用户级唯一（排除自身）+ 不与内置注册表工具重名 */
    private void validateName(String name, Long ownerId, Long excludeId) {
        String trimmed = name.trim();
        // 用户级唯一（逻辑删除记录也会占用唯一键，需物理清理后复用）
        Long duplicate = toolDefinitionMapper.selectCount(new LambdaQueryWrapper<ToolDefinition>()
                .eq(ToolDefinition::getCreatorId, ownerId)
                .eq(ToolDefinition::getName, trimmed)
                .ne(excludeId != null, ToolDefinition::getId, excludeId));
        if (duplicate != null && duplicate > 0) {
            throw new BusinessException(ResultCode.RESOURCE_CONFLICT, "工具名已存在，请更换名称");
        }
        // 不与内置注册表工具重名（元数据获取失败时降级跳过，不阻断主链路）
        try {
            List<Map<String, Object>> meta = aiServiceClient.getToolMeta();
            if (meta != null) {
                Set<String> builtin = new HashSet<>();
                meta.forEach(m -> {
                    if (m.get("name") != null) {
                        builtin.add(String.valueOf(m.get("name")));
                    }
                });
                if (builtin.contains(trimmed)) {
                    throw new BusinessException(ResultCode.RESOURCE_CONFLICT,
                            "工具名与内置工具冲突，请更换名称");
                }
            }
        } catch (BusinessException e) {
            if (e.getResultCode() == ResultCode.RESOURCE_CONFLICT) {
                throw e;
            }
            log.warn("内置工具元数据获取失败，跳过重名校验: {}", e.getMessage());
        }
    }

    /** 按 toolType 校验 http_config / script_config 必填字段与代码大小 */
    private void validateConfig(ToolDefinitionRequest request, ToolDefinition existing) {
        if ("http".equals(request.getToolType())) {
            if (request.getHttpConfig() == null) {
                throw new BusinessException(ResultCode.PARAM_ERROR, "HTTP 工具必须配置 httpConfig");
            }
            Object method = request.getHttpConfig().get("method");
            Object url = request.getHttpConfig().get("url");
            if (!StringUtils.hasText(method == null ? null : String.valueOf(method))
                    || !StringUtils.hasText(url == null ? null : String.valueOf(url))) {
                throw new BusinessException(ResultCode.PARAM_ERROR, "httpConfig 必须包含 method 与 url");
            }
            String urlStr = String.valueOf(url);
            if (!urlStr.startsWith("http://") && !urlStr.startsWith("https://")) {
                throw new BusinessException(ResultCode.PARAM_ERROR, "httpConfig.url 必须以 http:// 或 https:// 开头");
            }
        } else if ("script".equals(request.getToolType())) {
            if (request.getScriptConfig() == null) {
                throw new BusinessException(ResultCode.PARAM_ERROR, "代码工具必须配置 scriptConfig");
            }
            Object language = request.getScriptConfig().get("language");
            Object source = request.getScriptConfig().get("source");
            if (!"python".equals(language) && !"javascript".equals(language)) {
                throw new BusinessException(ResultCode.PARAM_ERROR, "scriptConfig.language 仅支持 python / javascript");
            }
            if (source == null || !StringUtils.hasText(String.valueOf(source))) {
                throw new BusinessException(ResultCode.PARAM_ERROR, "scriptConfig.source 代码不能为空");
            }
            if (String.valueOf(source).length() > SCRIPT_MAX_CHARS) {
                throw new BusinessException(ResultCode.PARAM_ERROR, "代码大小超过 50KB 上限");
            }
        } else {
            throw new BusinessException(ResultCode.PARAM_ERROR, "toolType 仅支持 http / script");
        }
        if (request.getParameters() != null && !(request.getParameters() instanceof Map)) {
            throw new BusinessException(ResultCode.PARAM_ERROR, "parameters 必须为 JSON 对象");
        }
    }

    // ---------------- 辅助 ----------------

    private ToolDefinition getOrThrow(Long id) {
        ToolDefinition definition = toolDefinitionMapper.selectById(id);
        if (definition == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "工具定义不存在");
        }
        return definition;
    }

    private void checkOwner(ToolDefinition definition, Long operatorId) {
        if (!definition.getCreatorId().equals(operatorId)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "仅创建者可操作该工具");
        }
    }

    /** 可见性校验：PRIVATE 非创建者视为不存在（不泄露存在性） */
    private void checkVisible(ToolDefinition definition, Long viewerId) {
        if (!"PUBLIC".equals(definition.getVisibility())
                && !definition.getCreatorId().equals(viewerId)) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "工具定义不存在");
        }
    }

    private String normalizeVisibility(String visibility) {
        return "PUBLIC".equals(visibility) ? "PUBLIC" : "PRIVATE";
    }

    private static java.util.function.Consumer<LambdaQueryWrapper<ToolDefinition>> eqCreator(Long creatorId) {
        return w -> w.eq(ToolDefinition::getCreatorId, creatorId);
    }

    /** 复制名称去冲突：原名、原名_copy、原名_copy_2… */
    private String uniqueCopyName(String baseName, Long ownerId) {
        String candidate = baseName;
        int i = 1;
        while (true) {
            Long count = toolDefinitionMapper.selectCount(new LambdaQueryWrapper<ToolDefinition>()
                    .eq(ToolDefinition::getCreatorId, ownerId)
                    .eq(ToolDefinition::getName, candidate));
            if (count == null || count == 0) {
                return candidate;
            }
            candidate = i == 1 ? baseName + COPY_SUFFIX : baseName + COPY_SUFFIX + "_" + i;
            i++;
        }
    }

    /** 出参：http_config 密钥脱敏 */
    private ToolDefinitionVO toVO(ToolDefinition definition) {
        return ToolDefinitionVO.builder()
                .id(definition.getId())
                .creatorId(definition.getCreatorId())
                .name(definition.getName())
                .displayName(definition.getDisplayName())
                .description(definition.getDescription())
                .toolType(definition.getToolType())
                .parameters(definition.getParameters())
                .httpConfig(ToolSecretUtil.maskSecrets(definition.getHttpConfig()))
                .scriptConfig(definition.getScriptConfig())
                .visibility(definition.getVisibility())
                .createdTime(definition.getCreatedTime())
                .updatedTime(definition.getUpdatedTime())
                .build();
    }
}
