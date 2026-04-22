import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' },
      },
      {
        path: 'intelligence',
        name: 'Intelligence',
        component: () => import('../views/Intelligence.vue'),
        meta: { title: '情报中心', icon: 'DocumentCopy' },
      },
      {
        path: 'intelligence/:id',
        name: 'IntelligenceDetail',
        component: () => import('../views/IntelligenceDetail.vue'),
        meta: { title: '情报详情', hidden: true },
      },
      {
        path: 'sources',
        name: 'Sources',
        component: () => import('../views/Sources.vue'),
        meta: { title: '情报源管理', icon: 'Connection' },
      },
      {
        path: 'reports',
        name: 'Reports',
        component: () => import('../views/Reports.vue'),
        meta: { title: '报告管理', icon: 'DataAnalysis' },
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('../views/System.vue'),
        meta: { title: '系统管理', icon: 'Setting' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'SIA'} - Security Intelligence Agent`
  next()
})

export default router
