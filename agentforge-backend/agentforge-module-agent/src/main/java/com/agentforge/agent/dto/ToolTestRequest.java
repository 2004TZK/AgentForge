package com.agentforge.agent.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.Map;

/**
 * 自定义工具测试入参：定义 + 示例参数 → 由后端透传 AI 服务执行（HTTP 直发 / 代码进沙箱）。
 */
@Data
public class ToolTestRequest {

    /** http / script */
    @NotBlank(message = "工具类型不能为空")
    private String toolType;

    /** HTTP 请求定义（toolType=http） */
    private Map<String, Object> httpConfig;

    /** 代码定义（toolType=script） */
    private Map<String, Object> scriptConfig;

    /** LLM 调用参数 Schema */
    private Map<String, Object> parameters;

    /** 示例参数（LLM 视角的入参） */
    private Map<String, Object> args;
}
