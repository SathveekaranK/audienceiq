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
  StatTile,
  StatTileSkeleton,
  TableSkeleton,
} from '@/components/ui'
import {
  ChartLegend,
  DonutChart,
  SENTIMENT_COLORS,
  TrendChart,
} from '@/components/charts'
import type { ViewProps } from './types'

type Range = 7 | 30 | 90 | 365

const RANGES: { value: Range; label: string }[] = [
  { value: 7, label: '7d' },
  { value: 30, label: '30d' },
  { value: 90, label: '90d' },
  { value: 365, label: '1y' },
]

const Sentiment: React.FC<ViewProps> = ({ creator, notify, onChanged }) => {
  const [range, setRange] = useState<Range>(30)
  const [running, setRunning] = useState(false)

  const distribution = useApi(
    () => api_.sentimentTimeseries(creator.creator_id, range),
    [creator.creator_id, range],
  )
  const summary = useApi(
    () => api_.dashboard(creator.creator_id),
    [creator.creator_id],
  )

  const runAnalysis = async () => {
    setRunning(true)
    try {
      const result = await api_.analyzeSentiment(creator.creator_id)
      notify(`Analysed ${result.analyzed} comments`)
      distribution.reload()
      summary.reload()
      onChanged()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Analysis failed', 'danger')
    } finally {
      setRunning(false)
    }
  }

  const sentiment = summary.data?.sentiment
  const series = distribution.data?.series ?? []

  const trendSeries = [
    {
      label: 'Positive',
      values: series.map((p) => p.positive),
    },
    {
      label: 'Neutral',
      values: series.map((p) => p.neutral),
    },
    {
      label: 'Negative',
      values: series.map((p) => p.negative),
    },
  ]

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-md border border-line bg-surface p-0.5">
          {RANGES.map((r) => (
            <button
              key={r.value}
              onClick={() => setRange(r.value)}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                range === r.value
                  ? 'bg-brand text-white'
                  : 'text-muted hover:bg-subtle hover:text-body'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>

        <Button
          variant="primary"
          loading={running}
          onClick={runAnalysis}
          icon={<Icon path={Icons.sparkles} className="size-4" />}
        >
          Analyse sentiment
        </Button>
      </div>

      {/* KPI row */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summary.loading ? (
          Array.from({ length: 4 }).map((_, i) => <StatTileSkeleton key={i} />)
        ) : (
          <>
            <StatTile
              label="Positive"
              value={`${sentiment?.positive_percent ?? 0}%`}
              hint={`${sentiment?.positive ?? 0} comments`}
              tone="success"
              icon={<Icon path={Icons.check} className="size-4" />}
            />
            <StatTile
              label="Neutral"
              value={`${sentiment?.neutral_percent ?? 0}%`}
              hint={`${sentiment?.neutral ?? 0} comments`}
              icon={<Icon path={Icons.info} className="size-4" />}
            />
            <StatTile
              label="Negative"
              value={`${sentiment?.negative_percent ?? 0}%`}
              hint={`${sentiment?.negative ?? 0} comments`}
              tone="danger"
              icon={<Icon path={Icons.alert} className="size-4" />}
            />
            <StatTile
              label="Total analysed"
              value={(sentiment?.analyzed ?? 0).toLocaleString()}
              hint={`${range} day window`}
              tone="brand"
              icon={<Icon path={Icons.sentiment} className="size-4" />}
            />
          </>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader
            title="Sentiment over time"
            subtitle="Daily volume by sentiment label"
          />
          <div className="mt-5">
            {distribution.loading ? (
              <div className="h-56 skeleton rounded-lg" />
            ) : distribution.error ? (
              <ErrorState message={distribution.error} onRetry={distribution.reload} />
            ) : series.length === 0 ? (
              <EmptyState
                icon={<Icon path={Icons.clock} className="size-5" />}
                title="No trend data"
                description="Comments collected outside this window, or sentiment has not been run yet."
              />
            ) : (
              <>
                <TrendChart
                  series={trendSeries}
                  labels={series.map((p) => p.date)}
                  colors={[
                    SENTIMENT_COLORS.positive,
                    SENTIMENT_COLORS.neutral,
                    SENTIMENT_COLORS.negative,
                  ]}
                />
                <div className="mt-4 border-t border-line-subtle pt-4">
                  <ChartLegend
                    items={[
                      { label: 'Positive', color: SENTIMENT_COLORS.positive },
                      { label: 'Neutral', color: SENTIMENT_COLORS.neutral },
                      { label: 'Negative', color: SENTIMENT_COLORS.negative },
                    ]}
                  />
                </div>
              </>
            )}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Overall split" subtitle="All analysed comments" />
          <div className="mt-5">
            {summary.loading ? (
              <div className="h-48 skeleton rounded-lg" />
            ) : (sentiment?.analyzed ?? 0) === 0 ? (
              <EmptyState
                icon={<Icon path={Icons.sentiment} className="size-5" />}
                title="Nothing analysed yet"
                description="Run the sentiment analysis to populate this chart."
              />
            ) : (
              <DonutChart
                data={[
                  { label: 'Positive', value: sentiment!.positive, color: SENTIMENT_COLORS.positive },
                  { label: 'Neutral', value: sentiment!.neutral, color: SENTIMENT_COLORS.neutral },
                  { label: 'Negative', value: sentiment!.negative, color: SENTIMENT_COLORS.negative },
                ]}
                centerValue={`${sentiment!.analyzed}`}
                centerLabel="comments"
                size={160}
                thickness={20}
              />
            )}
          </div>
        </Card>
      </div>

      {/* Daily breakdown table */}
      <Card padded={false}>
        <div className="border-b border-line px-5 py-4">
          <CardHeader
            title="Daily breakdown"
            subtitle="Every day with collected comments"
            action={<Badge tone="neutral">{series.length} days</Badge>}
          />
        </div>
        {distribution.loading ? (
          <TableSkeleton rows={4} cols={5} />
        ) : series.length === 0 ? (
          <EmptyState title="No daily data" description="Run the analysis to build a daily breakdown." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line bg-inset">
                  {['Date', 'Positive', 'Neutral', 'Negative', 'Total'].map((h) => (
                    <th
                      key={h}
                      className="whitespace-nowrap px-5 py-2.5 text-2xs font-semibold uppercase tracking-wide text-muted"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line-subtle">
                {[...series].reverse().map((point) => (
                  <tr key={point.date} className="transition-colors hover:bg-inset">
                    <td className="whitespace-nowrap px-5 py-2.5 text-xs font-medium text-body">
                      {point.date}
                    </td>
                    <td className="px-5 py-2.5 text-xs tabular text-success">
                      {point.positive}
                    </td>
                    <td className="px-5 py-2.5 text-xs tabular text-muted">
                      {point.neutral}
                    </td>
                    <td className="px-5 py-2.5 text-xs tabular text-danger">
                      {point.negative}
                    </td>
                    <td className="px-5 py-2.5 text-xs font-semibold tabular text-strong">
                      {point.total}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

export default Sentiment
