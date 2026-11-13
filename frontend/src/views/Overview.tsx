import React from 'react'
import { api_ } from '@/lib/api'
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
import { BarList, DonutChart, SENTIMENT_COLORS } from '@/components/charts'
import { titleCase } from '@/lib/format'
import type { ViewProps } from './types'

const Overview: React.FC<ViewProps> = ({ creator, onChanged, notify }) => {
  const summary = useApi(() => api_.dashboard(creator.creator_id), [creator.creator_id])
  const overview = useApi(() => api_.overview(creator.creator_id), [creator.creator_id])

  const runAll = async () => {
    try {
      await api_.analyzeSentiment(creator.creator_id)
      await api_.analyzeTopics(creator.creator_id)
      await api_.analyzeSegmentation(creator.creator_id)
      await api_.detectPainPoints(creator.creator_id)
      await api_.detectContentRequests(creator.creator_id)
      notify('Analysis complete')
      summary.reload()
      overview.reload()
      onChanged()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Analysis failed', 'danger')
    }
  }

  if (summary.loading) {
    return (
      <div className="space-y-5 p-4 sm:p-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <StatTileSkeleton key={i} />
          ))}
        </div>
        <div className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2 h-72 skeleton rounded-card" />
          <div className="h-72 skeleton rounded-card" />
        </div>
      </div>
    )
  }

  if (summary.error) {
    return (
      <ErrorState
        message={summary.error}
        onRetry={summary.reload}
        className="py-20"
      />
    )
  }

  const data = summary.data
  if (!data) return null

  const { totals, sentiment, top_topics, segments } = data
  const hasData = totals.comments > 0

  return (
    <div className="space-y-5 p-4 sm:p-6">
      {/* Analysis prompt */}
      {hasData && overview.data?.needs_sentiment ? (
        <Card className="border-brand/25 bg-brand-soft/40">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-brand text-white">
                <Icon path={Icons.sparkles} className="size-4" />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-strong">
                  Ready to analyse {totals.comments} comments
                </h3>
                <p className="mt-0.5 text-xs text-muted">
                  Run sentiment, topic modelling and audience segmentation in one go.
                </p>
              </div>
            </div>
            <Button variant="primary" onClick={runAll}>
              <Icon path={Icons.play} className="size-3.5" />
              Run full analysis
            </Button>
          </div>
        </Card>
      ) : null}

      {/* KPI row */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Comments analysed"
          value={totals.comments_analyzed.toLocaleString()}
          hint={`${totals.comments.toLocaleString()} collected in total`}
          tone="brand"
          icon={<Icon path={Icons.comments} className="size-4" />}
        />
        <StatTile
          label="Videos"
          value={totals.videos.toLocaleString()}
          hint={`${totals.views.toLocaleString()} total views`}
          icon={<Icon path={Icons.videos} className="size-4" />}
        />
        <StatTile
          label="Positive sentiment"
          value={`${sentiment.positive_percent}%`}
          hint={`${sentiment.positive.toLocaleString()} of ${sentiment.analyzed.toLocaleString()} comments`}
          tone="success"
          icon={<Icon path={Icons.sentiment} className="size-4" />}
        />
        <StatTile
          label="Audience segments"
          value={totals.segments.toLocaleString()}
          hint={`${totals.topics} topics discovered`}
          tone="warning"
          icon={<Icon path={Icons.segments} className="size-4" />}
        />
      </div>

      {/* Charts */}
      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Sentiment split"
            subtitle="Across every analysed comment"
          />
          <div className="mt-5">
            {sentiment.analyzed === 0 ? (
              <EmptyState
                icon={<Icon path={Icons.sentiment} className="size-5" />}
                title="No sentiment yet"
                description="Run the analysis to see how your audience feels about your content."
              />
            ) : (
              <DonutChart
                data={[
                  { label: 'Positive', value: sentiment.positive, color: SENTIMENT_COLORS.positive },
                  { label: 'Neutral', value: sentiment.neutral, color: SENTIMENT_COLORS.neutral },
                  { label: 'Negative', value: sentiment.negative, color: SENTIMENT_COLORS.negative },
                ]}
                centerValue={`${sentiment.analyzed}`}
                centerLabel="comments"
              />
            )}
          </div>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader
            title="Top discussion topics"
            subtitle="What viewers talk about most"
            action={
              top_topics.length > 0 ? (
                <Badge tone="brand">{top_topics.length} topics</Badge>
              ) : null
            }
          />
          <div className="mt-5">
            <BarList
              data={top_topics.map((t) => ({
                label: titleCase(t.topic),
                value: t.mentions,
                color: 'var(--brand-500)',
              }))}
              emptyMessage="Run topic modelling to discover what your audience talks about."
            />
          </div>
        </Card>
      </div>

      {/* Segments + most discussed */}
      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader
            title="Audience segments"
            subtitle="Groups of viewers with shared interests"
          />
          <div className="mt-5 space-y-4">
            {segments.length === 0 ? (
              <EmptyState
                icon={<Icon path={Icons.segments} className="size-5" />}
                title="No segments yet"
                description="Run segmentation to group your viewers into distinct audiences."
              />
            ) : (
              segments.map((segment) => (
                <div key={segment.segment_id} className="rounded-lg border border-line bg-inset p-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-strong">
                        {titleCase(segment.name)}
                      </p>
                      <p className="mt-0.5 truncate text-2xs text-muted">
                        {segment.description}
                      </p>
                    </div>
                    <Badge tone="brand">{segment.percentage}%</Badge>
                  </div>
                  <ProgressBar
                    className="mt-3"
                    value={segment.percentage}
                    tone="bg-brand"
                  />
                  <p className="mt-2 text-2xs text-muted">
                    {segment.size} comment{segment.size === 1 ? '' : 's'} ·{' '}
                    {segment.algorithm}
                  </p>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Most discussed video" subtitle="Where the conversation is" />
          <div className="mt-5">
            {data.most_discussed ? (
              <div className="rounded-lg border border-line bg-inset p-4">
                <div className="flex items-start gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-brand-soft text-brand">
                    <Icon path={Icons.videos} className="size-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-xs font-semibold text-strong">
                      {data.most_discussed.title}
                    </p>
                    <p className="mt-1 text-2xs text-muted">
                      {data.most_discussed.comments} comments ·{' '}
                      {data.most_discussed.view_count.toLocaleString()} views
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState
                icon={<Icon path={Icons.videos} className="size-5" />}
                title="No videos yet"
                description="Add a channel and collect comments to see your best performing content."
              />
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

export default Overview
