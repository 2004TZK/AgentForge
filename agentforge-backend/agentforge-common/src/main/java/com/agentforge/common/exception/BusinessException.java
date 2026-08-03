package com.agentforge.common.exception;

import com.agentforge.common.core.ResultCode;
import lombok.Getter;

/**
 * 业务异常：携带错误码与提示信息，由全局异常处理器统一转换为 Result 响应。
 */
@Getter
public class BusinessException extends RuntimeException {

    private final ResultCode resultCode;

    public BusinessException(ResultCode resultCode) {
        super(resultCode.getMessage());
        this.resultCode = resultCode;
    }

    public BusinessException(ResultCode resultCode, String message) {
        super(message);
        this.resultCode = resultCode;
    }

    public BusinessException(ResultCode resultCode, String message, Throwable cause) {
        super(message, cause);
        this.resultCode = resultCode;
    }
}
