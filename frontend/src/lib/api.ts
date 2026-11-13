/**
 * Typed API client for the AudienceIQ backend.
 *
 * All requests go through `request()` so error handling, JSON parsing and
 * the base URL live in exactly one place.
 */

const BASE_URL =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API_URL ??
  'http://127.0.0.1:8000'

const AUTH_TOKEN_KEY = 'aiq_access_token'

function getAuthToken(): string | null {
  return window.localStorage.getItem(AUTH_TOKEN_KEY)
}

export function setAuthToken(token: string): void {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token)
}

export function clearAuthToken(): void {
  window.localStorage.removeItem(AUTH_TOKEN_KEY)
}

export function hasAuthToken(): boolean {
  return Boolean(getAuthToken())
}

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

type Query = Record<string, string | number | boolean | null | undefined>

function buildUrl(path: string, query?: Query): string {
  const url = new URL(`${BASE_URL}${path}`)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') continue
      url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

async function request<T>(
  method: string,
  path: string,
  options: { query?: Query; body?: unknown } = {},
): Promise<T> {
  let response: Response

  try {
    const headers: Record<string, string> = {}
    if (options.body) headers['Content-Type'] = 'application/json'
    const token = getAuthToken()
    if (token) headers.Authorization = `Bearer ${token}`

    response = await fetch(buildUrl(path, options.query), {
      method,
      headers: Object.keys(headers).length > 0 ? headers : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
  } catch {
    throw new ApiError(
      0,
      'Cannot reach the API. Is the backend running on port 8000?',
    )
  }

  const text = await response.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/api/v1/auth/')) {
      clearAuthToken()
      window.dispatchEvent(new Event('audienceiq:auth-expired'))
    }
    const detail =
      typeof payload === 'object' && payload !== null && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : `Request failed with status ${response.status}`
    throw new ApiError(response.status, detail)
  }

  return payload as T
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>('GET', path, { query }),
  post: <T>(path: string, body?: unknown, query?: Query) =>
    request<T>('POST', path, { body, query }),
  del: <T>(path: string) => request<T>('DELETE', path),
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export type SentimentLabel = 'positive' | 'negative' | 'neutral' | 'unanalyzed'

export interface CreatorStats {
  videos: number
  comments: number
  segments: number
  reports: number
  views?: number
  likes?: number
}

export interface AuthResponse {
  user_id: number
  access_token: string
  token_type: 'bearer'
}

export interface Creator {
  creator_id: number
  name: string
  handle: string
  platform_type: string
  description: string | null
  profile_image: string | null
  created_at: string | null
  stats: CreatorStats
}

export interface Segment {
  segment_id: number
  name: string
  description: string | null
  algorithm: string | null
  size: number
  percentage: number
  sample_comments: string[]
}

export interface Topic {
  topic_id: number
  name: string
  slug: string
  description: string | null
  words: string[]
  mentions: number
  share: number
  avg_relevance: number
  samples: string[]
}

export interface DashboardSummary {
  creator: {
    creator_id: number
    name: string
    handle: string
    platform_type: string
    profile_image: string | null
  }
  totals: {
    videos: number
    comments: number
    comments_analyzed: number
    views: number
    likes: number
    segments: number
    topics: number
    reports: number
  }
  sentiment: {
    positive: number
    negative: number
    neutral: number
    positive_percent: number
    negative_percent: number
    neutral_percent: number
    analyzed: number
  }
  top_topics: { topic: string; mentions: number }[]
  segments: Segment[]
  most_discussed: {
    post_id: number
    title: string
    comments: number
    view_count: number
  } | null
}

export interface Video {
  post_id: number
  title: string | null
  description: string | null
  published_at: string | null
  view_count: number
  like_count: number
  comment_count: number
  sentiment: Record<SentimentLabel, number>
}

export interface CommentItem {
  comment_id: number
  post_id: number
  text: string
  like_count: number
  published_at: string | null
  sentiment: SentimentLabel
  sentiment_score: number | null
}

export interface PainPointExample {
  comment_id: number
  text: string
  sentiment: string
  matched: string[]
}

export interface PainPoint {
  type: string
  label: string
  count: number
  share: number
  examples: PainPointExample[]
}

export interface ContentRequest {
  category: string
  topic: string
  confidence: number
  count: number
}

export interface SentimentPoint {
  date: string
  positive: number
  negative: number
  neutral: number
  total: number
  positive_percent: number
  negative_percent: number
  neutral_percent: number
}

export interface AnalysisOverview {
  creator_id: number
  comments: number
  sentiment_analyzed: number
  topics: number
  segments: number
  needs_sentiment: boolean
  needs_topics: boolean
  needs_segmentation: boolean
}

export interface Report {
  report_id: number
  report_name: string
  date_from: string | null
  date_to: string | null
  total_comments: number
  generated_at: string | null
}

// ---------------------------------------------------------------------------
// YouTube video analysis
// ---------------------------------------------------------------------------

export interface VideoMetadata {
  video_id: string
  title: string
  channel: string
  channel_id: string
  author_url: string
  description: string
  published_at: string
  view_count: number | null
  like_count: number | null
  duration_seconds: number | null
  thumbnail_url: string
  watch_url: string
  source?: string
}

export interface VideoWorkspaceEntry {
  post_id: number
  creator_id: number
  channel: string
  title: string | null
  thumbnail_url: string | null
  watch_url: string | null
  view_count: number
  like_count: number
  comment_count: number
  published_at: string | null
  duration_seconds: number | null
  sentiment: Record<string, number>
  emotions: Record<string, number>
}

export interface EmotionExample {
  comment_id: number
  text: string
  author: string | null
  likes: number
  confidence: number | null
  intensity: number | null
}

export interface EmotionRow {
  emotion: string
  count: number
  percentage: number
}

export interface EmotionBreakdown {
  creator_id: number
  post_id: number | null
  total_comments: number
  analysed: number
  primary: EmotionRow[]
  multi_label: EmotionRow[]
  languages: { language: string; count: number }[]
  examples: Record<string, EmotionExample[]>
}

// ---------------------------------------------------------------------------
// Endpoint helpers
// ---------------------------------------------------------------------------

export const api_ = {
  // Workspace
  listCreators: () => api.get<{ creators: Creator[]; total: number }>('/api/v1/creators'),
  getCreator: (id: number) => api.get<Creator>(`/api/v1/creators/${id}`),
  deleteCreator: (id: number) =>
    api.del<{ message: string }>(`/api/v1/creators/${id}`),
  addCreator: (creator_name: string, platform_id: string) =>
    api.post<{ creator_id: number }>('/api/v1/creators/add', undefined, {
      creator_name,
      platform_id,
    }),
  searchCreators: (query: string) =>
    api.get<{ creators: { creator_id: number; name: string }[] }>(
      '/api/v1/creators/search',
      { query },
    ),

  // Dashboard
  dashboard: (creatorId: number) =>
    api.get<DashboardSummary>(`/api/v1/dashboard/summary/${creatorId}`),
  overview: (creatorId: number) =>
    api.get<AnalysisOverview>(`/api/v1/analysis/overview/${creatorId}`),

  // Content
  videos: (creatorId: number) =>
    api.get<{ videos: Video[]; total: number }>(`/api/v1/creators/${creatorId}/videos`),
  comments: (
    creatorId: number,
    query: { sentiment?: string; search?: string; limit?: number; offset?: number } = {},
  ) =>
    api.get<{
      comments: CommentItem[]
      total: number
      has_more: boolean
    }>(`/api/v1/creators/${creatorId}/comments`, query),

  // Analysis
  topics: (creatorId: number) =>
    api.get<{ topics: Topic[]; total: number }>(`/api/v1/analysis/topics/${creatorId}`),
  segments: (creatorId: number) =>
    api.get<{ segments: Segment[]; total: number }>(`/api/v1/analysis/segments/${creatorId}`),
  painPoints: (creatorId: number) =>
    api.get<{ pain_points: PainPoint[]; total: number }>(
      `/api/v1/analysis/pain-points/${creatorId}`,
    ),
  contentRequests: (creatorId: number) =>
    api.get<{
      requests: ContentRequest[]
      by_category: Record<string, number>
      total: number
    }>(`/api/v1/analysis/content-requests/${creatorId}`),
  sentimentTimeseries: (creatorId: number, days = 30) =>
    api.get<{ series: SentimentPoint[]; total: number }>(
      `/api/v1/analysis/sentiment/timeseries/${creatorId}`,
      { days },
    ),
  engagement: (creatorId: number) =>
    api.get<{ engagement_data: unknown[]; most_active_video: unknown }>(
      `/api/v1/analysis/engagement/${creatorId}`,
    ),

  // Actions
  collectComments: (postId: number) =>
    api.post<{ message: string }>(`/api/v1/comments/collect/${postId}`),
  analyzeSentiment: (creatorId: number) =>
    api.post<{ analyzed: number; distribution: Record<string, { count: number; percentage: number }> }>(
      `/api/v1/analysis/sentiment/bulk/${creatorId}`,
    ),
  analyzeTopics: (creatorId: number) =>
    api.post<{ topics_found: number }>(`/api/v1/analysis/topics/${creatorId}`),
  analyzeSegmentation: (creatorId: number) =>
    api.post<{ clusters_formed: number }>(`/api/v1/analysis/segmentation/${creatorId}`),
  detectPainPoints: (creatorId: number) =>
    api.post<{ pain_points: unknown[] }>(`/api/v1/analysis/pain-points/${creatorId}`),
  detectContentRequests: (creatorId: number) =>
    api.post<{ content_requests_found: number }>(
      `/api/v1/analysis/content-requests/${creatorId}`,
    ),
  generateReport: (creatorId: number, report_name: string, date_from: string, date_to: string) =>
    api.post<{ report_id: number }>(`/api/v1/reports/generate/${creatorId}`, undefined, {
      report_name,
      date_from,
      date_to,
    }),
  reports: (creatorId: number) =>
    api.get<{ creator_id: number; reports: Report[] }>(`/api/v1/reports/${creatorId}`),

  // Auth
  // Credentials go in the JSON body - never in the query string, where they
  // would end up in the URL, browser history and server access logs.
  register: async (username: string, email: string, password: string) => {
    const result = await api.post<AuthResponse>('/api/v1/auth/register', {
      username,
      email,
      password,
    })
    setAuthToken(result.access_token)
    return result
  },
  login: async (username: string, password: string) => {
    const result = await api.post<AuthResponse>('/api/v1/auth/login', {
      username,
      password,
    })
    setAuthToken(result.access_token)
    return result
  },
  logout: async () => {
    try {
      return await api.post<{ message: string }>('/api/v1/auth/logout')
    } finally {
      clearAuthToken()
    }
  },

  // YouTube video analysis
  resolveVideo: (url: string) =>
    api.post<VideoMetadata>('/api/v1/videos/resolve', undefined, { url }),
  analyzeVideo: (url: string, maxComments = 120) =>
    api.post<{
      message: string
      creator: { creator_id: number; name: string; handle: string }
      video: {
        post_id: number
        video_id: string
        title: string
        channel: string
        watch_url: string
        thumbnail_url: string | null
        view_count: number
        like_count: number
        comment_count: number
        published_at: string | null
        duration_seconds: number | null
      }
      comments_fetched: number
      comments_added: number
      analysis: Record<string, unknown>
    }>('/api/v1/videos/analyze', undefined, { url, max_comments: maxComments }),
  reanalyzeVideo: (postId: number, maxComments = 120) =>
    api.post<{ message: string; comments_added: number; analysis: Record<string, unknown> }>(
      `/api/v1/videos/${postId}/analyze`,
      undefined,
      { max_comments: maxComments },
    ),
  videoWorkspace: () =>
    api.get<{ videos: VideoWorkspaceEntry[]; total: number }>('/api/v1/videos/workspace'),

  // Emotions
  emotions: (creatorId: number, postId?: number) =>
    api.get<EmotionBreakdown>(`/api/v1/analysis/emotions/${creatorId}`, {
      post_id: postId,
    }),
  analyzeEmotions: (creatorId: number, postId?: number) =>
    api.post<{
      analysed: number
      distribution: Record<string, number>
      languages: Record<string, number>
    }>(`/api/v1/analysis/emotions/${creatorId}`, undefined, { post_id: postId }),
}
