package com.agentforge.agent.util;

import com.agentforge.framework.security.AesGcmCrypto;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 自定义工具配置中的密钥字段处理：加密入库 / 脱敏出参 / 编辑合并保留原值。
 *
 * <p>密钥识别规则：任意层级的 key 包含 {@code key/token/secret/password/pwd}（忽略大小写）
 * 且值为非空字符串。递归遍历 http_config / script_config / agent_tool.tool_config 等
 * 任意 JSON 结构（Map / List / 标量）。
 */
public final class ToolSecretUtil {

    /** 密钥字段 key 识别正则 */
    private static final java.util.regex.Pattern SECRET_KEY =
            java.util.regex.Pattern.compile("(?i).*(key|token|secret|password|pwd).*");

    /**
     * 是否密钥字段：key 名命中关键词（key/token/secret/password/pwd），
     * 或位于 auth 认证结构内（value/username/password 均为密钥位，如
     * {"auth": {"type":"api_key","headerName":"X-API-Key","value":"sk-xxx"}}）。
     */
    private static boolean isSecretField(String key, boolean inAuth) {
        if (inAuth && ("value".equals(key) || "username".equals(key)
                || "password".equals(key) || "secret".equals(key))) {
            return true;
        }
        return SECRET_KEY.matcher(key).matches();
    }

    private ToolSecretUtil() {
    }

    /** 加密：深拷贝后加密密钥字段（已加密的跳过，幂等） */
    public static Map<String, Object> encryptSecrets(Map<String, Object> config, AesGcmCrypto crypto) {
        if (config == null || config.isEmpty()) {
            return config;
        }
        return (Map<String, Object>) walk(config, crypto, true);
    }

    /** 解密：深拷贝后密钥字段密文（enc:v1: 前缀）解密为明文（装配链路透传 AI 服务前） */
    public static Map<String, Object> decryptSecrets(Map<String, Object> config, AesGcmCrypto crypto) {
        if (config == null || config.isEmpty()) {
            return config;
        }
        return (Map<String, Object>) walk(config, crypto, false, true);
    }

    /** 脱敏：深拷贝后密钥字段替换为掩码（详情返回用） */
    public static Map<String, Object> maskSecrets(Map<String, Object> config) {
        if (config == null || config.isEmpty()) {
            return config;
        }
        return (Map<String, Object>) walk(config, null, false);
    }

    /**
     * 编辑合并：incoming 中值为掩码的字段回填 old 中的对应值（"编辑留空不修改"），
     * 递归处理嵌套结构（如 auth.value 掩码保留库中原密文）。返回新 map。
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> mergeSecrets(Map<String, Object> oldConfig,
                                                   Map<String, Object> incoming,
                                                   AesGcmCrypto crypto) {
        if (incoming == null) {
            return null;
        }
        return (Map<String, Object>) mergeNode(oldConfig, incoming, crypto);
    }

    /** 递归合并：掩码字符串 → 保留旧节点原值（可能为密文）；其余递归/原样 */
    @SuppressWarnings("unchecked")
    private static Object mergeNode(Object oldNode, Object incoming, AesGcmCrypto crypto) {
        if (incoming instanceof Map<?, ?> map) {
            Map<String, Object> result = new HashMap<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                String key = String.valueOf(e.getKey());
                Object inValue = e.getValue();
                Object oldValue = oldNode instanceof Map<?, ?> oldMap ? oldMap.get(key) : null;
                if (inValue instanceof String s && AesGcmCrypto.isMasked(s)) {
                    result.put(key, oldValue);
                } else {
                    result.put(key, mergeNode(oldValue, inValue, crypto));
                }
            }
            return result;
        }
        if (incoming instanceof List<?> list) {
            List<Object> result = new ArrayList<>(list.size());
            List<?> oldList = oldNode instanceof List<?> l ? l : List.of();
            for (int i = 0; i < list.size(); i++) {
                Object oldItem = i < oldList.size() ? oldList.get(i) : null;
                result.add(mergeNode(oldItem, list.get(i), crypto));
            }
            return result;
        }
        return incoming;
    }

    /** 递归遍历：encrypt=true 加密密钥字段；false 替换为掩码 */
    @SuppressWarnings("unchecked")
    private static Object walk(Object node, AesGcmCrypto crypto, boolean encrypt) {
        return walk(node, crypto, encrypt, false, false);
    }

    /** 递归遍历：encrypt=true 加密；decrypt=true 解密；否则替换为掩码 */
    @SuppressWarnings("unchecked")
    private static Object walk(Object node, AesGcmCrypto crypto, boolean encrypt, boolean decrypt) {
        return walk(node, crypto, encrypt, decrypt, false);
    }

    /** 递归遍历（inAuth：父级为 auth 认证结构时 value/username/password 视为密钥） */
    @SuppressWarnings("unchecked")
    private static Object walk(Object node, AesGcmCrypto crypto, boolean encrypt,
                               boolean decrypt, boolean inAuth) {
        if (node instanceof Map<?, ?> map) {
            Map<String, Object> result = new HashMap<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                String key = String.valueOf(e.getKey());
                Object value = e.getValue();
                boolean childInAuth = inAuth || "auth".equalsIgnoreCase(key);
                if (value instanceof String s && !s.isEmpty() && isSecretField(key, inAuth)) {
                    if (encrypt) {
                        result.put(key, crypto.encrypt(s));
                    } else if (decrypt) {
                        result.put(key, crypto.decrypt(s));
                    } else {
                        result.put(key, AesGcmCrypto.MASK);
                    }
                } else {
                    result.put(key, walk(value, crypto, encrypt, decrypt, childInAuth));
                }
            }
            return result;
        }
        if (node instanceof List<?> list) {
            List<Object> result = new ArrayList<>(list.size());
            for (Object item : list) {
                result.add(walk(item, crypto, encrypt, decrypt, false));
            }
            return result;
        }
        return node;
    }
}
