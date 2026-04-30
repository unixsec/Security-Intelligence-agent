/**
 * Auth store (FE-1).
 *
 * Persists access + refresh tokens in localStorage and exposes login /
 * logout actions used by the Login view, the axios interceptor, and the
 * router guard. No fancy SSR support — Vite-built SPA only.
 */
import { defineStore } from 'pinia'
// Use raw axios so the auth store does not pull api -> stores/auth (cycle)
// at module load time. Calls go directly to /api/v1/auth/*.
import axios from 'axios'

const _http = axios.create({ baseURL: '/api/v1', timeout: 30000 })

const ACCESS_KEY = 'sia_access_token'
const REFRESH_KEY = 'sia_refresh_token'
const USER_KEY = 'sia_user'

function _readUser () {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (_) {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem(ACCESS_KEY) || '',
    refreshToken: localStorage.getItem(REFRESH_KEY) || '',
    user: _readUser(),
  }),

  getters: {
    isAuthenticated: (s) => Boolean(s.accessToken),
    role: (s) => s.user?.role || 'viewer',
  },

  actions: {
    async login ({ username, password, provider = 'local' }) {
      const resp = await _http.post('/auth/login', { username, password, provider })
      this._persist(resp.data)
      return resp.data
    },

    async fetchMe () {
      // Useful after page refresh to validate the token is still good.
      const resp = await _http.get('/auth/me', {
        headers: { Authorization: `Bearer ${this.accessToken}` },
      })
      this.user = resp.data
      localStorage.setItem(USER_KEY, JSON.stringify(resp.data))
      return resp.data
    },

    async logout () {
      // Tell the server first so the refresh token is invalidated and the
      // access token's jti is added to the Redis blacklist (SEC-4).
      try {
        await _http.post('/auth/logout', {
          access_token: this.accessToken,
          refresh_token: this.refreshToken,
        })
      } catch (_) {
        // Best-effort; clear locally regardless.
      }
      this._clear()
    },

    async refresh () {
      if (!this.refreshToken) throw new Error('No refresh token')
      const resp = await _http.post('/auth/token/refresh', { refresh_token: this.refreshToken })
      this._persist(resp.data)
      return resp.data
    },

    // ─── helpers ────────────────────────────────────────────────────────
    _persist (resp) {
      this.accessToken = resp.access_token
      this.refreshToken = resp.refresh_token
      this.user = resp.user
      localStorage.setItem(ACCESS_KEY, resp.access_token)
      localStorage.setItem(REFRESH_KEY, resp.refresh_token)
      localStorage.setItem(USER_KEY, JSON.stringify(resp.user))
    },

    _clear () {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem(ACCESS_KEY)
      localStorage.removeItem(REFRESH_KEY)
      localStorage.removeItem(USER_KEY)
    },
  },
})
