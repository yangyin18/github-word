import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import TaskSubmit from '../views/TaskSubmit.vue'
import TaskDetail from '../views/TaskDetail.vue'
import RepoFileBrowser from '../views/RepoFileBrowser.vue'
import TranslateFile from '../views/TranslateFile.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/submit', name: 'submit', component: TaskSubmit },
    { path: '/task/:id', name: 'detail', component: TaskDetail, props: true },
    { path: '/repo/:owner/:name', name: 'repo', component: RepoFileBrowser, props: true },
    { path: '/repo/:owner/:name/translate/:path(.*)', name: 'translate-file', component: TranslateFile, props: true },
  ],
})

export default router
