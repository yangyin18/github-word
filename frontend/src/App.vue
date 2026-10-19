<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView, useRouter } from 'vue-router'
import { RouterLink } from 'vue-router'
import { auth, ensureMe, login, logout } from './stores/auth'

const router = useRouter()

onMounted(() => {
  ensureMe()
})

async function handleLogout() {
  await logout()
  // 若停留在子页面（翻译/浏览等），退出后回到首页登录视图
  if (router.currentRoute.value.name !== 'home') {
    router.push({ name: 'home' })
  }
}
</script>

<template>
  <div class="app">
    <header class="app-header">
      <div class="header-left">
        <RouterLink to="/" class="brand">
          <h1>GitHub 翻译工具</h1>
          <p class="subtitle">自动翻译 GitHub 公开文档，保留代码与格式结构</p>
        </RouterLink>
      </div>

      <div class="header-right">
        <template v-if="auth.user">
          <img :src="auth.user.avatar_url" class="avatar" :alt="auth.user.name" />
          <span class="username">{{ auth.user.name || auth.user.login }}</span>
          <button class="btn-link" @click="handleLogout">退出</button>
        </template>
        <template v-else>
          <button class="btn-link" @click="login">登录</button>
        </template>
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e1e4e8;
}
.brand { text-decoration: none; color: inherit; }
.brand h1 { margin: 0; }
.subtitle { margin: 4px 0 0; color: #57606a; font-size: 13px; }
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.avatar { width: 32px; height: 32px; border-radius: 50%; }
.username { font-weight: 600; }
.btn-link {
  background: none;
  border: none;
  color: #0969da;
  cursor: pointer;
  padding: 4px 8px;
  font-size: 14px;
}
.btn-link:hover { text-decoration: underline; }
</style>
