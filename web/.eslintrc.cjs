/* FE-2: minimal Vue 3 lint baseline.
 *
 * vue3-recommended catches the high-value issues (unused vars, missing keys,
 * mismatched refs) without forcing a heavy style guide on a small codebase.
 * Tighten later by switching to ``vue3-strongly-recommended`` once the
 * existing views are clean.
 */
module.exports = {
  root: true,
  env: {
    browser: true,
    node: true,
    es2022: true,
  },
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  extends: [
    'plugin:vue/vue3-recommended',
    'eslint:recommended',
  ],
  rules: {
    // Allow unused params prefixed with _.
    'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    // Vue's recommended formatter wants self-closing components; we don't enforce.
    'vue/html-self-closing': 'off',
    // Multi-word component names are not always practical (Login.vue, Reports.vue, ...).
    'vue/multi-word-component-names': 'off',
    // Element Plus uses kebab-case + PascalCase interchangeably; allow both.
    'vue/component-name-in-template-casing': 'off',
  },
  ignorePatterns: ['dist/', 'node_modules/', '*.config.js'],
}
