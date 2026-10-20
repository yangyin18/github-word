<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { translateApi, type HistoryRecord } from '../api'
import { auth, login } from '../stores/auth'

const records = ref<HistoryRecord[]>([])
const loading = ref(true)
const unauthorized = ref(false)
const error = ref('')
const expandedId = ref<number | null>(null)

const statusText: Record<string, string> = {
  completed: '已完成',
  partial: '部分失败',
}

const typeText: Record<string, string> = {
  file: '文件',
  text: '文本',
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function langPair(r: HistoryRecord): string {
  return `→ ${r.target_lang.toUpperCase()}`
}

async function loadHistory() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await translateApi.history(50)
    records.value = data.records
  } catch (e: any) {
    if (e.response?.status === 401) {
      unauthorized.value = true
    } else {
      error.value = e.response?.data?.detail || '加载翻译历史失败'
    }
  } finally {
    loading.value = false
  }
}

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id
}

onMounted(loadHistory)
</script>

<template>
  <div class="history-page">
    <h2>翻译历史</h2>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="unauthorized" class="empty">
      <p>查看翻译历史需要先登录 GitHub 账号</p>
      <button class="btn-primary" @click="login">GitHub 登录</button>
    </div>

    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else-if="records.length === 0" class="empty">暂无翻译记录</div>

    <table v-else class="history-table">
      <thead>
        <tr>
          <th>时间</th>
          <th>类型</th>
          <th>目标语言</th>
          <th>状态</th>
          <th>分段</th>
          <th>耗时</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="r in records" :key="r.id">
          <tr class="row" :class="{ expanded: expandedId === r.id }" @click="toggleExpand(r.id)">
            <td>{{ formatTime(r.created_at) }}</td>
            <td>{{ typeText[r.source_type] || r.source_type }}</td>
            <td>{{ langPair(r) }}</td>
            <td>
              <span class="status" :class="r.status">{{ statusText[r.status] || r.status }}</span>
            </td>
            <td>{{ r.failed_count > 0 ? `${r.segment_count - r.failed_count}/${r.segment_count}` : r.segment_count }}</td>
            <td>{{ formatElapsed(r.elapsed_ms) }}</td>
          </tr>
          <tr v-if="expandedId === r.id" class="detail-row">
            <td colspan="6">
              <a v-if="r.resource_url" :href="r.resource_url" target="_blank" class="source-link">
                {{ r.resource_url }}
              </a>
              <div class="preview-block">
                <div class="preview-title">原文预览</div>
                <pre class="preview">{{ r.source_preview || '（空）' }}</pre>
              </div>
              <div class="preview-block">
                <div class="preview-title">译文预览</div>
                <pre class="preview">{{ r.translated_preview || '（空）' }}</pre>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.history-page { max-width: 900px; }
.loading, .empty { color: #8b949e; padding: 24px 0; text-align: center; }
.error { color: #f85149; padding: 16px 0; }
.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 10px;
  overflow: hidden;
}
.history-table th, .history-table td {
  padding: 10px 14px;
  border-bottom: 1px solid #30363d;
  text-align: left;
}
.history-table tbody tr:last-child td { border-bottom: none; }
.history-table th { color: #8b949e; font-weight: 600; }
.row { cursor: pointer; }
.row:hover { background: #1c2129; }
.row.expanded { background: #1c2129; }
.detail-row td { background: #161b22; }
.status.completed { color: #3fb950; }
.status.partial { color: #d29922; }
.source-link {
  display: inline-block;
  margin-bottom: 12px;
  color: #58a6ff;
  word-break: break-all;
}
.preview-block { margin-bottom: 12px; }
.preview-title { font-weight: 600; margin-bottom: 4px; font-size: 13px; color: #8b949e; }
.preview {
  margin: 0;
  padding: 8px 12px;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  color: #e6edf3;
}
.btn-primary {
  padding: 8px 16px;
  background: #238636;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.btn-primary:hover { background: #2ea043; }
</style>
