import React, { useState } from 'react'
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
import { BarList, CHART_PALETTE } from '@/components/charts'
import type { ViewProps } from './types'

const CATEGORY_LABELS: Record<string, string> = {
  tutorial_request: 'Tutorial requests',
  explanation_request: 'Explanation requests',
  project_walkthrough: 'Project walkthroughs',
  updated_content_request: 'Requests for updates',
  comparison_request: 'Comparison requests',
  recommendation_request: 'Recommendation requests',
}

function labelFor(category: string): string {
  return (
    CATEGORY_LABELS[category] ??
    category.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  )
}

const ContentIdeas: React.FC<ViewProps> = ({ creator, notify }) => {
  const [running, setRunning] = useState(false)
  const requests = useApi(
    () => api_.contentRequests(creator.creator_id),
    [creator.creator_id],
  )

  const run = async () => {
    setRunning(true)
    try {
      const result = await api_.detectContentRequests(creator.creator_id)
      notify(`Found ${result.content_requests_found} content signals`)
      requests.reload()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Detection failed', 'danger')
    } finally {
      setRunning(false)
    }
  }

  const list = requests.data?.requests ?? []
  const byCategory = requests.data?.by_category ?? {}
  const categoryEntries = Object.entries(byCategory).sort((a, b) => b[1] - a[1])

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">
          {list.length > 0
            ? `${list.length} signals about what to make next`
            : 'Turn audience questions into your next video ideas'}
        </p>
        <Button
          variant="primary"
          loading={running}
          onClick={run}
          icon={<Icon path={Icons.sparkles} className="size-4" />}
        >
          Detect content demand
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {requests.loading ? (
          Array.from({ length: 3 }).map((_, i) => <StatTileSkeleton key={i} />)
        ) : (
          <>
            <StatTile
              label="Demand signals"
              value={list.length}
              hint="Individual requests found"
              tone="brand"
              icon={<Icon path={Icons.content} className="size-4" />}
            />
            <StatTile
              label="Categories"
              value={categoryEntries.length}
              hint="Distinct request types"
              icon={<Icon path={Icons.layers} className="size-4" />}
            />
            <StatTile
              label="Top category"
              value={categoryEntries[0] ? labelFor(categoryEntries[0][0]) : '—'}
              hint={categoryEntries[0] ? `${categoryEntries[0][1]} signals` : 'No signals yet'}
              tone="warning"
              icon={<Icon path={Icons.topics} className="size-4" />}
            />
          </>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader title="Demand by category" subtitle="What viewers are asking for" />
          <div className="mt-5">
            {requests.loading ? (
              <div className="h-56 skeleton rounded-lg" />
            ) : requests.error ? (
              <ErrorState message={requests.error} onRetry={requests.reload} />
            ) : (
              <BarList
                data={categoryEntries.map(([category, count], i) => ({
                  label: labelFor(category),
                  value: count,
                  color: CHART_PALETTE[i % CHART_PALETTE.length],
                }))}
                emptyMessage="No content demand detected yet."
              />
            )}
          </div>
        </Card>

        <Card className="lg:col-span-3" padded={false}>
          <div className="border-b border-line px-5 py-4">
            <CardHeader
              title="Suggested next videos"
              subtitle="Ranked by how often viewers asked"
              action={<Badge tone="brand">{list.length}</Badge>}
            />
          </div>

          {requests.loading ? (
            <div className="space-y-3 p-5">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-16 skeleton rounded-lg" />
              ))}
            </div>
          ) : requests.error ? (
            <ErrorState message={requests.error} onRetry={requests.reload} />
          ) : list.length === 0 ? (
            <EmptyState
              icon={<Icon path={Icons.content} className="size-5" />}
              title="No suggestions yet"
              description="We look for phrases like “can you explain” or “how do I” to spot what your audience wants next."
            />
          ) : (
            <ol className="divide-y divide-line-subtle">
              {list.map((item, i) => (
                <li key={`${item.category}-${item.topic}-${i}`} className="px-5 py-4 transition-colors hover:bg-inset">
                  <div className="flex items-start gap-3">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-brand-soft text-2xs font-semibold text-brand">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-strong">
                        {item.topic || labelFor(item.category)}
                      </p>
                      <p className="mt-0.5 text-2xs text-muted">
                        {labelFor(item.category)}
                      </p>
                      <div className="mt-2 flex items-center gap-3">
                        <span className="text-2xs text-muted">
                          Confidence{' '}
                          <span className="font-semibold tabular text-body">
                            {(item.confidence * 100).toFixed(0)}%
                          </span>
                        </span>
                        <span className="text-2xs text-muted">
                          <span className="font-semibold tabular text-body">{item.count}</span>{' '}
                          request{item.count === 1 ? '' : 's'}
                        </span>
                      </div>
                      <ProgressBar
                        className="mt-2"
                        value={item.confidence * 100}
                        tone="bg-brand"
                      />
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  )
}

export default ContentIdeas
