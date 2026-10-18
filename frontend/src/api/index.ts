import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
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
