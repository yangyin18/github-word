<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { reposApi, translateApi, prApi, languagesApi, type RepoItem, type Language } from '../api'

const route = useRoute()
const router = useRouter()
const owner = computed(() => route.params.owner as string)
const repo = computed(() => route.params.name as string)
const path = ref('')
const items = ref<RepoItem[]>([])
const loading = ref(false)
const error = ref('')

// ===== 多文件批量翻译 =====
interface BatchFileState {
  path: string
  name: string
  status: 'pending' | 'translating' | 'done' | 'failed'
  translated: string
  error: string
  submitting: boolean
  prUrl: string
}
const selected = ref<Set<string>>(new Set())
const languages = ref<Language[]>([])
const targetLang = ref('zh')
const batchRunning = ref(false)
const batchFiles = ref<BatchFileState[]>([])

const markdownFiles = computed(() => items.value.filter(isMarkdown))
const selectedFiles = computed(() => markdownFiles.value.filter(f => selected.value.has(f.path)))
const allSelected = computed(
  () => markdownFiles.value.length > 0 && selectedFiles.value.length === markdownFiles.value.length,
)
const batchProgress = computed(() => ({
  total: batchFiles.value.length,
  done: batchFiles.value.filter(f => f.status === 'done' || f.status === 'failed').length,
}))

const BATCH_LABELS: Record<BatchFileState['status'], string> = {
  pending: '待翻译',
  translating: '翻译中',
  done: '已翻译',
  failed: '失败',
}
const BATCH_ICONS: Record<BatchFileState['status'], string> = {
  pending: '⏳',
  translating: '🔄',
  done: '✅',
  failed: '❌',
}

onMounted(async () => {
  loadContents('')
  try {
    const { data } = await languagesApi.list()
    languages.value = data.target_languages
  } catch {}
})

async function loadContents(p: string) {
  path.value = p
  selected.value = new Set() // 切换目录清空选择
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

function onRowClick(item: RepoItem) {
  // 批量翻译进行中禁止跳转，避免中断任务
  if (batchRunning.value) return
  if (item.type === 'dir' || isMarkdown(item)) loadContents(item.path)
}

function toggleSelect(item: RepoItem) {
  if (batchRunning.value) return
  const s = new Set(selected.value)
  if (s.has(item.path)) s.delete(item.path)
  else s.add(item.path)
  selected.value = s
}

function toggleSelectAll() {
  if (batchRunning.value) return
  selected.value = allSelected.value
    ? new Set()
    : new Set(markdownFiles.value.map(f => f.path))
}

async function startBatch() {
  if (!selectedFiles.value.length || batchRunning.value) return
  batchRunning.value = true
  error.value = ''
  batchFiles.value = selectedFiles.value.map(f => ({
    path: f.path,
    name: f.name,
    status: 'pending' as const,
    translated: '',
    error: '',
    submitting: false,
    prUrl: '',
  }))
  // 串行逐个翻译，避免并发请求打爆翻译服务（LLM 免费模型有速率限制）
  for (const bf of batchFiles.value) {
    bf.status = 'translating'
    try {
      const { data } = await reposApi.contents(owner.value, repo.value, bf.path)
      const content = data.type === 'file' ? (data.content ?? '') : ''
      const { data: res } = await translateApi.text(
        content,
        targetLang.value,
        'auto',
        `https://github.com/${owner.value}/${repo.value}/${bf.path}`,
      )
      bf.translated = res.translated
      bf.status = 'done'
    } catch (e: any) {
      bf.error = e.response?.data?.detail || '翻译失败'
      bf.status = 'failed'
    }
  }
  batchRunning.value = false
}

async function submitPrFor(bf: BatchFileState) {
  bf.submitting = true
  bf.error = ''
  try {
    const { data } = await prApi.create({
      repo: `${owner.value}/${repo.value}`,
      path: bf.path,
      content: bf.translated,
      target_lang: targetLang.value,
    })
    bf.prUrl = data.pr_url
  } catch (e: any) {
    bf.error = e.response?.data?.detail || '提交 PR 失败'
  } finally {
    bf.submitting = false
  }
}

function batchStatusOf(itemPath: string): BatchFileState['status'] | '' {
  const bf = batchFiles.value.find(f => f.path === itemPath)
  return bf ? bf.status : ''
}

function goToCrumb(idx: number) {
  if (batchRunning.value) return
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
      <span class="crumb" @click="!batchRunning && loadContents('')">根目录</span>
      <template v-for="(c, i) in breadcrumb" :key="i">
        <span class="sep">/</span>
        <span class="crumb" @click="goToCrumb(i)">{{ c }}</span>
      </template>
    </div>

    <!-- 批量翻译工具栏 -->
    <div v-if="markdownFiles.length" class="batch-bar">
      <label class="check-label">
        <input
          type="checkbox"
          :checked="allSelected"
          :disabled="batchRunning"
          @change="toggleSelectAll"
        />
        全选（{{ markdownFiles.length }} 个文档）
      </label>
      <label class="lang-label">
        目标语言：
        <select v-model="targetLang" :disabled="batchRunning">
          <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
        </select>
      </label>
      <button
        class="btn-primary"
        :disabled="!selectedFiles.length || batchRunning"
        @click="startBatch"
      >
        {{ batchRunning ? `翻译中 ${batchProgress.done}/${batchProgress.total}...` : `翻译所选（${selectedFiles.length}）` }}
      </button>
    </div>

    <p v-if="loading" class="hint">加载中...</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <div v-else class="file-list">
      <div
        v-for="item in items"
        :key="item.path"
        class="file-item"
        :class="{ clickable: (item.type === 'dir' || isMarkdown(item)) && !batchRunning }"
        @click="onRowClick(item)"
      >
        <input
          v-if="isMarkdown(item)"
          type="checkbox"
          class="row-check"
          :checked="selected.has(item.path)"
          :disabled="batchRunning"
          @click.stop
          @change="toggleSelect(item)"
        />
        <span class="icon">{{ item.type === 'dir' ? '📁' : '📄' }}</span>
        <span class="name">
          {{ item.name }}
          <span
            v-if="batchStatusOf(item.path)"
            class="badge"
            :class="batchStatusOf(item.path)"
          >{{ BATCH_LABELS[batchStatusOf(item.path) as BatchFileState['status']] }}</span>
        </span>
        <span v-if="item.type === 'file'" class="size">{{ (item.size / 1024).toFixed(1) }} KB</span>
      </div>
      <p v-if="!items.length" class="hint">此目录为空</p>
    </div>

    <!-- 批量翻译结果 -->
    <div v-if="batchFiles.length" class="batch-results">
      <h3>批量翻译结果</h3>
      <div v-for="bf in batchFiles" :key="bf.path" class="batch-row">
        <span class="bicon">{{ BATCH_ICONS[bf.status] }}</span>
        <span class="bname">{{ bf.name }}</span>
        <span v-if="bf.status === 'pending'" class="bstatus hint">排队中</span>
        <span v-else-if="bf.status === 'translating'" class="bstatus hint">翻译中...</span>
        <span v-else-if="bf.status === 'failed'" class="bstatus error">{{ bf.error }}</span>
        <template v-else>
          <a v-if="bf.prUrl" :href="bf.prUrl" target="_blank" class="pr-link">在 GitHub 查看 PR</a>
          <button
            v-else
            class="btn-primary btn-small"
            :disabled="bf.submitting"
            @click="submitPrFor(bf)"
          >
            {{ bf.submitting ? '提交中...' : '提交 PR' }}
          </button>
        </template>
      </div>
    </div>

    <p class="tip">提示：点击 .md / .txt 文件进入单文件翻译；勾选多个文件可一次性批量翻译，切换目录会清空选择</p>
  </div>
</template>

<style scoped>
.file-browser { max-width: 800px; margin: 0 auto; }
.header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.breadcrumb { margin-bottom: 16px; color: #57606a; font-size: 14px; }
.crumb { cursor: pointer; color: #0969da; }
.crumb:hover { text-decoration: underline; }
.sep { margin: 0 4px; color: #8c959f; }

.batch-bar {
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  padding: 10px 16px; margin-bottom: 12px;
  background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px;
}
.check-label, .lang-label { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #1f2328; }
.lang-label select { padding: 4px 8px; border-radius: 6px; border: 1px solid #d0d7de; }
.btn-primary {
  padding: 6px 14px; border: none; border-radius: 6px; cursor: pointer;
  background: #1f883d; color: #fff; font-size: 14px;
}
.btn-primary:disabled { background: #94d3a2; cursor: not-allowed; }
.btn-small { padding: 4px 10px; font-size: 13px; }

.file-list { border: 1px solid #d0d7de; border-radius: 8px; overflow: hidden; }
.file-item { display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-bottom: 1px solid #d0d7de; }
.file-item:last-child { border-bottom: none; }
.file-item.clickable { cursor: pointer; }
.file-item.clickable:hover { background: #f6f8fa; }
.row-check { flex-shrink: 0; }
.icon { font-size: 16px; }
.name { flex: 1; }
.badge {
  display: inline-block; margin-left: 6px; padding: 1px 8px;
  border-radius: 999px; font-size: 12px; vertical-align: middle;
}
.badge.pending { background: #eaeef2; color: #57606a; }
.badge.translating { background: #ddf4ff; color: #0969da; }
.badge.done { background: #dafbe1; color: #1a7f37; }
.badge.failed { background: #ffebe9; color: #cf222e; }
.size { color: #8c959f; font-size: 12px; }

.batch-results { margin-top: 16px; padding: 14px 16px; border: 1px solid #d0d7de; border-radius: 8px; }
.batch-results h3 { margin: 0 0 10px; font-size: 14px; color: #57606a; }
.batch-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid #eaeef2; }
.batch-row:last-child { border-bottom: none; }
.bicon { font-size: 14px; }
.bname { flex: 1; font-size: 14px; }
.bstatus { font-size: 13px; }
.pr-link { color: #0969da; font-size: 13px; text-decoration: none; }
.pr-link:hover { text-decoration: underline; }
.hint { color: #8c959f; font-size: 13px; }
.error { color: #cf222e; font-size: 13px; }
.tip { color: #8c959f; font-size: 13px; margin-top: 12px; }
</style>
