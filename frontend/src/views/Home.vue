<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { reposApi, type Repo } from '../api'
import { auth, ensureMe, login } from '../stores/auth'

const router = useRouter()
const repos = ref<Repo[]>([])
const loading = ref(false)
const error = ref('')
const activeTab = ref<'repos' | 'manual'>('repos')

onMounted(async () => {
  await ensureMe()
  if (auth.user) loadRepos()
})

async function loadRepos() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await reposApi.list()
    repos.value = data.repos
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载仓库失败'
  } finally {
    loading.value = false
  }
}

function openRepo(repo: Repo) {
  const [owner, name] = repo.full_name.split('/')
  router.push({ name: 'repo', params: { owner, name } })
}

function goManual() {
  activeTab.value = 'manual'
}
</script>

<template>
  <div class="home-page">
    <!-- 未登录：显示登录引导（退出/登录按钮在全局头部） -->
    <div v-if="!auth.user" class="login-box">
      <h2>登录 GitHub 账号</h2>
      <p class="hint">登录后可选择仓库文档，一键翻译并提交 PR</p>
      <button class="btn-primary btn-github" @click="login">
        <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
        </svg>
        用 GitHub 登录
      </button>
      <p class="tip">首次使用会请求仓库读写权限</p>
      <p class="tip">网页翻译与一键提 PR 无需安装 GitHub App；仅「PR 评论自动翻译」需要仓库安装本应用</p>
      <button class="btn-link" @click="goManual">没有账号？用 URL 手动翻译</button>
    </div>

    <!-- 已登录 -->
    <div v-else>
      <div class="tab-bar">
        <button class="btn-link" :class="{ active: activeTab === 'repos' }" @click="activeTab = 'repos'">我的仓库</button>
        <button class="btn-link" :class="{ active: activeTab === 'manual' }" @click="activeTab = 'manual'">URL 翻译</button>
      </div>

      <!-- 仓库列表 -->
      <div v-if="activeTab === 'repos'">
        <p v-if="loading" class="hint">加载仓库中...</p>
        <p v-else-if="error" class="error">{{ error }}</p>
        <div v-else class="repo-grid">
          <div
            v-for="repo in repos"
            :key="repo.id"
            class="repo-card"
            @click="openRepo(repo)"
          >
            <div class="repo-name">{{ repo.name }}</div>
            <div class="repo-desc">{{ repo.description || '无描述' }}</div>
            <div class="repo-meta">
              <span class="badge" :class="{ private: repo.private }">
                {{ repo.private ? '私有' : '公开' }}
              </span>
              <span v-if="repo.language" class="lang">{{ repo.language }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- URL 手动翻译 -->
      <div v-if="activeTab === 'manual'">
        <p class="hint">粘贴 GitHub Issue / PR / README 链接进行翻译</p>
        <button class="btn-primary" @click="router.push({ name: 'submit' })">前往手动翻译</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-page { max-width: 960px; margin: 0 auto; }
.login-box { text-align: center; padding: 60px 20px; }
.login-box h2 { margin-bottom: 8px; }
.btn-github { display: inline-flex; align-items: center; gap: 8px; }
.tip { color: #888; font-size: 13px; margin: 16px 0 8px; }
.tab-bar { display: flex; gap: 8px; margin-bottom: 24px; }
.btn-link { background: none; border: none; color: #0969da; cursor: pointer; padding: 4px 8px; }
.btn-link.active { font-weight: 600; }
.repo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.repo-card { border: 1px solid #d0d7de; border-radius: 8px; padding: 16px; cursor: pointer; transition: border-color .2s; }
.repo-card:hover { border-color: #0969da; }
.repo-name { font-weight: 600; margin-bottom: 6px; }
.repo-desc { color: #57606a; font-size: 13px; margin-bottom: 10px; min-height: 36px; }
.repo-meta { display: flex; gap: 8px; align-items: center; }
.badge { font-size: 12px; padding: 2px 8px; border-radius: 10px; background: #ddf4ff; color: #0969da; }
.badge.private { background: #fff8c5; color: #9a6700; }
.lang { font-size: 12px; color: #57606a; }
</style>
