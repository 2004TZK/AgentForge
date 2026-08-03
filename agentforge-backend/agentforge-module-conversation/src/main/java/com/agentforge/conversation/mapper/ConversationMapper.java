package com.agentforge.conversation.mapper;

import com.agentforge.conversation.entity.Conversation;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * 对话记录表 Mapper。
 */
@Mapper
public interface ConversationMapper extends BaseMapper<Conversation> {
}
