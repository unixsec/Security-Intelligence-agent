/**
 * Vue i18n setup (v0.4-4).
 *
 * Default locale follows the browser, falling back to ``zh-CN``.
 * Persisted across reloads via ``localStorage['sia_locale']`` so a user's
 * choice sticks even when they're not logged in.
 *
 * Usage:
 *
 *   <script setup>
 *     import { useI18n } from 'vue-i18n'
 *     const { t } = useI18n()
 *   </script>
 *   <template>
 *     <h1>{{ t('dashboard.title') }}</h1>
 *   </template>
 */
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.js'
import en from './locales/en.js'

const STORAGE_KEY = 'sia_locale'

function _detectLocale () {
  const saved = typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY)
  if (saved) return saved
  if (typeof navigator === 'undefined') return 'zh-CN'
  const lang = (navigator.language || 'zh-CN').toLowerCase()
  if (lang.startsWith('zh')) return 'zh-CN'
  if (lang.startsWith('en')) return 'en'
  return 'zh-CN'
}

const i18n = createI18n({
  legacy: false,                 // composition API
  locale: _detectLocale(),
  fallbackLocale: 'en',
  globalInjection: true,
  messages: { 'zh-CN': zhCN, en },
})

export function setLocale (loc) {
  i18n.global.locale.value = loc
  if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, loc)
}

export const SUPPORTED_LOCALES = [
  { code: 'zh-CN', label: '中文' },
  { code: 'en', label: 'English' },
]

export default i18n
