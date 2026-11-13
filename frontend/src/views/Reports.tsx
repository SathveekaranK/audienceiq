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
import { Modal } from '@/components/feedback'
import { formatDate } from '@/lib/format'
import type { ViewProps } from './types'

function isoDate(offsetDays = 0): string {
  const date = new Date()
  date.setDate(date.getDate() + offsetDays)
  return date.toISOString().slice(0, 10)
}

const Reports: React.FC<ViewProps> = ({ creator, notify }) => {
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')
  const [from, setFrom] = useState(isoDate(-30))
  const [to, setTo] = useState(isoDate(0))

  const reports = useApi(() => api_.reports(creator.creator_id), [creator.creator_id])
  const list = reports.data?.reports ?? []

  const generate = async () => {
    if (!name.trim()) {
      notify('Give the report a name first', 'danger')
      return
    }
    setSaving(true)
    try {
      await api_.generateReport(creator.creator_id, name.trim(), from, to)
      notify('Report generated')
      setModalOpen(false)
      setName('')
      reports.reload()
    } catch (err) {
      notify(err instanceof Error ? err.message : 'Could not generate the report', 'danger')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">
          {list.length > 0
            ? `${list.length} saved report${list.length === 1 ? '' : 's'}`
            : 'Snapshot your analysis so you can compare it later'}
        </p>
        <Button
          variant="primary"
          onClick={() => setModalOpen(true)}
          icon={<Icon path={Icons.plus} className="size-4" />}
        >
          New report
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {reports.loading ? (
          Array.from({ length: 3 }).map((_, i) => <StatTileSkeleton key={i} />)
        ) : (
          <>
            <StatTile
              label="Reports saved"
              value={list.length}
              hint="Snapshots of your analysis"
              tone="brand"
              icon={<Icon path={Icons.reports} className="size-4" />}
            />
            <StatTile
              label="Comments covered"
              value={list.reduce((sum, r) => sum + (r.total_comments ?? 0), 0).toLocaleString()}
              hint="Across all reports"
              icon={<Icon path={Icons.comments} className="size-4" />}
            />
            <StatTile
              label="Latest report"
              value={list.length > 0 ? formatDate(list[0].generated_at) : '—'}
              hint={list.length > 0 ? list[0].report_name : 'No reports yet'}
              icon={<Icon path={Icons.clock} className="size-4" />}
            />
          </>
        )}
      </div>

      <Card padded={false}>
        <div className="border-b border-line px-5 py-4">
          <CardHeader
            title="Saved reports"
            subtitle="Compare how your audience changes over time"
          />
        </div>

        {reports.loading ? (
          <TableSkeleton rows={4} cols={5} />
        ) : reports.error ? (
          <ErrorState message={reports.error} onRetry={reports.reload} />
        ) : list.length === 0 ? (
          <EmptyState
            icon={<Icon path={Icons.reports} className="size-5" />}
            title="No reports yet"
            description="Generate a report to freeze the current analysis, then generate another later to spot changes."
            action={
              <Button variant="primary" onClick={() => setModalOpen(true)}>
                <Icon path={Icons.plus} className="size-4" />
                New report
              </Button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line bg-inset">
                  {['Report', 'Date range', 'Comments', 'Generated', ''].map((h, i) => (
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
                {list.map((report) => (
                  <tr key={report.report_id} className="transition-colors hover:bg-inset">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-brand-soft text-brand">
                          <Icon path={Icons.reports} className="size-3.5" />
                        </span>
                        <span className="truncate text-xs font-medium text-strong">
                          {report.report_name}
                        </span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-xs text-muted">
                      {formatDate(report.date_from)} → {formatDate(report.date_to)}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-xs font-semibold tabular text-strong">
                      {report.total_comments}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-xs text-muted">
                      {formatDate(report.generated_at)}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-right">
                      <Badge tone="neutral">#{report.report_id}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Generate a report"
        description="Freeze the current analysis for a date range."
      >
        <div className="space-y-4">
          <div>
            <label htmlFor="report-name" className="mb-1.5 block text-xs font-medium text-body">
              Report name
            </label>
            <input
              id="report-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Q1 Audience Review"
              autoFocus
              className="h-9 w-full rounded-md border border-line bg-surface px-3 text-sm text-strong outline-none transition-shadow placeholder:text-subtle-text focus:border-brand focus:ring-2 focus:ring-brand/15"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="report-from" className="mb-1.5 block text-xs font-medium text-body">
                From
              </label>
              <input
                id="report-from"
                type="date"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                className="h-9 w-full rounded-md border border-line bg-surface px-3 text-sm text-strong outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
            <div>
              <label htmlFor="report-to" className="mb-1.5 block text-xs font-medium text-body">
                To
              </label>
              <input
                id="report-to"
                type="date"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                className="h-9 w-full rounded-md border border-line bg-surface px-3 text-sm text-strong outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" loading={saving} onClick={generate}>
              Generate report
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default Reports
