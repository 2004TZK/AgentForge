package com.agentforge.system.vo;

import lombok.Builder;
import lombok.Data;

/**
 * 登录出参：JWT token 与用户信息。
 */
@Data
@Builder
public class LoginVO {

    /** JWT 访问令牌，请求头 Authorization: Bearer <token> */
    private String token;

    /** 令牌有效期（秒） */
    private long expiresIn;

    private UserVO user;
}
