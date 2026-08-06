/** 文件接口：上传（含切片方式）/ 预览 / 列表 / 删除 / 重试入库 */
import request from '../utils/request'
import type { PageQuery, PageResult } from '../types/api'
import type { DocumentItem, SlicePreview } from '../types/chat'

export interface UploadOptions {
  slicingMode?: 'auto' | 'manual'
  slicingConfig?: string
}

export function apiUploadFile(agentId: number, file: File, options: UploadOptions = {},
                              onProgress?: (percent: number) => void): Promise<DocumentItem> {
  const form = new FormData()
  form.append('file', file)
  return request.post('/file/upload', form, {
    params: { agentId, ...options },
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    },
  }) as Promise<DocumentItem>
}

/** 手动切片预览：只读解析结构 + 样例 chunk，不入库 */
export function apiPreviewFile(file: File, options: UploadOptions = {}): Promise<SlicePreview> {
  const form = new FormData()
  form.append('file', file)
  return request.post('/file/preview', form, {
    params: { ...options },
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<SlicePreview>
}

export function apiFileList(agentId: number, params: PageQuery): Promise<PageResult<DocumentItem>> {
  return request.get('/file/list', { params: { agentId, ...params } }) as Promise<PageResult<DocumentItem>>
}

export function apiDeleteFile(id: number): Promise<void> {
  return request.delete(`/file/${id}`) as Promise<void>
}

export function apiRetryFile(id: number): Promise<DocumentItem> {
  return request.post(`/file/${id}/retry`) as Promise<DocumentItem>
}
