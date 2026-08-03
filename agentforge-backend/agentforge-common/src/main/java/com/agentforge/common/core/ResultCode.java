package com.agentforge.common.core;

import lombok.Getter;

/**
 * 统一错误码（分段约定见设计文档 7.2 节）：
 * <ul>
 *   <li>0：成功</li>
 *   <li>10xxx：参数/业务错误</li>
 *   <li>20xxx：认证/授权错误</li>
 *   <li>30xxx：AI 服务错误</li>
 *   <li>40xxx：文件/RAG 错误</li>
 *   <li>50xxx：系统内部错误</li>
 * </ul>
 */
@Getter
public enum ResultCode {

    SUCCESS(0, "成功"),

    // ---- 10xxx 参数 / 业务错误 ----
    PARAM_ERROR(10001, "参数错误"),
    BUSINESS_ERROR(10002, "业务处理失败"),
    RESOURCE_NOT_FOUND(10003, "资源不存在"),
    RESOURCE_CONFLICT(10004, "资源冲突或已存在"),

    // ---- 20xxx 认证 / 授权错误 ----
    UNAUTHORIZED(20001, "未登录或登录已过期"),
    TOKEN_INVALID(20002, "无效的登录凭证"),
    FORBIDDEN(20003, "没有操作权限"),
    LOGIN_FAILED(20004, "用户名或密码错误"),

    // ---- 30xxx AI 服务错误 ----
    AI_TIMEOUT(30001, "AI 服务调用超时"),
    AI_UNAVAILABLE(30002, "AI 服务不可用"),
    LLM_ERROR(30003, "模型调用失败"),

    // ---- 40xxx 文件 / RAG 错误 ----
    FILE_TYPE_NOT_ALLOWED(40001, "不支持的文件类型"),
    FILE_TOO_LARGE(40002, "文件大小超出限制（20MB）"),
    FILE_EMPTY(40003, "文件内容为空"),
    RAG_ERROR(40004, "知识库处理失败"),

    // ---- 50xxx 系统错误 ----
    SYSTEM_ERROR(50000, "系统内部错误");

    private final int code;
    private final String message;

    ResultCode(int code, String message) {
        this.code = code;
        this.message = message;
    }
}
