import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { title: 'nav.dashboard', icon: 'Odometer' },
      },
      {
        path: 'intelligence',
        name: 'Intelligence',
        component: () => import('../views/Intelligence.vue'),
        meta: { title: 'nav.intelligence', icon: 'DocumentCopy' },
      },
      {
        path: 'intelligence/:id',
        name: 'IntelligenceDetail',
        component: () => import('../views/IntelligenceDetail.vue'),
        meta: { title: 'nav.intelDetail', hidden: true },
      },
      {
        path: 'sources',
        name: 'Sources',
        component: () => import('../views/Sources.vue'),
        meta: { title: 'nav.sources', icon: 'Connection', requireRole: 'analyst' },
      },
      {
        path: 'reports',
        name: 'Reports',
        component: () => import('../views/Reports.vue'),
        meta: { title: 'nav.reports', icon: 'DataAnalysis' },
      },
      {
        path: 'admin/users',
        name: 'Users',
        component: () => import('../views/Users.vue'),
        meta: { title: 'nav.users', icon: 'User', requireRole: 'admin' },
      },
      {
        path: 'admin/api-keys',
        name: 'ApiKeys',
        component: () => import('../views/ApiKeys.vue'),
        meta: { title: 'nav.apiKeys', icon: 'Key', requireRole: 'admin' },
      },
      {
        path: 'admin/audit',
        name: 'AuditLog',
        component: () => import('../views/AuditLog.vue'),
        meta: { title: 'nav.audit', icon: 'Document', requireRole: 'admin' },
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('../views/System.vue'),
        meta: { title: 'nav.system', icon: 'Setting', requireRole: 'admin' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const ROLE_LEVEL = { admin: 30, analyst: 20, viewer: 10 }

router.beforeEach((to) => {
  document.title = `${to.meta.title || 'SIA'} - Security Intelligence Agent`

  // Public routes (login) bypass the guard.
  if (to.meta.public) return true

  const auth = useAuthStore()
  if (!auth.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // Optional per-route role check.
  if (to.meta.requireRole) {
    const have = ROLE_LEVEL[auth.role] || 0
    const need = ROLE_LEVEL[to.meta.requireRole] || 0
    if (have < need) {
      return { path: '/', query: { denied: to.fullPath } }
    }
  }
  return true
})

export default router
