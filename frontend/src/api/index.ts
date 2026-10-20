import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true,
})

export interface Language {
  code: string
  name: string
}

export interface TaskCreateRequest {
  resource_url: string
  target_lang: string
  source_lang?: string
}

export interface TaskCreateResponse {
  task_id: string
  status: string
  resource_type: string
}

export interface TaskResponse {
  task_id: string
  status: string
  resource_type: string
  resource_url: string
  source_lang: string
  target_lang: string
  total_segments: number
  translated_segments: number
  failed_segments: number
  translated_count: number | null
  total_count: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface Segment {
  segment_id: string
  sequence: number
  segment_type: string
  translatable: boolean
  source_text: string
  translated_text: string | null
  status: string
  error_message: string | null
}

export interface SegmentListResponse {
  segments: Segment[]
}

export interface Repo {
  id: number
  name: string
  full_name: string
  private: boolean
  default_branch: string
  description: string | null
  html_url: string
  updated_at: string
  language: string | null
}

export interface RepoItem {
  name: string
  path: string
  type: string
  size: number
}

export interface UserInfo {
  login: string
  name: string
  avatar_url: string
  html_url: string
}

export const languagesApi = {
  list: () => api.get<{ source_languages: Language[]; target_languages: Language[] }>('/languages'),
}

export const tasksApi = {
  create: (data: TaskCreateRequest) => api.post<TaskCreateResponse>('/tasks', data),
  get: (id: string) => api.get<TaskResponse>(`/tasks/${id}`),
  segments: (id: string) => api.get<SegmentListResponse>(`/tasks/${id}/segments`),
  result: (id: string) => api.get<{ translated_markdown: string }>(`/tasks/${id}/result`),
  updateSegment: (taskId: string, segId: string, translated_text: string) =>
    api.put<Segment>(`/tasks/${taskId}/segments/${segId}`, { translated_text }),
  retry: (id: string) => api.post<{ retried_count: number; status: string }>(`/tasks/${id}/retry`),
}

export const authApi = {
  me: () => api.get<{ logged_in: boolean; user: UserInfo }>('/auth/me'),
  logout: () => api.post('/auth/logout'),
}

export const reposApi = {
  list: (page = 1, perPage = 50) =>
    api.get<{ repos: Repo[] }>('/repos', { params: { page, per_page: perPage } }),
  contents: (owner: string, repo: string, path = '') =>
    api.get<{ type: string; items?: RepoItem[]; content?: string; sha?: string; name?: string; path?: string }>(
      `/repos/${owner}/${repo}/contents/${path}`,
    ),
}

export interface HistoryRecord {
  id: number
  resource_url: string | null
  source_type: string
  target_lang: string
  status: string
  segment_count: number
  failed_count: number
  elapsed_ms: number
  created_at: string | null
  source_preview: string
  translated_preview: string
}

export const translateApi = {
  // 翻译需要多次 LLM 调用，耗时远超普通请求，单独放宽到 5 分钟
  text: (content: string, targetLang: string, sourceLang = 'auto', resourceUrl?: string) =>
    api.post<{ translated: string; record_id?: string }>(
      '/translate',
      { content, target_lang: targetLang, source_lang: sourceLang, resource_url: resourceUrl },
      { timeout: 300000 },
    ),
  history: (limit = 50) =>
    api.get<{ user: UserInfo; total: number; records: HistoryRecord[] }>('/translate/history', {
      params: { limit },
    }),
}

export const prApi = {
  create: (data: { repo: string; path: string; content: string; target_lang: string; original_sha?: string }) =>
    api.post<{ pr_url: string; pr_number: number; branch: string; translated_path: string }>('/pr/create', data),
}
