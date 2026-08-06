package com.agentforge.framework.security;

import com.agentforge.common.exception.BusinessException;
import com.agentforge.common.core.ResultCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

/**
 * AES-GCM 对称加密（自定义工具密钥字段加密，文档 v3.0 §6 安全收口）。
 *
 * <p>密文格式：{@code enc:v1:{ivBase64}:{cipherBase64}}。识别前缀 {@code enc:v1:} 用于
 * 幂等（已加密字段再次保存时不再重复加密）与前后端透传（详情接口一律返回掩码，
 * 掩码值回传时视为"未修改"，保留库中原值）。
 *
 * <p>密钥配置：{@code agentforge.security.tool-secret}（环境变量
 * {@code AGENTFORGE_TOOL_SECRET}，≥32 字节；开发默认值仅限本地）。
 */
@Slf4j
@Component
public class AesGcmCrypto {

    /** 密文前缀（用于识别与幂等判断） */
    public static final String PREFIX = "enc:v1:";

    /** 密钥字段掩码（详情返回 / 前端回显，编辑留空不修改） */
    public static final String MASK = "********";

    private static final int IV_LENGTH = 12;
    private static final int TAG_LENGTH_BITS = 128;
    private static final String ALGORITHM = "AES/GCM/NoPadding";

    private final SecretKeySpec key;

    public AesGcmCrypto(@Value("${agentforge.security.tool-secret:dev-only-tool-secret-0123456789abcdef-0123456789}")
                        String secret) {
        byte[] raw = normalizeKey(secret);
        this.key = new SecretKeySpec(raw, "AES");
    }

    /** 密钥归一化：≥32 字节截断为 32；不足则 SHA-256 派生为 32 字节（防误配短密钥启动崩溃） */
    private byte[] normalizeKey(String secret) {
        if (!StringUtils.hasText(secret)) {
            throw new BusinessException(ResultCode.SYSTEM_ERROR,
                    "agentforge.security.tool-secret 未配置");
        }
        byte[] raw = secret.getBytes(StandardCharsets.UTF_8);
        if (raw.length >= 32) {
            byte[] out = new byte[32];
            System.arraycopy(raw, 0, out, 0, 32);
            return out;
        }
        try {
            var digest = java.security.MessageDigest.getInstance("SHA-256");
            return digest.digest(raw);
        } catch (Exception e) {
            throw new BusinessException(ResultCode.SYSTEM_ERROR, "工具密钥初始化失败");
        }
    }

    /** 加密明文 → enc:v1:{iv}:{cipher}；null/空/已加密 原样返回（幂等） */
    public String encrypt(String plain) {
        if (!StringUtils.hasText(plain) || plain.startsWith(PREFIX)) {
            return plain;
        }
        try {
            byte[] iv = new byte[IV_LENGTH];
            new SecureRandom().nextBytes(iv);
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(TAG_LENGTH_BITS, iv));
            byte[] encrypted = cipher.doFinal(plain.getBytes(StandardCharsets.UTF_8));
            return PREFIX + Base64.getEncoder().encodeToString(iv) + ":"
                    + Base64.getEncoder().encodeToString(encrypted);
        } catch (Exception e) {
            log.error("AES-GCM 加密失败", e);
            throw new BusinessException(ResultCode.SYSTEM_ERROR, "工具密钥加密失败");
        }
    }

    /** 解密；非 enc:v1: 前缀（如旧数据明文）原样返回；解密失败抛业务异常（不静默降级） */
    public String decrypt(String cipherText) {
        if (!StringUtils.hasText(cipherText)) {
            return cipherText;
        }
        if (!cipherText.startsWith(PREFIX)) {
            return cipherText;
        }
        try {
            String body = cipherText.substring(PREFIX.length());
            int sep = body.indexOf(':');
            byte[] iv = Base64.getDecoder().decode(body.substring(0, sep));
            byte[] encrypted = Base64.getDecoder().decode(body.substring(sep + 1));
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(TAG_LENGTH_BITS, iv));
            return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        } catch (Exception e) {
            log.error("AES-GCM 解密失败", e);
            throw new BusinessException(ResultCode.SYSTEM_ERROR, "工具密钥解密失败");
        }
    }

    public boolean isEncrypted(String value) {
        return value != null && value.startsWith(PREFIX);
    }

    public static boolean isMasked(String value) {
        return MASK.equals(value);
    }
}
