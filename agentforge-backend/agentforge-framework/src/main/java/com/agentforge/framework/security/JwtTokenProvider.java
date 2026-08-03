package com.agentforge.framework.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;

/**
 * JWT 签发与校验（jjwt 0.12.x）。
 * 载荷：sub=userId、username；密钥与有效期均来自环境变量，禁止硬编码。
 */
@Component
public class JwtTokenProvider {

    private final SecretKey secretKey;
    private final Duration expireDuration;

    public JwtTokenProvider(@Value("${agentforge.jwt.secret}") String secret,
                            @Value("${agentforge.jwt.expire-hours:24}") long expireHours) {
        this.secretKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expireDuration = Duration.ofHours(expireHours);
    }

    /** 签发 token，返回原始 JWT 字符串 */
    public String generateToken(Long userId, String username) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claim("username", username)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(expireDuration)))
                .signWith(secretKey)
                .compact();
    }

    /**
     * 解析并校验 token。
     *
     * @return 有效时返回 Claims，无效/过期时返回 null
     */
    public Claims parseToken(String token) {
        try {
            return Jwts.parser().verifyWith(secretKey).build()
                    .parseSignedClaims(token).getPayload();
        } catch (JwtException | IllegalArgumentException e) {
            return null;
        }
    }

    public long getExpireSeconds() {
        return expireDuration.toSeconds();
    }
}
