package com.agentforge.system.service.impl;

import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.framework.security.JwtTokenProvider;
import com.agentforge.system.dto.LoginRequest;
import com.agentforge.system.dto.RegisterRequest;
import com.agentforge.system.entity.User;
import com.agentforge.system.mapper.UserMapper;
import com.agentforge.system.service.AuthService;
import com.agentforge.system.vo.LoginVO;
import com.agentforge.system.vo.UserVO;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.Duration;

/**
 * 认证服务实现。
 * Redis 会话缓存 session:user:{id}：Redis 故障时降级为仅 JWT 认证，
 * 不阻断注册/登录主链路（开发期中间件未启动也可跑通）。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private static final String SESSION_KEY_PREFIX = "session:user:";

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final StringRedisTemplate stringRedisTemplate;
    private final ObjectMapper objectMapper;

    @Override
    public UserVO register(RegisterRequest request) {
        // 用户名/邮箱唯一性校验（配合数据库唯一索引兜底）
        boolean usernameExists = userMapper.exists(
                new LambdaQueryWrapper<User>().eq(User::getUsername, request.getUsername()));
        if (usernameExists) {
            throw new BusinessException(ResultCode.RESOURCE_CONFLICT, "用户名已被占用");
        }
        if (StringUtils.hasText(request.getEmail())) {
            boolean emailExists = userMapper.exists(
                    new LambdaQueryWrapper<User>().eq(User::getEmail, request.getEmail()));
            if (emailExists) {
                throw new BusinessException(ResultCode.RESOURCE_CONFLICT, "邮箱已被注册");
            }
        }

        User user = new User();
        user.setUsername(request.getUsername());
        user.setEmail(StringUtils.hasText(request.getEmail()) ? request.getEmail() : null);
        user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
        userMapper.insert(user);

        log.info("用户注册成功: id={}, username={}", user.getId(), user.getUsername());
        return toUserVO(user);
    }

    @Override
    public LoginVO login(LoginRequest request) {
        User user = userMapper.selectOne(
                new LambdaQueryWrapper<User>().eq(User::getUsername, request.getUsername()));
        if (user == null || !passwordEncoder.matches(request.getPassword(), user.getPasswordHash())) {
            throw new BusinessException(ResultCode.LOGIN_FAILED);
        }

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername());
        long expiresIn = jwtTokenProvider.getExpireSeconds();
        cacheSession(user, expiresIn);

        log.info("用户登录成功: id={}, username={}", user.getId(), user.getUsername());
        return LoginVO.builder()
                .token(token)
                .expiresIn(expiresIn)
                .user(toUserVO(user))
                .build();
    }

    @Override
    public UserVO getCurrentUser(Long userId) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "用户不存在或已被删除");
        }
        return toUserVO(user);
    }

    /** 会话缓存：key=session:user:{id}，value=UserVO JSON，TTL 与 JWT 有效期一致 */
    private void cacheSession(User user, long ttlSeconds) {
        try {
            stringRedisTemplate.opsForValue().set(
                    SESSION_KEY_PREFIX + user.getId(),
                    objectMapper.writeValueAsString(toUserVO(user)),
                    Duration.ofSeconds(ttlSeconds));
        } catch (Exception e) {
            log.warn("Redis 会话缓存写入失败（降级为仅 JWT）: userId={}, err={}", user.getId(), e.getMessage());
        }
    }

    private UserVO toUserVO(User user) {
        return UserVO.builder()
                .id(user.getId())
                .username(user.getUsername())
                .email(user.getEmail())
                .avatar(user.getAvatar())
                .createdTime(user.getCreatedTime())
                .build();
    }
}
