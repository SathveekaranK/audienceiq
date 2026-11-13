import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api_, type EmotionBreakdown } from '@/lib/api'
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
import { BarList, CHART_PALETTE } from '@/components/charts'
import type { ViewProps } from './types'

const EMOTION_META: Record<
  string,
  { label: string; description: string; color: string; tone: string }
> = {
  influenced: {
    label: 'Influenced',
    description: 'The video changed their mind or moved them to act',
    color: 'var(--brand-500)',
    tone: 'brand',
  },
  triggered: {
    label: 'Triggered',
    description: 'The video hit them emotionally',
    color: 'var(--warning)',
    tone: 'warning',
  },
  hate: {
    label: 'Hate',
    description: 'They dislike the content or the creator',
    color: 'var(--danger)',
    tone: 'danger',
  },
  love: {
    label: 'Love',
    description: 'Genuine appreciation',
    color: 'var(--success)',
    tone: 'success',
  },
  curious: {
    label: 'Curious',
    description: 'They want more - content demand in disguise',
    color: 'var(--accent-500)',
    tone: 'brand',
  },
  neutral: {
    label: 'Neutral',
    description: 'Nothing in particular',
    color: 'var(--text-subtle)',
    tone: 'neutral',
  },
}

const ORDER = ['influenced', 'triggered', 'hate', 'love', 'curious', 'neutral']

const Emotions: React.FC<ViewProps> = ({ creator, notify }) => {
  const [running, setRunning] = useState(false)
  const [scope, setScope] = useState<'creator' | number>('creator')

  const emotions = useApi(
    () => api_.emotions(creator.creator_id, typeof scope === 'number' ? scope : undefined),
    [creator.creator_id, scope],
  )
  const videos = useApi(() => api_.videos(creator.creator_id), [creator.creator_id])

  const run = useCallback(async () => {
    setRunning(true)
    try {
      const result = await api_.analyzeEmotions(
        creator.creator_id,
        typeof scope === 'number' ? scope : undefined,
      )
      notify(`Classified ${result.analysed} comments`)
      emotions.reload()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Emotion analysis failed', 'danger')
    } finally {
      setRunning(false)
    }
  }, [creator.creator_id, scope, emotions, notify])

  // Run the detection automatically the first time a channel is opened.
  const autoRunRef = useRef(false)
  useEffect(() => {
    if (autoRunRef.current) return
    if (emotions.loading || emotions.data === null) return
    autoRunRef.current = true
    if ((emotions.data.analysed ?? 0) === 0) {
      void run()
    }
  }, [emotions.loading, emotions.data, run])

  const data = emotions.data
  const primary = data?.primary ?? []
  const multi = data?.multi_label ?? []
  const total = data?.total_comments ?? 0
  const analysed = data?.analysed ?? 0

  const byEmotion = new Map(primary.map((p) => [p.emotion, p]))
  const videoList = videos.data?.videos ?? []

  return (
    <div className="space-y-5 p-4 sm:p-6">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted">Scope</span>
          <select
            value={typeof scope === 'number' ? String(scope) : 'creator'}
            onChange={(e) =>
              setScope(e.target.value === 'creator' ? 'creator' : Number(e.target.value))
            }
            className="h-8 rounded-md border border-line bg-surface px-2.5 text-xs text-strong outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
            aria-label="Analysis scope"
          >
            <option value="creator">All videos ({creator.name})</option>
            {videoList.map((v) => (
              <option key={v.post_id} value={v.post_id}>
                {v.title?.slice(0, 46) ?? `Video ${v.post_id}`}
              </option>
            ))}
          </select>
        </div>

        <Button
          variant="primary"
          loading={running}
          onClick={run}
          icon={<Icon path={Icons.sparkles} className="size-4" />}
        >
          Detect emotions
        </Button>
      </div>

      {/* Headline numbers */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {emotions.loading ? (
          Array.from({ length: 4 }).map((_, i) => <StatTileSkeleton key={i} />)
        ) : (
          <>
            {(['influenced', 'triggered', 'hate'] as const).map((key) => {
              const row = byEmotion.get(key)
              return (
                <StatTile
                  key={key}
                  label={EMOTION_META[key].label}
                  value={`${row?.percentage ?? 0}%`}
                  hint={`${row?.count ?? 0} of ${total} comments`}
                  tone={
                    key === 'hate'
                      ? 'danger'
                      : key === 'triggered'
                        ? 'warning'
                        : 'brand'
                  }
                  icon={<Icon path={Icons.sparkles} className="size-4" />}
                />
              )
            })}
            <StatTile
              label="Comments analysed"
              value={analysed.toLocaleString()}
              hint={`${total.toLocaleString()} in scope`}
              icon={<Icon path={Icons.comments} className="size-4" />}
            />
          </>
        )}
      </div>

      {/* Explanation strip */}
      <Card className="border-brand/20 bg-brand-soft/30">
        <div className="flex flex-wrap items-start gap-x-6 gap-y-3">
          {ORDER.filter((k) => k !== 'neutral').map((key) => {
            const meta = EMOTION_META[key]
            const row = byEmotion.get(key)
            return (
              <div key={key} className="min-w-[150px] flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className="size-2.5 rounded-full"
                    style={{ backgroundColor: meta.color }}
                  />
                  <span className="text-xs font-semibold text-strong">{meta.label}</span>
                  <span className="ml-auto text-xs font-semibold tabular text-muted">
                    {row?.percentage ?? 0}%
                  </span>
                </div>
                <p className="mt-1 text-2xs leading-relaxed text-muted">
                  {meta.description}
                </p>
              </div>
            )
          })}
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-5">
        {/* Distribution */}
        <Card className="lg:col-span-2">
          <CardHeader title="Primary emotion" subtitle="Every comment counted once" />
          <div className="mt-5">
            {emotions.loading ? (
              <div className="h-56 skeleton rounded-lg" />
            ) : emotions.error ? (
              <ErrorState message={emotions.error} onRetry={emotions.reload} />
            ) : analysed === 0 ? (
              <EmptyState
                icon={<Icon path={Icons.sparkles} className="size-5" />}
                title="No emotions detected yet"
                description="Press “Detect emotions” to classify the comments in scope."
              />
            ) : (
              <BarList
                data={primary.map((row, i) => ({
                  label: EMOTION_META[row.emotion]?.label ?? row.emotion,
                  value: row.count,
                  color:
                    EMOTION_META[row.emotion]?.color ??
                    CHART_PALETTE[i % CHART_PALETTE.length],
                  meta: `${row.percentage}%`,
                }))}
              />
            )}
          </div>
        </Card>

        {/* Multi-label + examples */}
        <Card className="lg:col-span-3" padded={false}>
          <div className="border-b border-line px-5 py-4">
            <CardHeader
              title="Every signal"
              subtitle="A comment can hit more than one emotion"
              action={<Badge tone="neutral">{multi.length} signals</Badge>}
            />
          </div>

          {emotions.loading ? (
            <div className="space-y-3 p-5">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-20 skeleton rounded-lg" />
              ))}
            </div>
          ) : emotions.error ? (
            <ErrorState message={emotions.error} onRetry={emotions.reload} />
          ) : analysed === 0 ? (
            <EmptyState
              icon={<Icon path={Icons.sparkles} className="size-5" />}
              title="Nothing to show yet"
              description="Run the emotion detection to see how your audience reacted."
            />
          ) : (
            <div className="p-5">
              <ul className="space-y-2.5">
                {multi.map((row, i) => {
                  const meta = EMOTION_META[row.emotion]
                  return (
                    <li key={row.emotion}>
                      <div className="mb-1 flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2 text-xs font-medium text-body">
                          <span
                            className="size-2 rounded-full"
                            style={{ backgroundColor: meta?.color ?? CHART_PALETTE[i % CHART_PALETTE.length] }}
                          />
                          {meta?.label ?? row.emotion}
                        </span>
                        <span className="text-xs tabular text-muted">
                          {row.count} · {row.percentage}%
                        </span>
                      </div>
                      <ProgressBar
                        value={row.percentage}
                        tone="bg-brand"
                      />
                    </li>
                  )
                })}
              </ul>

              {/* Examples */}
              {Object.entries(data?.examples ?? {})
                .filter(([emotion]) => emotion !== 'neutral')
                .map(([emotion, examples]) => {
                  const meta = EMOTION_META[emotion]
                  if (!examples.length) return null
                  return (
                    <div key={emotion} className="mt-6 border-t border-line-subtle pt-5">
                      <p className="flex items-center gap-2 text-xs font-semibold text-strong">
                        <span
                          className="size-2.5 rounded-full"
                          style={{ backgroundColor: meta.color }}
                        />
                        {meta.label}
                        <span className="font-normal text-muted">
                          - what they said
                        </span>
                      </p>
                      <ul className="mt-2.5 space-y-2">
                        {examples.slice(0, 3).map((example) => (
                          <li
                            key={example.comment_id}
                            className="rounded-md border border-line bg-inset px-3 py-2"
                          >
                            <p className="line-clamp-2 text-xs leading-relaxed text-body">
                              “{example.text}”
                            </p>
                            <p className="mt-1 flex flex-wrap items-center gap-x-3 text-2xs text-muted">
                              {example.author ? <span>@{example.author}</span> : null}
                              {example.likes ? <span>{example.likes} likes</span> : null}
                              {example.confidence ? (
                                <span>
                                  confidence{' '}
                                  {(example.confidence * 100).toFixed(0)}%
                                </span>
                              ) : null}
                            </p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )
                })}

              {data?.languages?.length ? (
                <div className="mt-6 border-t border-line-subtle pt-5">
                  <p className="text-xs font-semibold text-strong">Comment languages</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {data.languages.map((lang) => (
                      <Badge key={lang.language} tone="neutral">
                        {lang.language} {lang.count}
                      </Badge>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

export default Emotions
