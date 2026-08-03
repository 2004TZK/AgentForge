package com.agentforge.conversation.controller;

import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.Result;
import com.agentforge.conversation.dto.ChatRequest;
import com.agentforge.conversation.service.ConversationService;
import com.agentforge.conversation.vo.ChatVO;
import com.agentforge.conversation.vo.ConversationVO;
import com.agentforge.framework.context.UserContext;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

/**
 * 对话接口：发送消息（同步/SSE 流式）/ 历史查询。
 * 同步 JSON（Phase 1-2）；M1 起增加 /chat/stream（SSE 打字机透传）。
 */
@Tag(name = "对话")
@Validated
@RestController
@RequestMapping("/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ConversationService conversationService;

    @Operation(summary = "发送消息（同步回答）")
    @PostMapping
    public Result<ChatVO> chat(@Valid @RequestBody ChatRequest request) {
        return Result.success(conversationService.chat(request, UserContext.getUserId()));
    }

    /**
     * SSE 流式回答：原始事件流透传（delta 逐块输出 / done 汇总 / error 失败）。
     * 响应头禁用缓存与 Nginx 代理缓冲（X-Accel-Buffering），保证逐字到达。
     */
    @Operation(summary = "发送消息（SSE 流式回答）")
    @PostMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public ResponseEntity<StreamingResponseBody> chatStream(@Valid @RequestBody ChatRequest request) {
        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_EVENT_STREAM)
                .header(HttpHeaders.CACHE_CONTROL, "no-cache")
                .header("X-Accel-Buffering", "no")
                .body(conversationService.chatStream(request, UserContext.getUserId()));
    }

    @Operation(summary = "历史记录分页（可按会话隔离）")
    @GetMapping("/history")
    public Result<PageResult<ConversationVO>> history(
            @RequestParam @NotNull(message = "agentId 不能为空") Long agentId,
            @RequestParam(required = false) Long sessionId,
            @RequestParam(defaultValue = "1") @Min(value = 1, message = "page 需 >= 1") long page,
            @RequestParam(defaultValue = "20") @Min(value = 1) @Max(value = 100, message = "size 需 <= 100") long size) {
        return Result.success(conversationService.history(agentId, sessionId,
                UserContext.getUserId(), page, size));
    }
}
