<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app">
    <header class="app-header">
      <h1>GitHub 翻译工具</h1>
      <p class="subtitle">自动翻译 GitHub 公开文档，保留代码与格式结构</p>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
