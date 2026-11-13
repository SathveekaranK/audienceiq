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
import { SENTIMENT_COLORS } from '@/components/charts'
import { compactNumber, formatDate } from '@/lib/format'
import type { ViewProps } from './types'

const Videos: React.FC<ViewProps> = ({ creator, notify }) => {
  const [collecting, setCollecting] = useState<number | null>(null)
  const videos = useApi(() => api_.videos(creator.creator_id), [creator.creator_id])

  const collect = async (postId: number) => {
    setCollecting(postId)
    try {
      const result = await api_.collectComments(postId)
      notify(result.message)
      videos.reload()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Collection failed', 'danger')
    } finally {
      setCollecting(null)
    }
  }

  const list = videos.data?.videos ?? []
  const totalViews = list.reduce((sum, v) => sum + (v.view_count ?? 0), 0)
  const totalComments = list.reduce((sum, v) => sum + (v.comment_count ?? 0), 0)

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="grid gap-4 sm:grid-cols-3">
        {videos.loading ? (
          Array.from({ length: 3 }).map((_, i) => <StatTileSkeleton key={i} />)
        ) : (
          <>
            <StatTile
              label="Videos tracked"
              value={list.length}
              hint="In this channel"
              tone="brand"
              icon={<Icon path={Icons.videos} className="size-4" />}
            />
            <StatTile
              label="Total views"
              value={compactNumber(totalViews)}
              hint="Across all videos"
              icon={<Icon path={Icons.eye} className="size-4" />}
            />
            <StatTile
              label="Comments collected"
              value={totalComments.toLocaleString()}
              hint="Ready for analysis"
              tone="warning"
              icon={<Icon path={Icons.comments} className="size-4" />}
            />
          </>
        )}
      </div>

      <Card padded={false}>
        <div className="border-b border-line px-5 py-4">
          <CardHeader
            title="Your videos"
            subtitle="Performance and sentiment per video"
            action={<Badge tone="neutral">{list.length}</Badge>}
          />
        </div>

        {videos.loading ? (
          <TableSkeleton rows={5} cols={6} />
        ) : videos.error ? (
          <ErrorState message={videos.error} onRetry={videos.reload} />
        ) : list.length === 0 ? (
          <EmptyState
            icon={<Icon path={Icons.videos} className="size-5" />}
            title="No videos yet"
            description="Once comments are collected for a video it will show up here with its performance stats."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line bg-inset">
                  {['Video', 'Published', 'Views', 'Likes', 'Comments', 'Sentiment', ''].map((h, i) => (
                    <th
                      key={i}
                      className="whitespace-nowrap px-5 py-2.5 text-2xs font-semibold uppercase tracking-wide text-muted"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line-subtle">
                {list.map((video) => {
                  const sentimentTotal =
                    video.sentiment.positive +
                    video.sentiment.negative +
                    video.sentiment.neutral
                  const posPct = sentimentTotal
                    ? (video.sentiment.positive / sentimentTotal) * 100
                    : 0

                  return (
                    <tr key={video.post_id} className="transition-colors hover:bg-inset">
                      <td className="max-w-xs px-5 py-3">
                        <p className="truncate text-xs font-medium text-strong">
                          {video.title || 'Untitled video'}
                        </p>
                        {video.description ? (
                          <p className="mt-0.5 truncate text-2xs text-muted">
                            {video.description}
                          </p>
                        ) : null}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-xs text-muted">
                        {formatDate(video.published_at)}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-xs tabular text-body">
                        {compactNumber(video.view_count ?? 0)}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-xs tabular text-body">
                        {compactNumber(video.like_count ?? 0)}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-xs font-semibold tabular text-strong">
                        {video.comment_count}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3">
                        {sentimentTotal === 0 ? (
                          <span className="text-2xs text-subtle-text">Not analysed</span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-xs tabular text-body">
                            <span className="size-2 rounded-full" style={{ backgroundColor: SENTIMENT_COLORS.positive }} />
                            {posPct.toFixed(0)}% positive
                          </span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          loading={collecting === video.post_id}
                          onClick={() => collect(video.post_id)}
                          icon={<Icon path={Icons.download} className="size-3.5" />}
                        >
                          Collect
                        </Button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

export default Videos
