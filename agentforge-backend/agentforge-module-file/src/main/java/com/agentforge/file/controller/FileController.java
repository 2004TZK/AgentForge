package com.agentforge.file.controller;

import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.Result;
import com.agentforge.framework.context.UserContext;
import com.agentforge.file.service.FileService;
import com.agentforge.file.vo.DocumentVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文件接口：上传 / 列表 / 删除 / 重试入库。
 */
@Tag(name = "文件")
@Validated
@RestController
@RequestMapping("/file")
@RequiredArgsConstructor
public class FileController {

    private final FileService fileService;

    @Operation(summary = "上传文档（自动触发 RAG 入库）")
    @PostMapping("/upload")
    public Result<DocumentVO> upload(@RequestParam @NotNull(message = "agentId 不能为空") Long agentId,
                                     @RequestParam("file") MultipartFile file) {
        return Result.success(fileService.upload(agentId, file));
    }

    @Operation(summary = "文档列表")
    @GetMapping("/list")
    public Result<PageResult<DocumentVO>> list(
            @RequestParam @NotNull(message = "agentId 不能为空") Long agentId,
            @RequestParam(defaultValue = "1") @Min(value = 1, message = "page 需 >= 1") long page,
            @RequestParam(defaultValue = "20") @Min(value = 1) @Max(value = 100, message = "size 需 <= 100") long size) {
        return Result.success(fileService.list(agentId, page, size));
    }

    @Operation(summary = "删除文档（元数据 + 磁盘文件 + Qdrant 向量）")
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        fileService.delete(id, UserContext.getUserId());
        return Result.success();
    }

    @Operation(summary = "重试 RAG 入库（PENDING/FAILED 状态）")
    @PostMapping("/{id}/retry")
    public Result<DocumentVO> retry(@PathVariable Long id) {
        return Result.success(fileService.retryIngest(id, UserContext.getUserId()));
    }
}
