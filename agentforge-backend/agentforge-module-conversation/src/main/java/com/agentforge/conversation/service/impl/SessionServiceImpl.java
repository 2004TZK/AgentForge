package com.agentforge.conversation.service.impl;

import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.conversation.entity.Session;
import com.agentforge.conversation.mapper.SessionMapper;
import com.agentforge.conversation.service.SessionService;
import com.agentforge.conversation.vo.SessionVO;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;

/**
 * 会话服务实现。
 * 权限规则：仅本人可操作（按 userId 归属校验）；删除为逻辑删除，消息历史保留。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SessionServiceImpl implements SessionService {

    private final SessionMapper sessionMapper;

    @Override
    public List<SessionVO> list(Long agentId, Long userId) {
        return sessionMapper.selectList(
                        new LambdaQueryWrapper<Session>()
                                .eq(Session::getAgentId, agentId)
                                .eq(Session::getUserId, userId)
                                .orderByDesc(Session::getUpdatedTime)
                                .orderByDesc(Session::getId))  // 同秒创建时以 ID 倒序稳定排序
                .stream()
                .map(this::toVO)
                .toList();
    }

    @Override
    public SessionVO create(Long agentId, String name, Long userId) {
        Session session = new Session();
        session.setAgentId(agentId);
        session.setUserId(userId);
        session.setName(StringUtils.hasText(name) ? name.trim() : "新会话");
        sessionMapper.insert(session);
        log.info("新建会话: id={}, agentId={}, userId={}", session.getId(), agentId, userId);
        return toVO(session);
    }

    @Override
    public void delete(Long sessionId, Long userId) {
        Session session = getSessionOrThrow(sessionId);
        if (!session.getUserId().equals(userId)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "仅创建者可删除该会话");
        }
        sessionMapper.deleteById(sessionId);
        log.info("删除会话: id={}, userId={}", sessionId, userId);
    }

    // ---------------- 私有方法 ----------------

    private Session getSessionOrThrow(Long sessionId) {
        Session session = sessionMapper.selectById(sessionId);
        if (session == null) {
            throw new BusinessException(ResultCode.RESOURCE_NOT_FOUND, "会话不存在");
        }
        return session;
    }

    private SessionVO toVO(Session session) {
        return SessionVO.builder()
                .id(session.getId())
                .agentId(session.getAgentId())
                .name(session.getName())
                .createdTime(session.getCreatedTime())
                .updatedTime(session.getUpdatedTime())
                .build();
    }
}
