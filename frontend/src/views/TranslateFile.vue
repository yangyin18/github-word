<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { reposApi, translateApi, prApi, languagesApi, type Language } from '../api'

const route = useRoute()
const router = useRouter()
const owner = computed(() => route.params.owner as string)
const repo = computed(() => route.params.name as string)
const filePath = computed(() => route.params.path as string)

const sourceContent = ref('')
const translated = ref('')
const targetLang = ref('zh')
const sourceLang = ref('auto')
const languages = ref<Language[]>([])
const loadingFile = ref(true)
const translating = ref(false)
const submitting = ref(false)
const error = ref('')
const prUrl = ref('')

// 进度条特效状态
const progress = ref(0)
const elapsed = ref(0)
let progressTimer: number | null = null

const STAGES = [
  { at: 0, text: '📖 正在解析文档结构...' },
  { at: 12, text: '✂️ 正在切分翻译段落...' },
  { at: 25, text: '🤖 AI 正在逐段翻译（免费模型较慢，请耐心等待）...' },
  { at: 60, text: '✍️ 正在润色译文...' },
  { at: 85, text: '🧩 正在组装译文...' },
  { at: 96, text: '⏳ 即将完成，马上就好...' },
]
const stageText = computed(() => {
  const s = STAGES.filter(x => progress.value >= x.at)
  return s.length ? s[s.length - 1].text : STAGES[0].text
})

function startProgress() {
  progress.value = 0
  elapsed.value = 0
  progressTimer = window.setInterval(() => {
    elapsed.value += 0.2
    // 渐近式增长：越接近 95% 越慢，配合微小线性推进保持动感
    progress.value = Math.min(95, progress.value + (95 - progress.value) * 0.006 + 0.12)
  }, 200)
}

function stopProgress(success: boolean) {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  progress.value = success ? 100 : 0
  if (success) {
    setTimeout(() => { progress.value = 0 }, 1200)
  }
}

onMounted(async () => {
  // 加载语言列表
  try {
    const { data } = await languagesApi.list()
    languages.value = data.target_languages
  } catch {}
  loadFile()
})

async function loadFile() {
  loadingFile.value = true
  error.value = ''
  try {
    const { data } = await reposApi.contents(owner.value, repo.value, filePath.value)
    if (data.type === 'file' && data.content != null) {
      sourceContent.value = data.content
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载文件失败'
  } finally {
    loadingFile.value = false
  }
}

async function doTranslate() {
  translating.value = true
  error.value = ''
  startProgress()
  try {
    const { data } = await translateApi.text(
      sourceContent.value,
      targetLang.value,
      sourceLang.value,
      `https://github.com/${owner.value}/${repo.value}/${filePath.value}`,
    )
    translated.value = data.translated
    stopProgress(true)
  } catch (e: any) {
    stopProgress(false)
    error.value = e.response?.data?.detail || '翻译失败'
  } finally {
    translating.value = false
  }
}

async function submitPR() {
  submitting.value = true
  error.value = ''
  try {
    const { data } = await prApi.create({
      repo: `${owner.value}/${repo.value}`,
      path: filePath.value,
      content: translated.value,
      target_lang: targetLang.value,
    })
    prUrl.value = data.pr_url
  } catch (e: any) {
    error.value = e.response?.data?.detail || '提交 PR 失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="translate-page">
    <div class="header">
      <button class="btn-link" @click="router.back()">← 返回</button>
      <h2>{{ filePath }}</h2>
    </div>

    <p v-if="loadingFile" class="hint">加载文件中...</p>
    <p v-else-if="error && !sourceContent" class="error">{{ error }}</p>

    <template v-else>
      <div class="lang-bar">
        <label>目标语言：
          <select v-model="targetLang">
            <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
          </select>
        </label>
        <button class="btn-primary" :disabled="translating" @click="doTranslate">
          {{ translating ? '翻译中...' : '翻译' }}
        </button>
      </div>

      <!-- 翻译进度条特效 -->
      <div v-if="translating" class="progress-panel">
        <div class="progress-head">
          <span class="stage-text">{{ stageText }}</span>
          <span class="progress-meta">{{ Math.floor(progress) }}% · 已用 {{ Math.floor(elapsed) }}s</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progress + '%' }"></div>
          <div class="progress-shine"></div>
        </div>
      </div>

      <div class="compare">
        <div class="col">
          <h3>原文</h3>
          <textarea v-model="sourceContent" rows="20" readonly></textarea>
        </div>
        <div class="col">
          <h3>译文（可编辑）</h3>
          <textarea v-model="translated" rows="20" placeholder="点击「翻译」生成译文"></textarea>
        </div>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div v-if="prUrl" class="pr-success">
        <p>✅ PR 已创建！</p>
        <a :href="prUrl" target="_blank" class="btn-primary">在 GitHub 查看 PR</a>
      </div>

      <div v-else class="actions">
        <button class="btn-primary" :disabled="!translated || submitting" @click="submitPR">
          {{ submitting ? '提交中...' : '一键提交 PR' }}
        </button>
        <p class="tip">将创建新分支，译文以新文件（如 README.zh.md）提交，不覆盖原文</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.translate-page { max-width: 1200px; margin: 0 auto; }
.header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.lang-bar { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.lang-bar select { padding: 6px 10px; border-radius: 6px; border: 1px solid #d0d7de; }
.compare { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.col h3 { margin-bottom: 8px; font-size: 14px; color: #57606a; }
textarea { width: 100%; padding: 12px; border: 1px solid #d0d7de; border-radius: 8px; font-family: monospace; font-size: 13px; resize: vertical; box-sizing: border-box; }
.actions { margin-top: 20px; text-align: center; }
.tip { color: #8c959f; font-size: 13px; margin-top: 8px; }

/* 进度条特效 */
.progress-panel { margin-bottom: 16px; padding: 14px 16px; background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 10px; }
.progress-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.stage-text { font-size: 14px; font-weight: 600; color: #1f2328; animation: stage-fade .4s ease; }
.progress-meta { font-size: 13px; color: #57606a; font-variant-numeric: tabular-nums; }
.progress-track { position: relative; height: 12px; background: #d8dee4; border-radius: 999px; overflow: hidden; }
.progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #218bff, #8957e5, #218bff);
  background-size: 200% 100%;
  animation: bar-flow 2s linear infinite;
  transition: width .25s ease-out;
}
.progress-shine {
  position: absolute; inset: 0;
  background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,.55) 50%, transparent 60%);
  transform: translateX(-100%);
  animation: shine 1.6s ease-in-out infinite;
}
@keyframes bar-flow { 0% { background-position: 0% 0; } 100% { background-position: 200% 0; } }
@keyframes shine { to { transform: translateX(100%); } }
@keyframes stage-fade { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: none; } }
.pr-success { margin-top: 20px; padding: 20px; background: #dafbe1; border-radius: 8px; text-align: center; }
.pr-success p { font-weight: 600; margin-bottom: 12px; }
</style>
