package com.agentforge.system.vo;

import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 用户出参（禁止直接返回 User 实体）。
 */
@Data
@Builder
public class UserVO {

    private Long id;

    private String username;

    private String email;

    private String avatar;

    private LocalDateTime createdTime;
}
