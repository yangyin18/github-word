<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { languagesApi, tasksApi, type Language } from '../api'

const router = useRouter()
const sourceLangs = ref<Language[]>([])
const targetLangs = ref<Language[]>([])
const resourceUrl = ref('')
const sourceLang = ref('auto')
const targetLang = ref('zh')
const loading = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const { data } = await languagesApi.list()
    sourceLangs.value = data.source_languages
    targetLangs.value = data.target_languages
  } catch (e) {
    error.value = '加载语言列表失败'
  }
})

async function submit() {
  error.value = ''
  if (!resourceUrl.value.trim()) {
    error.value = '请输入 GitHub 资源 URL'
    return
  }
  loading.value = true
  try {
    const { data } = await tasksApi.create({
      resource_url: resourceUrl.value.trim(),
      target_lang: targetLang.value,
      source_lang: sourceLang.value,
    })
    router.push({ name: 'detail', params: { id: data.task_id } })
  } catch (e: any) {
    error.value = e.response?.data?.message || '创建任务失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="submit-page">
    <div class="card">
      <h2>提交翻译任务</h2>
      <p class="hint">支持公开的 Issue / Pull Request / 仓库 README</p>

      <div class="form-group">
        <label>GitHub 资源 URL</label>
        <input
          v-model="resourceUrl"
          type="text"
          placeholder="https://github.com/owner/repo/issues/123"
        />
      </div>

      <div class="form-row">
        <div class="form-group">
          <label>源语言</label>
          <select v-model="sourceLang">
            <option v-for="l in sourceLangs" :key="l.code" :value="l.code">{{ l.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>目标语言</label>
          <select v-model="targetLang">
            <option v-for="l in targetLangs" :key="l.code" :value="l.code">{{ l.name }}</option>
          </select>
        </div>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="btn-primary" :disabled="loading" @click="submit">
        {{ loading ? '提交中...' : '开始翻译' }}
      </button>
    </div>
  </div>
</template>
