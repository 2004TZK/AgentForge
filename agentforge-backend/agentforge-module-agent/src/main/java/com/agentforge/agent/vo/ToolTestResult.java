package com.agentforge.agent.vo;

import lombok.Builder;
import lombok.Data;

/**
 * 自定义工具测试出参（AI 服务执行结果）。
 */
@Data
@Builder
public class ToolTestResult {

    /** 是否执行成功（HTTP 非 2xx、沙箱超时/报错等均为 false） */
    private boolean ok;

    /** 执行结果（JSON 可序列化；HTTP 工具为响应体文本） */
    private Object result;

    /** 代码工具 stdout（截断后） */
    private String stdout;

    /** 失败原因（ok=false 时：TimeoutError / MemoryLimitError / SyntaxError / HTTP 404 等） */
    private String error;

    /** 执行耗时（毫秒） */
    private long durationMs;
}
