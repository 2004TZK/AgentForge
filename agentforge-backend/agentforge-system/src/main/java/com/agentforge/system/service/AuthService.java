package com.agentforge.system.service;

import com.agentforge.system.dto.LoginRequest;
import com.agentforge.system.dto.RegisterRequest;
import com.agentforge.system.vo.LoginVO;
import com.agentforge.system.vo.UserVO;

/**
 * 认证服务：注册 / 登录 / 当前用户信息。
 */
public interface AuthService {

    /** 注册新用户，成功返回用户信息（不自动登录） */
    UserVO register(RegisterRequest request);

    /** 登录校验，成功签发 JWT 并写入 Redis 会话缓存 */
    LoginVO login(LoginRequest request);

    /** 获取当前登录用户信息 */
    UserVO getCurrentUser(Long userId);
}
