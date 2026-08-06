package com.agentforge.file.controller;

import com.agentforge.aigateway.config.AiGatewayProperties;
import com.agentforge.aigateway.dto.AiPreviewResponse;
import com.agentforge.common.core.PageResult;
import com.agentforge.common.core.Result;
import com.agentforge.common.core.ResultCode;
import com.agentforge.common.exception.BusinessException;
import com.agentforge.framework.context.UserContext;
import com.agentforge.file.dto.ProgressRequest;
import com.agentforge.file.service.FileService;
import com.agentforge.file.vo.DocumentVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.util.StringUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文件接口：上传（含切片方式）/ 预览 / 列表 / 删除 / 重试入库 / 内部进度回写。
 */
@Tag(name = "文件")
@Validated
@RestController
@RequestMapping("/file")
@RequiredArgsConstructor
public class FileController {

    private final FileService fileService;
    private final AiGatewayProperties aiGatewayProperties;

    @Operation(summary = "上传文档（自动触发 RAG 入库；slicingMode=manual 时提交切片参数）")
    @PostMapping("/upload")
    public Result<DocumentVO> upload(@RequestParam @NotNull(message = "agentId 不能为空") Long agentId,
                                     @RequestParam("file") MultipartFile file,
                                     @RequestParam(required = false) String slicingMode,
                                     @RequestParam(required = false) String slicingConfig) {
        return Result.success(fileService.upload(agentId, file, slicingMode, slicingConfig));
    }

    @Operation(summary = "手动切片预览（数据库/表格类文件，只读解析结构 + 样例 chunk，不入库）")
    @PostMapping("/preview")
    public Result<AiPreviewResponse> preview(@RequestParam("file") MultipartFile file,
                                             @RequestParam(required = false) String slicingMode,
                                             @RequestParam(required = false) String slicingConfig) {
        return Result.success(fileService.preview(file, slicingMode, slicingConfig));
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

    @Operation(summary = "重试 RAG 入库（PENDING/FAILED 状态，沿用原切片配置）")
    @PostMapping("/{id}/retry")
    public Result<DocumentVO> retry(@PathVariable Long id) {
        return Result.success(fileService.retryIngest(id, UserContext.getUserId()));
    }

    /**
     * 入库进度回写（仅 AI 服务内部调用，X-Internal-Token 校验与 AI 服务配置一致）。
     * AI 服务分批回写 processedChunks/totalChunks，完成/失败回写 status。
     */
    @Operation(summary = "入库进度回写（内部接口）", hidden = true)
    @PostMapping("/{id}/progress")
    public Result<Void> progress(@PathVariable Long id,
                                 @RequestHeader(value = "X-Internal-Token", required = false) String token,
                                 @RequestBody ProgressRequest request) {
        if (!StringUtils.hasText(token)
                || !token.equals(aiGatewayProperties.getInternalToken())) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "内部鉴权失败");
        }
        request.setDocumentId(id);
        fileService.updateProgress(id, request);
        return Result.success();
    }
}
