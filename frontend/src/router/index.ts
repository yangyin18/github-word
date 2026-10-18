import { createRouter, createWebHistory } from 'vue-router'
import TaskSubmit from '../views/TaskSubmit.vue'
import TaskDetail from '../views/TaskDetail.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'submit', component: TaskSubmit },
    { path: '/task/:id', name: 'detail', component: TaskDetail, props: true },
  ],
})

export default router
