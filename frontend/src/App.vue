<template>
  <router-view v-if="isPlainPage" />
  <el-container v-else class="layout-container">
    <el-aside width="220px">
      <div class="logo">Listing 文案生成工具</div>
      <el-menu :default-active="activeMenu" class="sidebar-menu" @select="handleMenuSelect">
        <el-menu-item index="/dashboard">
          <el-icon><i class="icon-dashboard" /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/shop-auth">
          <el-icon><i class="icon-shop" /></el-icon>
          <span>店铺授权</span>
        </el-menu-item>
        <el-menu-item index="/generate">
          <el-icon><i class="icon-generate" /></el-icon>
          <span>文案生成</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><i class="icon-history" /></el-icon>
          <span>历史记录</span>
        </el-menu-item>
        <el-menu-item index="/billing">
          <el-icon><i class="icon-billing" /></el-icon>
          <span>用量与计费</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><i class="icon-settings" /></el-icon>
          <span>设置</span>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/admin">
          <el-icon><i class="icon-settings" /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
      <div class="user-info" v-if="isLoggedIn">
        <el-dropdown @command="handleUserCommand">
          <span class="el-dropdown-link">
            {{ userNickname }}
            <el-icon><i class="icon-down" /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings">设置</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-aside>
    <el-container>
      <el-header>
        <div class="header-actions">
          <span v-if="isLoggedIn">
            欢迎使用 Listing 文案生成工具（{{ planLabel }} · 剩余额度 {{ quotaRemaining }}/{{ quotaTotal }}）
          </span>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isPlainPage = computed(() => route.meta.public === true)
const isLoggedIn = computed(() => authStore.isLoggedIn)
const isAdmin = computed(() => authStore.isAdmin)
const userNickname = computed(() => authStore.userNickname)
const quotaRemaining = computed(() => authStore.quotaRemaining)
const quotaTotal = computed(() => authStore.quotaTotal)
const planLabel = computed(() => {
  const map: Record<string, string> = { free: '免费版', basic: '基础版', pro: '专业版' }
  return map[authStore.plan] || authStore.plan
})
const activeMenu = computed(() => route.path)

const handleMenuSelect = (index: string) => {
  router.push(index)
}

const handleUserCommand = (command: string) => {
  if (command === 'logout') {
    authStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } else if (command === 'settings') {
    router.push('/settings')
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.el-aside {
  background-color: #f0f5ff;
  padding: 20px 0;
  border-right: 1px solid #e4e7ed;
  position: relative;
}

.logo {
  font-size: 18px;
  font-weight: bold;
  color: #2d3748;
  padding: 0 16px 20px;
  border-bottom: 1px solid #e4e7ed;
  text-align: center;
}

.sidebar-menu {
  border: none;
  padding: 10px 0;
}

.sidebar-menu .el-menu-item {
  height: 50px;
  line-height: 50px;
  margin: 5px 8px;
  border-radius: 6px;
}

.sidebar-menu .el-menu-item:hover {
  background-color: #e6f7ff;
}

.sidebar-menu .el-menu-item.is-active {
  background-color: #1890ff;
  color: #fff;
}

.sidebar-menu .el-icon {
  margin-right: 8px;
}

.el-header {
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  padding: 0 24px;
}

.header-actions {
  flex: 1;
  text-align: right;
  color: #606266;
  font-size: 13px;
}

.user-info {
  position: absolute;
  bottom: 20px;
  left: 20px;
  width: calc(100% - 40px);
}

.el-dropdown-link {
  cursor: pointer;
  color: #606266;
  display: flex;
  align-items: center;
}
</style>
