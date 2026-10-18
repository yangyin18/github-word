<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { tasksApi, type TaskResponse, type Segment } from '../api'

const route = useRoute()
const taskId = route.params.id as string

const task = ref<TaskResponse | null>(null)
const segments = ref<Segment[]>([])
const translatedMd = ref('')
const loading = ref(true)
const error = ref('')
const showComparison = ref(true)
let timer: any = null

const isFinished = computed(() =>
  task.value ? ['completed', 'partial_failed', 'failed'].includes(task.value.status) : false
)

const statusText: Record<string, string> = {
  created: '已创建',
  fetching: '抓取中',
  fetched: '已抓取',
  parsing: '解析中',
  translating: '翻译中',
  completed: '已完成',
  partial_failed: '部分失败',
  failed: '失败',
}

async function loadTask() {
  try {
    const { data } = await tasksApi.get(taskId)
    task.value = data
    if (isFinished.value) {
      const [segRes, resultRes] = await Promise.all([
        tasksApi.segments(taskId),
        tasksApi.result(taskId),
      ])
      segments.value = segRes.data.segments
      translatedMd.value = resultRes.data.translated_markdown
      stopPolling()
    }
  } catch (e: any) {
    error.value = e.response?.data?.message || '加载任务失败'
  } finally {
    loading.value = false
  }
}

function startPolling() {
  timer = setInterval(loadTask, 1500)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(() => {
  loadTask()
  startPolling()
})

onUnmounted(stopPolling)

async function retryFailed() {
  try {
    await tasksApi.retry(taskId)
    loadTask()
    startPolling()
  } catch (e: any) {
    error.value = '重试失败'
  }
}

async function editSegment(seg: Segment) {
  const text = prompt('修正译文：', seg.translated_text || seg.source_text)
  if (text !== null) {
    try {
      await tasksApi.updateSegment(taskId, seg.segment_id, text)
      loadTask()
    } catch (e) {
      error.value = '保存失败'
    }
  }
}
</script>

<template>
  <div class="detail-page">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else-if="task" class="task-info">
      <h2>任务详情</h2>
      <div class="meta">
        <span class="status" :class="task.status">{{ statusText[task.status] || task.status }}</span>
        <span>{{ task.resource_type }}</span>
        <a :href="task.resource_url" target="_blank">查看源资源</a>
      </div>
      <div class="stats">
        分段 {{ task.total_segments }} · 已译 {{ task.translated_segments }} · 失败 {{ task.failed_segments }}
      </div>
      <p v-if="task.error_message" class="error">{{ task.error_message }}</p>
    </div>

    <div v-if="task && isFinished" class="actions">
      <button class="btn-toggle" @click="showComparison = !showComparison">
        {{ showComparison ? '查看纯译文' : '查看对照' }}
      </button>
      <button v-if="task.failed_segments > 0" class="btn-retry" @click="retryFailed">
        重试失败分段
      </button>
    </div>

    <!-- 对照视图 -->
    <div v-if="task && isFinished && showComparison" class="comparison">
      <h3>原文 - 译文对照</h3>
      <div v-for="seg in segments" :key="seg.segment_id" class="seg-row" :class="seg.segment_type">
        <div class="seg-source">{{ seg.source_text }}</div>
        <div class="seg-arrow">→</div>
        <div class="seg-target">
          <template v-if="seg.translatable">
            <span v-if="seg.translated_text">{{ seg.translated_text }}</span>
            <span v-else class="muted">（翻译失败）</span>
            <button v-if="seg.translatable" class="btn-edit" @click="editSegment(seg)">修正</button>
          </template>
          <template v-else>
            <span class="code-tag">[{{ seg.segment_type }}]</span>
          </template>
        </div>
      </div>
    </div>

    <!-- 纯译文视图 -->
    <div v-if="task && isFinished && !showComparison" class="result-md">
      <h3>译文</h3>
      <pre>{{ translatedMd }}</pre>
    </div>
  </div>
</template>
