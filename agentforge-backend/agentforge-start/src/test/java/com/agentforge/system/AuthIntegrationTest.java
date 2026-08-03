package com.agentforge.system;

import com.agentforge.IntegrationTestBase;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 认证接口集成测试：注册 / 登录 / 当前用户 / 401 拦截。
 */
class AuthIntegrationTest extends IntegrationTestBase {

    @Test
    @DisplayName("注册成功返回用户信息（不含密码哈希）")
    void registerSuccess() throws Exception {
        mockMvc.perform(post("/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"alice","password":"%s","email":"alice@test.local"}"""
                                .formatted(TEST_PASSWORD)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.username").value("alice"))
                .andExpect(jsonPath("$.data.id").isNumber())
                .andExpect(jsonPath("$.data.passwordHash").doesNotExist());
    }

    @Test
    @DisplayName("重复用户名注册返回 10004 资源冲突")
    void registerDuplicateUsername() throws Exception {
        register("alice");
        mockMvc.perform(post("/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"alice","password":"%s"}""".formatted(TEST_PASSWORD)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10004));
    }

    @Test
    @DisplayName("用户名格式不合法返回 10001 参数错误")
    void registerInvalidUsername() throws Exception {
        mockMvc.perform(post("/auth/register")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"a!","password":"%s"}""".formatted(TEST_PASSWORD)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10001));
    }

    @Test
    @DisplayName("登录成功返回 token 与用户信息")
    void loginSuccess() throws Exception {
        register("alice");
        mockMvc.perform(post("/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"alice","password":"%s"}""".formatted(TEST_PASSWORD)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.token").isNotEmpty())
                .andExpect(jsonPath("$.data.user.username").value("alice"));
    }

    @Test
    @DisplayName("密码错误返回 20004")
    void loginWrongPassword() throws Exception {
        register("alice");
        mockMvc.perform(post("/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"alice","password":"wrong-pass-1"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(20004));
    }

    @Test
    @DisplayName("携带 token 可访问 /auth/me")
    void meWithToken() throws Exception {
        String token = registerAndLogin("alice");
        mockMvc.perform(get("/auth/me")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.username").value("alice"));
    }

    @Test
    @DisplayName("未登录访问受保护接口：HTTP 401 + code 20001")
    void noTokenReturns401() throws Exception {
        mockMvc.perform(get("/auth/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(20001));
    }

    @Test
    @DisplayName("非法 token：HTTP 401 + code 20001（过滤器不认证，走统一 401 出口）")
    void invalidTokenReturns401() throws Exception {
        mockMvc.perform(get("/auth/me")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer invalid.token.value"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(20001));
    }
}
