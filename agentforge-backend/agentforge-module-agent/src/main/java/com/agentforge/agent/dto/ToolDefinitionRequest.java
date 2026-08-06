package com.agentforge.agent.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.Map;

/**
 * 用户自定义工具创建/更新入参（工具定义开发文档 v3.0 §5.1）。
 *
 * <p>toolType=http 时必填 httpConfig；toolType=script 时必填 scriptConfig；
 * 密钥字段允许传掩码（********）表示"不修改"，由 Service 合并库中原值。
 */
@Data
public class ToolDefinitionRequest {

    /** 工具名：小写字母开头，小写字母/数字/下划线，2-50 位，供 LLM 调用 */
    @NotBlank(message = "工具名不能为空")
    @Pattern(regexp = "^[a-z][a-z0-9_]{1,49}$", message = "工具名须为小写字母开头，含小写字母/数字/下划线，长度 2-50")
    private String name;

    @NotBlank(message = "展示名称不能为空")
    @Size(max = 100, message = "展示名称长度不能超过 100")
    private String displayName;

    @Size(max = 500, message = "描述长度不能超过 500")
    private String description;

    /** http / script */
    @NotBlank(message = "工具类型不能为空")
    @Pattern(regexp = "http|script", message = "工具类型仅支持 http / script")
    private String toolType;

    /** LLM 调用参数 Schema（OpenAI function parameters） */
    private Map<String, Object> parameters;

    /** HTTP 请求定义（toolType=http 必填） */
    private Map<String, Object> httpConfig;

    /** 代码定义（toolType=script 必填） */
    private Map<String, Object> scriptConfig;

    /** PRIVATE / PUBLIC */
    private String visibility = "PRIVATE";
}
