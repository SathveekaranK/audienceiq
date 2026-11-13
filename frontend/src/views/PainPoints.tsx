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
import { BarList } from '@/components/charts'
import type { ViewProps } from './types'

const PainPoints: React.FC<ViewProps> = ({ creator, notify }) => {
  const [running, setRunning] = useState(false)
  const pains = useApi(() => api_.painPoints(creator.creator_id), [creator.creator_id])

  const run = async () => {
    setRunning(true)
    try {
      await api_.detectPainPoints(creator.creator_id)
      notify('Pain points updated')
      pains.reload()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Detection failed', 'danger')
    } finally {
      setRunning(false)
    }
  }

  const list = pains.data?.pain_points ?? []
  const totalHits = list.reduce((sum, p) => sum + p.count, 0)

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">
          {list.length > 0
            ? `${list.length} recurring friction points found`
            : 'Surface the things your viewers keep complaining about'}
        </p>
        <Button
          variant="primary"
          loading={running}
          onClick={run}
          icon={<Icon path={Icons.sparkles} className="size-4" />}
        >
          Detect pain points
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {pains.loading ? (
          Array.from({ length: 3 }).map((_, i) => <StatTileSkeleton key={i} />)
        ) : (
          <>
            <StatTile
              label="Distinct pain points"
              value={list.length}
              hint="Unique complaint categories"
              tone="warning"
              icon={<Icon path={Icons.pains} className="size-4" />}
            />
            <StatTile
              label="Total signals"
              value={totalHits}
              hint="Comments matching a category"
              tone="danger"
              icon={<Icon path={Icons.alert} className="size-4" />}
            />
            <StatTile
              label="Most cited"
              value={list[0]?.label ?? '—'}
              hint={list[0] ? `${list[0].count} comments` : 'No signals yet'}
              icon={<Icon path={Icons.topics} className="size-4" />}
            />
          </>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader title="Complaint frequency" subtitle="Comments per category" />
          <div className="mt-5">
            {pains.loading ? (
              <div className="h-56 skeleton rounded-lg" />
            ) : pains.error ? (
              <ErrorState message={pains.error} onRetry={pains.reload} />
            ) : (
              <BarList
                data={list.map((p) => ({
                  label: p.label,
                  value: p.count,
                  color: 'var(--danger)',
                  meta: `${p.share}%`,
                }))}
                emptyMessage="No pain points detected yet."
              />
            )}
          </div>
        </Card>

        <Card className="lg:col-span-3" padded={false}>
          <div className="border-b border-line px-5 py-4">
            <CardHeader
              title="Pain points in detail"
              subtitle="With the comments that triggered each one"
              action={<Badge tone="danger">{list.length}</Badge>}
            />
          </div>

          {pains.loading ? (
            <div className="space-y-3 p-5">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-24 skeleton rounded-lg" />
              ))}
            </div>
          ) : pains.error ? (
            <ErrorState message={pains.error} onRetry={pains.reload} />
          ) : list.length === 0 ? (
            <EmptyState
              icon={<Icon path={Icons.pains} className="size-5" />}
              title="No complaints found"
              description="Either your audience is happy, or comments have not been analysed for sentiment yet."
            />
          ) : (
            <ul className="divide-y divide-line-subtle">
              {list.map((pain) => (
                <li key={pain.type} className="px-5 py-4 transition-colors hover:bg-inset">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-danger-soft text-danger">
                        <Icon path={Icons.alert} className="size-3.5" />
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-strong">
                          {pain.label}
                        </p>
                        <p className="mt-0.5 text-2xs text-muted">
                          {pain.count} comment{pain.count === 1 ? '' : 's'} mention this
                        </p>
                      </div>
                    </div>
                    <Badge tone="danger">{pain.share}%</Badge>
                  </div>

                  <ProgressBar
                    className="mt-3"
                    value={pain.share}
                    tone="bg-danger"
                  />

                  {pain.examples.length > 0 ? (
                    <ul className="mt-3 space-y-1.5 border-l-2 border-danger/30 pl-3">
                      {pain.examples.map((ex) => (
                        <li key={`${pain.type}-${ex.comment_id}`} className="line-clamp-2 text-2xs italic text-muted">
                          “{ex.text}”
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

export default PainPoints
