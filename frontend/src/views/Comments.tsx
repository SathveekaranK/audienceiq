import React, { useEffect, useMemo, useState } from 'react'
import { api_, type SentimentLabel } from '@/lib/api'
import { useApi } from '@/lib/hooks'
import {
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Icon,
  Icons,
  TableSkeleton,
} from '@/components/ui'
import { SENTIMENT_COLORS } from '@/components/charts'
import { formatDate } from '@/lib/format'
import type { ViewProps } from './types'

const FILTERS: { value: SentimentLabel | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'positive', label: 'Positive' },
  { value: 'neutral', label: 'Neutral' },
  { value: 'negative', label: 'Negative' },
  { value: 'unanalyzed', label: 'Not analysed' },
]

const PAGE_SIZE = 25

const Comments: React.FC<ViewProps> = ({ creator }) => {
  const [sentiment, setSentiment] = useState<SentimentLabel | 'all'>('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [offset, setOffset] = useState(0)

  // Debounce the search box so we do not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
      setOffset(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [search])

  const comments = useApi(
    () =>
      api_.comments(creator.creator_id, {
        sentiment: sentiment === 'all' ? undefined : sentiment,
        search: debouncedSearch || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [creator.creator_id, sentiment, debouncedSearch, offset],
  )

  const list = comments.data?.comments ?? []
  const total = comments.data?.total ?? 0

  const filterCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const c of list) {
      counts[c.sentiment] = (counts[c.sentiment] ?? 0) + 1
    }
    return counts
  }, [list])

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <Card padded={false}>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
          <CardHeader
            title="All comments"
            subtitle={`${total.toLocaleString()} matching comment${total === 1 ? '' : 's'}`}
          />

          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <div className="relative flex-1 sm:flex-none">
              <Icon
                path={Icons.search}
                className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-subtle-text"
              />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search comments…"
                aria-label="Search comments"
                className="h-8 w-full rounded-md border border-line bg-surface pl-8 pr-3 text-xs text-strong outline-none transition-shadow placeholder:text-subtle-text focus:border-brand focus:ring-2 focus:ring-brand/15 sm:w-56"
              />
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-line bg-inset px-5 py-2.5">
          {FILTERS.map((filter) => (
            <button
              key={filter.value}
              onClick={() => {
                setSentiment(filter.value)
                setOffset(0)
              }}
              className={`rounded px-2.5 py-1 text-xs font-medium capitalize transition-colors ${
                sentiment === filter.value
                  ? 'bg-brand text-white'
                  : 'text-muted hover:bg-subtle hover:text-body'
              }`}
            >
              {filter.label}
              {filter.value !== 'all' && filterCounts[filter.value] ? (
                <span className="ml-1.5 opacity-70">{filterCounts[filter.value]}</span>
              ) : null}
            </button>
          ))}
        </div>

        {comments.loading ? (
          <TableSkeleton rows={8} cols={4} />
        ) : comments.error ? (
          <ErrorState message={comments.error} onRetry={comments.reload} />
        ) : list.length === 0 ? (
          <EmptyState
            icon={<Icon path={Icons.comments} className="size-5" />}
            title="No comments found"
            description={
              debouncedSearch
                ? `Nothing matches “${debouncedSearch}”. Try a different search.`
                : 'Collect comments from a video to populate this list.'
            }
          />
        ) : (
          <ul className="divide-y divide-line-subtle">
            {list.map((comment) => (
              <li key={comment.comment_id} className="px-5 py-3.5 transition-colors hover:bg-inset">
                <div className="flex items-start gap-3">
                  <span
                    className="mt-1.5 size-2 shrink-0 rounded-full"
                    style={{
                      backgroundColor:
                        SENTIMENT_COLORS[comment.sentiment as keyof typeof SENTIMENT_COLORS] ??
                        SENTIMENT_COLORS.unanalyzed,
                    }}
                    title={comment.sentiment}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs leading-relaxed text-body">{comment.text}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-muted">
                      <span>{formatDate(comment.published_at)}</span>
                      <span>Video #{comment.post_id}</span>
                      {comment.like_count > 0 ? (
                        <span>{comment.like_count} likes</span>
                      ) : null}
                    </div>
                  </div>
                  <Badge
                    tone={
                      comment.sentiment === 'positive'
                        ? 'success'
                        : comment.sentiment === 'negative'
                          ? 'danger'
                          : comment.sentiment === 'neutral'
                            ? 'neutral'
                            : 'warning'
                    }
                  >
                    {comment.sentiment}
                  </Badge>
                </div>
              </li>
            ))}
          </ul>
        )}

        {/* Pagination */}
        {total > PAGE_SIZE ? (
          <div className="flex items-center justify-between border-t border-line px-5 py-3">
            <p className="text-2xs text-muted">
              Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                className="rounded-md border border-line px-2.5 py-1 text-xs font-medium text-body transition-colors hover:bg-subtle disabled:cursor-not-allowed disabled:text-subtle-text"
              >
                Previous
              </button>
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
                className="rounded-md border border-line px-2.5 py-1 text-xs font-medium text-body transition-colors hover:bg-subtle disabled:cursor-not-allowed disabled:text-subtle-text"
              >
                Next
              </button>
            </div>
          </div>
        ) : null}
      </Card>
    </div>
  )
}

export default Comments
