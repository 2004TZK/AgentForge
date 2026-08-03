package com.agentforge.file.mapper;

import com.agentforge.file.entity.Document;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * 文档表 Mapper。
 */
@Mapper
public interface DocumentMapper extends BaseMapper<Document> {
}
