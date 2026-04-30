/* FE-2: smoke test for the auth store.
 *
 * We don't hit a real network — axios is mocked via the module factory so
 * the test stays fast and deterministic. Coverage focuses on the state
 * transitions that the router guard relies on (isAuthenticated true/false).
 */
import { describe, expect, it, vi } from 'vitest'

vi.mock('axios', () => {
  const post = vi.fn().mockImplementation((url) => {
    if (url === '/auth/login') {
      return Promise.resolve({
        data: {
          access_token: 'a-token',
          refresh_token: 'r-token',
          token_type: 'bearer',
          expires_in: 1800,
          user: { id: 1, username: 'alice', role: 'analyst', auth_provider: 'local' },
        },
      })
    }
    if (url === '/auth/logout') return Promise.resolve({ data: { status: 'logged_out' } })
    return Promise.resolve({ data: {} })
  })
  const get = vi.fn().mockResolvedValue({ data: { id: 1, username: 'alice', role: 'analyst' } })
  const create = vi.fn(() => ({ post, get }))
  return { default: { create, post, get }, create, post, get }
})

import { useAuthStore } from '../auth'

describe('auth store', () => {
  it('starts unauthenticated', () => {
    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.role).toBe('viewer')
  })

  it('becomes authenticated after login()', async () => {
    const auth = useAuthStore()
    await auth.login({ username: 'alice', password: 'p', provider: 'local' })
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.user.username).toBe('alice')
    expect(auth.role).toBe('analyst')
    expect(localStorage.getItem('sia_access_token')).toBe('a-token')
  })

  it('clears state on logout()', async () => {
    const auth = useAuthStore()
    await auth.login({ username: 'alice', password: 'p', provider: 'local' })
    await auth.logout()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.user).toBeNull()
    expect(localStorage.getItem('sia_access_token')).toBeNull()
  })
})
