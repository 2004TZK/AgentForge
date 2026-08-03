package com.agentforge.conversation.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 新建会话入参（name 可空，默认「新会话」）。
 */
@Data
public class CreateSessionRequest {

    @NotNull(message = "agentId 不能为空")
    private Long agentId;

    @Size(max = 100, message = "会话名称长度不能超过 100")
    private String name;
}
