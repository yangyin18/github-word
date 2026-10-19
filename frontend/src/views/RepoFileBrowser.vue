<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { reposApi, type RepoItem } from '../api'

const route = useRoute()
const router = useRouter()
const owner = computed(() => route.params.owner as string)
const repo = computed(() => route.params.name as string)
const path = ref('')
const items = ref<RepoItem[]>([])
const loading = ref(false)
const error = ref('')

const breadcrumb = computed(() => {
  if (!path.value) return []
  return path.value.split('/')
})

onMounted(() => loadContents(''))

async function loadContents(p: string) {
  path.value = p
  loading.value = true
  error.value = ''
  try {
    const { data } = await reposApi.contents(owner.value, repo.value, p)
    if (data.type === 'dir' && data.items) {
      items.value = data.items.sort((a, b) => {
        if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
        return a.name.localeCompare(b.name)
      })
    } else if (data.type === 'file') {
      // 单文件：跳到翻译页
      router.push({
        name: 'translate-file',
        params: { owner: owner.value, name: repo.value, path: data.path },
        query: { sha: data.sha, name: data.name },
      })
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

function isMarkdown(item: RepoItem) {
  return item.type === 'file' && /\.(md|markdown|txt)$/i.test(item.name)
}

function goToCrumb(idx: number) {
  const p = breadcrumb.value.slice(0, idx + 1).join('/')
  loadContents(p)
}
</script>

<template>
  <div class="file-browser">
    <div class="header">
      <button class="btn-link" @click="router.back()">← 返回</button>
      <h2>{{ owner }}/{{ repo }}</h2>
    </div>

    <div class="breadcrumb">
      <span class="crumb" @click="loadContents('')">根目录</span>
      <template v-for="(c, i) in breadcrumb" :key="i">
        <span class="sep">/</span>
        <span class="crumb" @click="goToCrumb(i)">{{ c }}</span>
      </template>
    </div>

    <p v-if="loading" class="hint">加载中...</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <div v-else class="file-list">
      <div
        v-for="item in items"
        :key="item.path"
        class="file-item"
        :class="{ clickable: item.type === 'dir' || isMarkdown(item) }"
        @click="item.type === 'dir' ? loadContents(item.path) : isMarkdown(item) && loadContents(item.path)"
      >
        <span class="icon">{{ item.type === 'dir' ? '📁' : '📄' }}</span>
        <span class="name">{{ item.name }}</span>
        <span v-if="item.type === 'file'" class="size">{{ (item.size / 1024).toFixed(1) }} KB</span>
      </div>
      <p v-if="!items.length" class="hint">此目录为空</p>
    </div>

    <p class="tip">提示：点击 .md / .txt 文件进入翻译</p>
  </div>
</template>

<style scoped>
.file-browser { max-width: 800px; margin: 0 auto; }
.header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.breadcrumb { margin-bottom: 16px; color: #57606a; font-size: 14px; }
.crumb { cursor: pointer; color: #0969da; }
.crumb:hover { text-decoration: underline; }
.sep { margin: 0 4px; color: #8c959f; }
.file-list { border: 1px solid #d0d7de; border-radius: 8px; overflow: hidden; }
.file-item { display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-bottom: 1px solid #d0d7de; }
.file-item:last-child { border-bottom: none; }
.file-item.clickable { cursor: pointer; }
.file-item.clickable:hover { background: #f6f8fa; }
.icon { font-size: 16px; }
.name { flex: 1; }
.size { color: #8c959f; font-size: 12px; }
.tip { color: #8c959f; font-size: 13px; margin-top: 12px; }
</style>
