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
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 对话接口：发送消息 / 历史查询。
 * 发送走同步 JSON（Phase 1-2），Phase 3 起增加 /chat/stream（SSE）。
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

    @Operation(summary = "历史记录分页")
    @GetMapping("/history")
    public Result<PageResult<ConversationVO>> history(
            @RequestParam @NotNull(message = "agentId 不能为空") Long agentId,
            @RequestParam(defaultValue = "1") @Min(value = 1, message = "page 需 >= 1") long page,
            @RequestParam(defaultValue = "20") @Min(value = 1) @Max(value = 100, message = "size 需 <= 100") long size) {
        return Result.success(conversationService.history(agentId, UserContext.getUserId(), page, size));
    }
}
