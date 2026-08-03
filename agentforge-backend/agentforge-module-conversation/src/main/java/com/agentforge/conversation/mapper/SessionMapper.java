package com.agentforge.conversation.mapper;

import com.agentforge.conversation.entity.Session;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * 会话表 Mapper。
 */
@Mapper
public interface SessionMapper extends BaseMapper<Session> {
}
