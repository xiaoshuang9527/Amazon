/** 认证 store：对接后端 JWT，负责登录态持久化与用户信息加载。 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi, billingApi, errorMessage, getToken, setToken } from '../api'
import type { AuthUser, ShopRead, UsageRead } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(getToken())
  const user = ref<AuthUser | null>(null)
  const loading = ref(false)
  const isLoggedIn = computed(() => Boolean(token.value))
  const isAdmin = computed(() => user.value?.is_admin === true)

  const userNickname = computed(() => user.value?.nickname || '未登录')
  const quotaRemaining = computed(() => user.value?.quotaRemaining ?? 0)
  const quotaTotal = computed(() => user.value?.quotaTotal ?? 0)
  const plan = computed(() => user.value?.plan || 'free')

  /** 拉取当前用户与配额信息，作为登录态的用户画像。 */
  async function loadProfile(): Promise<AuthUser> {
    const me = await authApi.me()
    let usage: UsageRead | null = null
    try {
      usage = await billingApi.usage()
    } catch {
      usage = null
    }
    const profile: AuthUser = {
      ...me,
      nickname: me.email ? me.email.split('@')[0] : '用户',
      plan: usage?.plan || 'free',
      quotaRemaining: usage?.quota_remaining ?? 0,
      quotaTotal: usage?.quota_total ?? 0
    }
    user.value = profile
    return profile
  }

  /** 注册（不含登录态），注册后由调用方决定是否自动登录。 */
  async function register(email: string, password: string): Promise<void> {
    loading.value = true
    try {
      await authApi.register(email, password)
    } finally {
      loading.value = false
    }
  }

  async function login(email: string, password: string): Promise<AuthUser> {
    loading.value = true
    try {
      const result = await authApi.login(email, password)
      token.value = result.access_token
      setToken(result.access_token)
      return await loadProfile()
    } catch (error) {
      logout()
      throw new Error(errorMessage(error, '登录失败，请检查邮箱与密码'))
    } finally {
      loading.value = false
    }
  }

  function logout(): void {
    token.value = ''
    user.value = null
    setToken('')
  }

  /** 校验本地 token 是否仍然有效（用于路由守卫与刷新后恢复会话）。 */
  async function checkToken(): Promise<boolean> {
    if (!token.value) return false
    try {
      await loadProfile()
      return true
    } catch {
      logout()
      return false
    }
  }

  async function restore(): Promise<boolean> {
    if (user.value) return true
    return checkToken()
  }

  async function loadShops(): Promise<ShopRead[]> {
    return authApi.shops()
  }

  return {
    token,
    user,
    loading,
    isLoggedIn,
    isAdmin,
    userNickname,
    quotaRemaining,
    quotaTotal,
    plan,
    register,
    login,
    logout,
    checkToken,
    restore,
    loadProfile,
    loadShops
  }
})
