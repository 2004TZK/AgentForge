package com.agentforge.framework.context;

import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/**
 * 当前登录用户上下文：从 SecurityContext 读取 userId。
 * principal 由 JwtAuthenticationFilter 写入（Long 类型）。
 */
public final class UserContext {

    private UserContext() {
    }

    /** 获取当前登录用户 ID；未登录抛认证异常 */
    public static Long getUserId() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof Long userId)) {
            throw new BusinessException(ResultCode.UNAUTHORIZED);
        }
        return userId;
    }

    /** 是否已登录（供公开接口判断可选登录场景使用） */
    public static boolean isLoggedIn() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        return authentication != null && authentication.getPrincipal() instanceof Long;
    }
}
