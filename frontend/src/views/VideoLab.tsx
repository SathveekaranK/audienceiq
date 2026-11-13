import React, { useState } from 'react'
import { api_, type VideoMetadata, type VideoWorkspaceEntry } from '@/lib/api'
import { useApi } from '@/lib/hooks'
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Icon,
  Icons,
  ProgressBar,
  StatTile,
  StatTileSkeleton,
} from '@/components/ui'
import { formatDate, compactNumber } from '@/lib/format'
import type { ViewProps } from './types'

const EMOTION_TONES: Record<string, 'brand' | 'success' | 'danger' | 'warning' | 'info' | 'neutral'> = {
  influenced: 'brand',
  triggered: 'warning',
  hate: 'danger',
  love: 'success',
  curious: 'info',
  neutral: 'neutral',
}

const VideoLab: React.FC<ViewProps> = ({ creator, notify, onChanged, selectCreator }) => {
  const [url, setUrl] = useState('')
  const [resolving, setResolving] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [preview, setPreview] = useState<VideoMetadata | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)

  const workspace = useApi(() => api_.videoWorkspace(), [])

  const resolve = async () => {
    if (!url.trim()) {
      setError('Paste a YouTube video link first')
      return
    }
    setResolving(true)
    setError(null)
    setResult(null)
    try {
      const meta = await api_.resolveVideo(url.trim())
      setPreview(meta)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not read that link')
      setPreview(null)
    } finally {
      setResolving(false)
    }
  }

  const analyze = async () => {
    setAnalyzing(true)
    setError(null)
    try {
      const response = await api_.analyzeVideo(url.trim(), 120)
      setResult(response.analysis as Record<string, unknown>)
      setPreview(null)
      notify(`Analysed ${response.comments_added} new comments`)
      workspace.reload()
      onChanged()
      // Jump straight to the channel that was just analysed so the rest of
      // the dashboard is showing the new data.
      selectCreator(response.creator.creator_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  const entries = workspace.data?.videos ?? []

  return (
    <div className="space-y-5 p-4 sm:p-6">
      {/* Input card */}
      <Card>
        <CardHeader
          title="Analyse a YouTube video"
          subtitle="Paste any video link and AudienceIQ pulls its real comments straight from YouTube"
        />

        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Icon
              path={Icons.videos}
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-subtle-text"
            />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && resolve()}
              placeholder="https://www.youtube.com/watch?v=XXXXXXXXXXX"
              aria-label="YouTube video link"
              className="h-10 w-full rounded-md border border-line bg-surface pl-9 pr-3 text-sm text-strong outline-none transition-shadow placeholder:text-subtle-text focus:border-brand focus:ring-2 focus:ring-brand/15"
            />
          </div>
          <Button
            variant="secondary"
            loading={resolving}
            onClick={resolve}
            icon={<Icon path={Icons.search} className="size-4" />}
          >
            Preview
          </Button>
          <Button
            variant="primary"
            loading={analyzing}
            onClick={analyze}
            icon={<Icon path={Icons.sparkles} className="size-4" />}
          >
            Fetch &amp; analyse
          </Button>
        </div>

        {error ? (
          <p className="mt-3 flex items-start gap-2 rounded-md bg-danger-soft px-3 py-2 text-xs text-danger">
            <Icon path={Icons.alert} className="mt-px size-3.5 shrink-0" />
            {error}
          </p>
        ) : null}

        {/* Preview card */}
        {preview ? (
          <div className="mt-4 animate-fade-in overflow-hidden rounded-lg border border-line bg-inset">
            <div className="flex flex-col gap-4 p-4 sm:flex-row">
              {preview.thumbnail_url ? (
                <img
                  src={preview.thumbnail_url}
                  alt=""
                  className="w-full shrink-0 rounded-md object-cover sm:w-56"
                />
              ) : null}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-strong">{preview.title}</p>
                <p className="mt-1 text-xs text-muted">{preview.channel}</p>

                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
                  <span>{compactNumber(preview.view_count)} views</span>
                  {preview.duration_seconds ? (
                    <span>{Math.round(preview.duration_seconds / 60)} min</span>
                  ) : null}
                  {preview.published_at ? (
                    <span>{formatDate(preview.published_at.slice(0, 10))}</span>
                  ) : null}
                </div>

                <a
                  href={preview.watch_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-brand hover:underline"
                >
                  <Icon path={Icons.eye} className="size-3.5" />
                  Open on YouTube
                </a>
              </div>
            </div>
          </div>
        ) : null}

        {/* Analysis result */}
        {result ? (
          <div className="mt-4 animate-fade-in rounded-lg border border-brand/25 bg-brand-soft/40 p-4">
            <p className="text-xs font-semibold text-strong">Analysis complete</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(result).map(([key, value]) => (
                <div key={key} className="rounded-md bg-surface px-3 py-2">
                  <p className="text-2xs text-muted">{key.replace(/_/g, ' ')}</p>
                  <p className="mt-0.5 text-sm font-semibold tabular text-strong">
                    {typeof value === 'object' && value !== null
                      ? Object.entries(value as Record<string, number>)
                          .map(([k, v]) => `${k} ${v}`)
                          .join(' · ')
                      : String(value)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </Card>

      {/* Already analysed videos */}
      <Card padded={false}>
        <div className="border-b border-line px-5 py-4">
          <CardHeader
            title="Analysed videos"
            subtitle="Every video AudienceIQ has pulled comments for"
            action={<Badge tone="brand">{entries.length}</Badge>}
          />
        </div>

        {workspace.loading ? (
          <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <StatTileSkeleton key={i} />
            ))}
          </div>
        ) : workspace.error ? (
          <ErrorState message={workspace.error} onRetry={workspace.reload} />
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<Icon path={Icons.videos} className="size-5" />}
            title="No videos analysed yet"
            description="Paste a YouTube link above and AudienceIQ will fetch its comments and analyse them."
          />
        ) : (
          <ul className="divide-y divide-line-subtle">
            {entries.map((video) => (
              <li key={video.post_id} className="px-5 py-4 transition-colors hover:bg-inset">
                <div className="flex flex-col gap-4 sm:flex-row">
                  {video.thumbnail_url ? (
                    <img
                      src={video.thumbnail_url}
                      alt=""
                      className="w-full shrink-0 rounded-md object-cover sm:w-40"
                    />
                  ) : null}

                  <div className="min-w-0 flex-1">
                    <a
                      href={video.watch_url ?? '#'}
                      target="_blank"
                      rel="noreferrer"
                      className="line-clamp-1 text-sm font-semibold text-strong hover:text-brand"
                    >
                      {video.title}
                    </a>
                    <p className="mt-0.5 text-xs text-muted">{video.channel}</p>

                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
                      <span>{compactNumber(video.view_count)} views</span>
                      <span>{video.comment_count} comments</span>
                      {video.published_at ? (
                        <span>{formatDate(video.published_at.slice(0, 10))}</span>
                      ) : null}
                    </div>

                    {Object.keys(video.emotions).length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {Object.entries(video.emotions).map(([emotion, count]) => (
                          <Badge key={emotion} tone={EMOTION_TONES[emotion] ?? 'neutral'}>
                            {emotion} {count}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

export default VideoLab
