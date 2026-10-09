import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import ShopAuth from '../views/ShopAuth.vue'
import Generate from '../views/Generate.vue'
import History from '../views/History.vue'
import Billing from '../views/Billing.vue'
import Settings from '../views/Settings.vue'
import Admin from '../views/Admin.vue'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', component: Login, meta: { public: true, title: '登录' } },
  { path: '/dashboard', component: Dashboard, meta: { title: '工作台' } },
  { path: '/shop-auth', component: ShopAuth, meta: { title: '店铺授权' } },
  { path: '/generate', component: Generate, meta: { title: '文案生成' } },
  { path: '/history', component: History, meta: { title: '历史记录' } },
  { path: '/billing', component: Billing, meta: { title: '用量与计费' } },
  { path: '/settings', component: Settings, meta: { title: '设置' } },
  { path: '/admin', component: Admin, meta: { title: '用户管理', adminOnly: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  const isPublic = to.meta.public === true

  if (isPublic) {
    // 已登录用户访问登录页，直接进工作台
    if (authStore.isLoggedIn && (await authStore.checkToken())) {
      return { path: '/dashboard' }
    }
    return true
  }

  if (!authStore.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (!authStore.user && !(await authStore.checkToken())) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 仅管理员可进入的页面
  if (to.meta.adminOnly === true && !authStore.isAdmin) {
    return { path: '/dashboard' }
  }

  return true
})

export default router
