/** 模型 Provider API（M4 多模型配置） */
import request from '../utils/request'
import type { Provider, ProviderPayload } from '../types/provider'

export function apiProviderList(): Promise<Provider[]> {
  return request.get('/model/providers')
}

export function apiCreateProvider(payload: ProviderPayload): Promise<Provider> {
  return request.post('/model/providers', payload)
}

export function apiUpdateProvider(id: number, payload: ProviderPayload): Promise<Provider> {
  return request.put(`/model/providers/${id}`, payload)
}

export function apiDeleteProvider(id: number): Promise<void> {
  return request.delete(`/model/providers/${id}`)
}
