/* FE-2: jsdom-based unit tests for Pinia stores + composables. */
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/__tests__/**/*.test.{js,vue}'],
    setupFiles: ['src/__tests__/setup.js'],
  },
})
