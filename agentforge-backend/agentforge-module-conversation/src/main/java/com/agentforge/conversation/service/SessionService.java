package com.agentforge.conversation.service;

import com.agentforge.conversation.vo.SessionVO;

import java.util.List;

/**
 * 会话服务：列表 / 新建 / 删除（基础版，不做重命名/搜索/归档，见规划决策 #2）。
 */
public interface SessionService {

    /** 某智能体下当前用户的会话列表（按最后活跃时间倒序） */
    List<SessionVO> list(Long agentId, Long userId);

    /** 新建会话（name 可空，默认「新会话」） */
    SessionVO create(Long agentId, String name, Long userId);

    /** 删除会话（逻辑删除；其下消息保留，避免误删） */
    void delete(Long sessionId, Long userId);
}
