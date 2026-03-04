// ================================================================
// 安全情报分析智能体 — 前端路由配置
// 版本：v1.0
// 作者：alex (unix_sec@163.com)
// ================================================================

import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/views/LayoutView.vue'),
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '系统概览', icon: 'DataBoard' },
      },
      {
        path: 'sources',
        name: 'Sources',
        component: () => import('@/views/SourcesView.vue'),
        meta: { title: '情报源管理', icon: 'Connection' },
      },
      {
        path: 'keywords',
        name: 'Keywords',
        component: () => import('@/views/KeywordsView.vue'),
        meta: { title: '关键词管理', icon: 'Search' },
      },
      {
        path: 'intel',
        name: 'Intel',
        component: () => import('@/views/IntelView.vue'),
        meta: { title: '情报列表', icon: 'Document' },
      },
      {
        path: 'reports',
        name: 'Reports',
        component: () => import('@/views/ReportsView.vue'),
        meta: { title: '报告管理', icon: 'Memo' },
      },
      {
        path: 'config',
        name: 'Config',
        component: () => import('@/views/ConfigView.vue'),
        meta: { title: '系统配置', icon: 'Setting' },
      },
      {
        path: 'audit',
        name: 'Audit',
        component: () => import('@/views/AuditView.vue'),
        meta: { title: '审计日志', icon: 'Tickets' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} — 安全情报智能体`
    : '安全情报智能体管理控制台'
})

export default router
