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
  TableSkeleton,
} from '@/components/ui'
import { BarList, CHART_PALETTE } from '@/components/charts'
import { titleCase } from '@/lib/format'
import type { ViewProps } from './types'

const Segments: React.FC<ViewProps> = ({ creator, notify, onChanged }) => {
  const [running, setRunning] = useState(false)
  const [clusterCount, setClusterCount] = useState(5)
  const segments = useApi(
    () => api_.segments(creator.creator_id),
    [creator.creator_id],
  )

  const run = async () => {
    setRunning(true)
    try {
      const result = await api_.analyzeSegmentation(creator.creator_id)
      notify(`Formed ${result.clusters_formed} segments`)
      segments.reload()
      onChanged()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Segmentation failed', 'danger')
    } finally {
      setRunning(false)
    }
  }

  const list = segments.data?.segments ?? []

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">
          {list.length > 0
            ? `${list.length} distinct audiences identified`
            : 'Group your viewers into distinct audiences'}
        </p>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-muted">
            Clusters
            <input
              type="number"
              min={2}
              max={10}
              value={clusterCount}
              onChange={(e) =>
                setClusterCount(Math.min(10, Math.max(2, Number(e.target.value) || 2)))
              }
              className="h-8 w-16 rounded-md border border-line bg-surface px-2 text-center text-xs text-strong outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
            />
          </label>
          <Button
            variant="primary"
            loading={running}
            onClick={run}
            icon={<Icon path={Icons.sparkles} className="size-4" />}
          >
            {list.length > 0 ? 'Re-cluster' : 'Segment audience'}
          </Button>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader title="Segment sizes" subtitle="Share of your audience" />
          <div className="mt-5">
            {segments.loading ? (
              <div className="h-56 skeleton rounded-lg" />
            ) : segments.error ? (
              <ErrorState message={segments.error} onRetry={segments.reload} />
            ) : (
              <BarList
                data={list.map((s, i) => ({
                  label: titleCase(s.name),
                  value: s.size,
                  color: CHART_PALETTE[i % CHART_PALETTE.length],
                  meta: `${s.percentage}%`,
                }))}
                emptyMessage="No segments yet. Run the analysis to group your viewers."
              />
            )}
          </div>
        </Card>

        <Card className="lg:col-span-3" padded={false}>
          <div className="border-b border-line px-5 py-4">
            <CardHeader
              title="Audience segments"
              subtitle="Named after the keywords in each cluster"
              action={<Badge tone="brand">{list.length}</Badge>}
            />
          </div>

          {segments.loading ? (
            <TableSkeleton rows={4} cols={3} />
          ) : segments.error ? (
            <ErrorState message={segments.error} onRetry={segments.reload} />
          ) : list.length === 0 ? (
            <EmptyState
              icon={<Icon path={Icons.segments} className="size-5" />}
              title="No segments yet"
              description="Clustering reads the text of every comment and groups viewers with shared interests."
            />
          ) : (
            <ul className="divide-y divide-line-subtle">
              {list.map((segment, i) => (
                <li key={segment.segment_id} className="px-5 py-4 transition-colors hover:bg-inset">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <span
                        className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md text-2xs font-semibold text-white"
                        style={{ backgroundColor: CHART_PALETTE[i % CHART_PALETTE.length] }}
                      >
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-strong">
                          {titleCase(segment.name)}
                        </p>
                        <p className="mt-0.5 text-2xs text-muted">
                          {segment.description}
                        </p>
                      </div>
                    </div>
                    <Badge tone="neutral">{segment.percentage}%</Badge>
                  </div>

                  <ProgressBar
                    className="mt-3"
                    value={segment.percentage}
                    tone="bg-brand"
                  />

                  {segment.sample_comments.length > 0 ? (
                    <div className="mt-3 space-y-1.5 border-l-2 border-line pl-3">
                      {segment.sample_comments.map((text, idx) => (
                        <p key={idx} className="line-clamp-2 text-2xs italic text-muted">
                          “{text}”
                        </p>
                      ))}
                    </div>
                  ) : null}

                  <p className="mt-2.5 text-2xs text-subtle-text">
                    {segment.size} comment{segment.size === 1 ? '' : 's'} ·{' '}
                    {segment.algorithm}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

export default Segments
