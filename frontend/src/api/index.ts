/**
 * 统一 API 层。
 *
 * - 请求拦截注入 JWT；响应拦截直接返回 data，业务层拿到的就是数据体；
 * - 401 统一登出（登录/注册请求自身失败不触发跳转，避免误伤）；
 * - token 读写集中在本模块，store 通过 getToken/setToken 复用，避免循环依赖。
 */

import axios from 'axios'
import type { AxiosError, AxiosRequestConfig, AxiosInstance } from 'axios'
import type {
  AdminStats,
  AdminUserPage,
  AdminUserRow,
  ApplyRequest,
  ApplyResponse,
  ExportFormat,
  GenerationRow,
  ListingDiff,
  ListingRow,
  PlanRead,
  ShopRead,
  SourceContentPayload,
  SubscribeResponse,
  TaskStatus,
  TokenRead,
  UsageRead,
  UserRead
} from '../types'

const TOKEN_KEY = 'amazon_listing_token'

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setToken(token: string): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  } catch {
    /* localStorage 不可用时静默降级为内存态 */
  }
}

export const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 60000
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    const response = error.response
    // blob 请求失败时，错误体也是 Blob，需还原成 JSON 才能展示后端 message。
    if (response && typeof Blob !== 'undefined' && response.data instanceof Blob) {
      try {
        const text = await response.data.text()
        response.data = JSON.parse(text)
      } catch {
        /* 非 JSON 时保留原始 Blob */
      }
    }
    const url = error.config?.url || ''
    const isAuthEntry = url.includes('/auth/token') || url.includes('/auth/register')
    if (response?.status === 401 && !isAuthEntry) {
      setToken('')
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

function request<T>(config: AxiosRequestConfig): Promise<T> {
  return api.request(config) as unknown as Promise<T>
}

export function httpGet<T>(url: string, params?: Record<string, any>): Promise<T> {
  return request<T>({ method: 'GET', url, params })
}

export function httpPost<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
  return request<T>({ method: 'POST', url, data, ...config })
}

/** 从各类异常里抽取可展示的错误信息。 */
export function errorMessage(error: unknown, fallback = '请求失败，请稍后重试'): string {
  const err = error as AxiosError<any>
  const data = err?.response?.data
  if (data && typeof data === 'object') {
    const msg = (data as any).message || (data as any).detail
    if (typeof msg === 'string' && msg) return msg
  }
  if (err?.message) return err.message
  return fallback
}

/** 取出后端统一错误体（含 code / message / details）。 */
export function errorPayload(error: unknown): any {
  return (error as AxiosError<any>)?.response?.data
}

/** 触发浏览器下载。 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const authApi = {
  changePassword: (oldPassword: string, newPassword: string) =>
    httpPost<{ message: string }>('/auth/password', {
      old_password: oldPassword,
      new_password: newPassword
    }),
  register: (email: string, password: string) =>
    httpPost<UserRead>('/auth/register', { email, password }),
  login: (email: string, password: string) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    return httpPost<TokenRead>('/auth/token', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
  },
  me: () => httpGet<UserRead>('/auth/me'),
  shops: () => httpGet<ShopRead[]>('/auth/shops'),
  authorizeUrl: () =>
    httpGet<{ authorize_url: string; state: string; configured: boolean }>('/auth/spapi/authorize'),
  revokeShop: (shopId: number) =>
    request<{ shop_id: number; message: string }>({
      method: 'DELETE',
      url: `/auth/shops/${shopId}`
    })
}

export const billingApi = {
  usage: () => httpGet<UsageRead>('/billing/usage'),
  plans: () => httpGet<PlanRead[]>('/billing/plans'),
  subscribe: (plan: string, period: 'monthly' | 'yearly' = 'monthly') =>
    httpPost<SubscribeResponse>('/billing/subscribe', { plan, period })
}

export const adminApi = {
  stats: () => httpGet<AdminStats>('/admin/stats'),
  users: (limit = 50, offset = 0) =>
    httpGet<AdminUserPage>('/admin/users', { limit, offset }),
  user: (userId: number) => httpGet<AdminUserRow>(`/admin/users/${userId}`),
  update: (userId: number, payload: { is_active?: boolean; is_admin?: boolean }) =>
    request<AdminUserRow>({ method: 'PATCH', url: `/admin/users/${userId}`, data: payload }),
  resetPassword: (userId: number, newPassword: string) =>
    httpPost<{ user_id: number; email: string; message: string }>(
      `/admin/users/${userId}/reset-password`,
      { new_password: newPassword }
    )
}

export const generateApi = {
  submit: (payload: {
    shop_id?: number | null
    listing_id?: number | null
    source_content: SourceContentPayload
    target_marketplaces: string[]
    category: string
    tone: string
    quality: string
  }) => httpPost<{ task_id: string; status: string; message: string }>('/generate/listing', payload),
  status: (taskId: string) => httpGet<TaskStatus>(`/generate/${taskId}`),
  history: (limit = 50) => httpGet<GenerationRow[]>('/generate/history', { limit }),
  exportFile: (taskId: string, format: ExportFormat) =>
    request<Blob>({
      method: 'GET',
      url: `/generate/${taskId}/export`,
      params: { format },
      responseType: 'blob'
    })
}

export const listingsApi = {
  list: () => httpGet<ListingRow[]>('/listings'),
  detail: (listingId: number) => httpGet<ListingRow>(`/listings/${listingId}`),
  create: (payload: {
    shop_id?: number | null
    asin?: string | null
    sku?: string | null
    marketplace_id?: string | null
    source_language?: string
    source_content: SourceContentPayload
  }) => httpPost<ListingRow>('/listings', payload),
  diff: (listingId: number, taskId: string, marketplaceId: string) =>
    httpGet<ListingDiff>(`/listings/${listingId}/diff`, {
      task_id: taskId,
      marketplace_id: marketplaceId
    }),
  apply: (listingId: number, payload: ApplyRequest) =>
    httpPost<ApplyResponse>(`/listings/${listingId}/apply`, payload)
}

export default api
