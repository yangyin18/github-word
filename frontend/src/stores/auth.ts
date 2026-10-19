/**
 * 全局登录态：应用级单例（reactive），所有页面共享同一份用户状态。
 * 登录 / 退出后状态即时同步，避免各页面各自维护导致不同步。
 */
import { reactive } from 'vue'
import { authApi, type UserInfo } from '../api'

interface AuthState {
  user: UserInfo | null
  /** 是否已完成首次 /me 查询（避免闪烁） */
  ready: boolean
}

export const auth = reactive<AuthState>({
  user: null,
  ready: false,
})

let mePromise: Promise<void> | null = null

/** 查询登录态（幂等：已完成则直接返回，并发请求共享同一个 Promise） */
export function ensureMe(): Promise<void> {
  if (auth.ready) return Promise.resolve()
  if (!mePromise) {
    mePromise = (async () => {
      try {
        const { data } = await authApi.me()
        auth.user = data.logged_in ? data.user : null
      } catch {
        auth.user = null
      } finally {
        auth.ready = true
        mePromise = null
      }
    })()
  }
  return mePromise
}

/** 跳转 GitHub OAuth 登录 */
export function login(): void {
  window.location.href = '/api/auth/login'
}

/** 退出：调用后端清 session，无论成败都清理本地登录态 */
export async function logout(): Promise<void> {
  try {
    await authApi.logout()
  } catch {
    // 后端不可达 / session 已过期等场景：仍然清理本地状态
  }
  auth.user = null
}
