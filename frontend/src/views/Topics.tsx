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

const Topics: React.FC<ViewProps> = ({ creator, notify, onChanged }) => {
  const [running, setRunning] = useState(false)
  const topics = useApi(() => api_.topics(creator.creator_id), [creator.creator_id])

  const run = async () => {
    setRunning(true)
    try {
      const result = await api_.analyzeTopics(creator.creator_id)
      notify(`Found ${result.topics_found} topics`)
      topics.reload()
      onChanged()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Topic modelling failed', 'danger')
    } finally {
      setRunning(false)
    }
  }

  const list = topics.data?.topics ?? []

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">
          {list.length > 0
            ? `${list.length} topics discovered across your comments`
            : 'Discover what your audience actually talks about'}
        </p>
        <Button
          variant="primary"
          loading={running}
          onClick={run}
          icon={<Icon path={Icons.sparkles} className="size-4" />}
        >
          {list.length > 0 ? 'Re-run topic modelling' : 'Discover topics'}
        </Button>
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader title="Topic share" subtitle="Relative mention volume" />
          <div className="mt-5">
            {topics.loading ? (
              <div className="h-56 skeleton rounded-lg" />
            ) : topics.error ? (
              <ErrorState message={topics.error} onRetry={topics.reload} />
            ) : (
              <BarList
                data={list.map((t, i) => ({
                  label: titleCase(t.name),
                  value: t.mentions,
                  color: CHART_PALETTE[i % CHART_PALETTE.length],
                  meta: `${t.share}%`,
                }))}
                emptyMessage="No topics yet. Run the analysis to discover them."
              />
            )}
          </div>
        </Card>

        <Card className="lg:col-span-3" padded={false}>
          <div className="border-b border-line px-5 py-4">
            <CardHeader
              title="All topics"
              subtitle="Sorted by how often they come up"
              action={<Badge tone="brand">{list.length}</Badge>}
            />
          </div>

          {topics.loading ? (
            <TableSkeleton rows={5} cols={4} />
          ) : topics.error ? (
            <ErrorState message={topics.error} onRetry={topics.reload} />
          ) : list.length === 0 ? (
            <EmptyState
              icon={<Icon path={Icons.topics} className="size-5" />}
              title="No topics yet"
              description="Topic modelling groups your comments into the themes that come up most."
            />
          ) : (
            <ul className="divide-y divide-line-subtle">
              {list.map((topic, i) => (
                <li key={topic.topic_id} className="px-5 py-4 transition-colors hover:bg-inset">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <span
                        className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded text-2xs font-semibold text-white"
                        style={{ backgroundColor: CHART_PALETTE[i % CHART_PALETTE.length] }}
                      >
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-strong">
                          {titleCase(topic.name)}
                        </p>
                        <p className="mt-0.5 truncate text-2xs text-muted">
                          {topic.mentions} comment{topic.mentions === 1 ? '' : 's'} ·{' '}
                          {topic.share}% of the comments
                        </p>
                      </div>
                    </div>
                    <Badge tone="neutral">{topic.mentions} mentions</Badge>
                  </div>

                  {topic.words.length > 0 ? (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {topic.words.map((word) => (
                        <span
                          key={word}
                          className="rounded bg-subtle px-1.5 py-0.5 text-2xs font-medium text-body"
                        >
                          {word}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {topic.samples.length > 0 ? (
                    <ul className="mt-3 space-y-1 border-l-2 border-line pl-3">
                      {topic.samples.slice(0, 2).map((sample, idx) => (
                        <li key={idx} className="line-clamp-1 text-2xs italic text-muted">
                          “{sample}”
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  <ProgressBar
                    className="mt-3"
                    value={topic.share}
                    max={100}
                    tone="bg-brand"
                    showLabel
                  />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

export default Topics
