/* Vitest global setup: fresh Pinia per test, mocked localStorage. */
import { beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

beforeEach(() => {
  setActivePinia(createPinia())
  // jsdom provides localStorage; clear between tests so state doesn't leak.
  if (typeof localStorage !== 'undefined') {
    localStorage.clear()
  }
})
