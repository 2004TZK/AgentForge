package com.agentforge.conversation.controller;

import com.agentforge.common.core.Result;
import com.agentforge.conversation.dto.CreateSessionRequest;
import com.agentforge.conversation.service.SessionService;
import com.agentforge.conversation.vo.SessionVO;
import com.agentforge.framework.context.UserContext;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 会话接口（M2 多会话）：列表 / 新建 / 删除。
 */
@Tag(name = "会话")
@Validated
@RestController
@RequestMapping("/chat/session")
@RequiredArgsConstructor
public class SessionController {

    private final SessionService sessionService;

    @Operation(summary = "会话列表（按最后活跃倒序）")
    @GetMapping("/list")
    public Result<List<SessionVO>> list(
            @RequestParam @NotNull(message = "agentId 不能为空") Long agentId) {
        return Result.success(sessionService.list(agentId, UserContext.getUserId()));
    }

    @Operation(summary = "新建会话")
    @PostMapping
    public Result<SessionVO> create(@Valid @RequestBody CreateSessionRequest request) {
        return Result.success(sessionService.create(request.getAgentId(), request.getName(),
                UserContext.getUserId()));
    }

    @Operation(summary = "删除会话（逻辑删除，消息历史保留）")
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        sessionService.delete(id, UserContext.getUserId());
        return Result.success();
    }
}
