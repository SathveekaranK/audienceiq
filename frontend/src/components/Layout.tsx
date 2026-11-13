import React, { useEffect, useMemo, useState } from 'react'
import { api_, type Creator } from '@/lib/api'
import { useApi } from '@/lib/hooks'
import { Badge, Button, Icon, Icons } from '@/components/ui'

// ---------------------------------------------------------------------------
// Navigation definition
// ---------------------------------------------------------------------------

export type ViewKey =
  | 'overview'
  | 'sentiment'
  | 'emotions'
  | 'topics'
  | 'segments'
  | 'pain-points'
  | 'content'
  | 'video-lab'
  | 'videos'
  | 'comments'
  | 'reports'

interface NavItem {
  key: ViewKey
  label: string
  icon: string
  group: 'Insights' | 'Content' | 'Workspace'
}

export const NAV_ITEMS: NavItem[] = [
  { key: 'overview', label: 'Overview', icon: Icons.overview, group: 'Insights' },
  { key: 'sentiment', label: 'Sentiment', icon: Icons.sentiment, group: 'Insights' },
  { key: 'emotions', label: 'Emotions', icon: Icons.sparkles, group: 'Insights' },
  { key: 'topics', label: 'Topics', icon: Icons.topics, group: 'Insights' },
  { key: 'segments', label: 'Segments', icon: Icons.segments, group: 'Insights' },
  { key: 'pain-points', label: 'Pain Points', icon: Icons.pains, group: 'Insights' },
  { key: 'content', label: 'Content Ideas', icon: Icons.content, group: 'Insights' },
  { key: 'video-lab', label: 'Analyse Video', icon: Icons.download, group: 'Content' },
  { key: 'videos', label: 'Videos', icon: Icons.videos, group: 'Content' },
  { key: 'comments', label: 'Comments', icon: Icons.comments, group: 'Content' },
  { key: 'reports', label: 'Reports', icon: Icons.reports, group: 'Workspace' },
]

export const NAV_GROUPS = ['Insights', 'Content', 'Workspace'] as const

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

interface SidebarProps {
  view: ViewKey
  onViewChange: (view: ViewKey) => void
  creator: Creator | null
  creators: Creator[]
  onSelectCreator: (id: number) => void
  onAddCreator: () => void
  onManageCreator: () => void
  onToggleAuth: () => void
  signedIn: boolean
  mobileOpen: boolean
  onCloseMobile: () => void
}

const Sidebar: React.FC<SidebarProps> = ({
  view,
  onViewChange,
  creator,
  creators,
  onSelectCreator,
  onAddCreator,
  onManageCreator,
  onToggleAuth,
  signedIn,
  mobileOpen,
  onCloseMobile,
}) => {
  const [pickerOpen, setPickerOpen] = useState(false)

  const grouped = useMemo(() => {
    const map: Record<string, NavItem[]> = {}
    for (const item of NAV_ITEMS) {
      ;(map[item.group] ||= []).push(item)
    }
    return map
  }, [])

  const handleNav = (key: ViewKey) => {
    onViewChange(key)
    onCloseMobile()
  }

  return (
    <>
      {mobileOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px] lg:hidden"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      ) : null}

      <aside
        className={[
          'fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col border-r border-line bg-surface transition-transform duration-200 lg:translate-x-0 lg:static lg:z-auto',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        ].join(' ')}
      >
        {/* Brand */}
        <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-line px-5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-brand text-white">
            <svg className="size-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M13 10V3L4 14h7m6 4-7 7-7-7H5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-strong">AudienceIQ</p>
            <p className="truncate text-2xs text-muted">Audience Intelligence</p>
          </div>
          <button
            onClick={onCloseMobile}
            className="ml-auto rounded-md p-1.5 text-muted hover:bg-subtle lg:hidden"
            aria-label="Close navigation"
          >
            <Icon path={Icons.x} className="size-4" />
          </button>
        </div>

        {/* Creator picker */}
        <div className="relative shrink-0 border-b border-line p-3">
          <button
            onClick={() => setPickerOpen((o) => !o)}
            className="flex w-full items-center gap-2.5 rounded-md border border-line bg-surface px-2.5 py-2 text-left transition-colors hover:bg-subtle"
          >
            <span className="flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-brand-soft text-2xs font-semibold text-brand">
              {creator?.profile_image ? (
                <img src={creator.profile_image} alt="" className="size-full object-cover" />
              ) : (
                (creator?.name ?? 'A').slice(0, 1).toUpperCase()
              )}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-semibold text-strong">
                {creator?.name ?? 'No creator selected'}
              </span>
              <span className="block truncate text-2xs text-muted">
                {creator ? `${creator.stats.videos} videos · ${creator.stats.comments} comments` : 'Add a channel to begin'}
              </span>
            </span>
            <Icon
              path={Icons.chevronDown}
              className={`size-3.5 shrink-0 text-muted transition-transform ${pickerOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {pickerOpen ? (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setPickerOpen(false)} aria-hidden="true" />
              <div className="absolute left-3 right-3 top-[calc(100%-4px)] z-20 animate-fade-in overflow-hidden rounded-md border border-line bg-surface shadow-overlay">
                <div className="max-h-64 overflow-y-auto scrollbar-thin p-1">
                  {creators.length === 0 ? (
                    <p className="px-3 py-3 text-xs text-muted">No channels yet.</p>
                  ) : (
                    creators.map((c) => (
                      <button
                        key={c.creator_id}
                        onClick={() => {
                          onSelectCreator(c.creator_id)
                          setPickerOpen(false)
                        }}
                        className={`flex w-full items-center gap-2.5 rounded px-2.5 py-2 text-left transition-colors hover:bg-subtle ${
                          creator?.creator_id === c.creator_id ? 'bg-brand-soft' : ''
                        }`}
                      >
                        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-subtle text-2xs font-semibold text-muted">
                          {c.name.slice(0, 1).toUpperCase()}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-xs font-medium text-strong">{c.name}</span>
                          <span className="block truncate text-2xs text-muted">{c.stats.comments} comments</span>
                        </span>
                        {creator?.creator_id === c.creator_id ? (
                          <Icon path={Icons.check} className="size-3.5 shrink-0 text-brand" />
                        ) : null}
                      </button>
                    ))
                  )}
                </div>
                <button
                  onClick={() => {
                    setPickerOpen(false)
                    onAddCreator()
                  }}
                  className="flex w-full items-center gap-2 border-t border-line px-3 py-2.5 text-xs font-medium text-brand transition-colors hover:bg-brand-soft"
                >
                  <Icon path={Icons.plus} className="size-3.5" />
                  Add a channel
                </button>
                {creator ? (
                  <button
                    onClick={() => {
                      setPickerOpen(false)
                      onManageCreator()
                    }}
                    className="flex w-full items-center gap-2 border-t border-line px-3 py-2.5 text-xs font-medium text-muted transition-colors hover:bg-subtle hover:text-body"
                  >
                    <Icon path={Icons.settings} className="size-3.5" />
                    Manage this channel
                  </button>
                ) : null}
              </div>
            </>
          ) : null}
        </div>
        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto scrollbar-thin p-3">
          {NAV_GROUPS.map((group) => (
            <div key={group} className="mb-5 last:mb-0">
              <p className="mb-1.5 px-2.5 text-2xs font-semibold uppercase tracking-wider text-subtle-text">
                {group}
              </p>
              <ul className="space-y-0.5">
                {grouped[group]?.map((item) => {
                  const active = view === item.key
                  return (
                    <li key={item.key}>
                      <button
                        onClick={() => handleNav(item.key)}
                        aria-current={active ? 'page' : undefined}
                        className={[
                          'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-xs font-medium transition-colors',
                          active
                            ? 'bg-brand-soft text-brand'
                            : 'text-body hover:bg-subtle',
                        ].join(' ')}
                      >
                        <Icon path={item.icon} className="size-4 shrink-0" />
                        {item.label}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="shrink-0 border-t border-line p-3">
          <button
            onClick={onToggleAuth}
            className="mb-2 flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors hover:bg-subtle"
          >
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-subtle text-2xs font-semibold text-muted">
              <Icon path={signedIn ? Icons.check : Icons.logout} className="size-3.5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-medium text-strong">
                {signedIn ? 'Signed in' : 'Sign in'}
              </span>
              <span className="block truncate text-2xs text-muted">
                {signedIn ? 'Session active' : 'Optional for local use'}
              </span>
            </span>
          </button>

          <div className="flex items-center justify-between gap-2 rounded-md bg-subtle px-3 py-2">
            <div className="min-w-0">
              <p className="text-2xs font-medium text-muted">API Status</p>
              <p className="flex items-center gap-1.5 text-2xs font-semibold text-success">
                <span className="size-1.5 rounded-full bg-success" />
                Connected
              </p>
            </div>
            <Badge tone="neutral">v1.0</Badge>
          </div>
        </div>
      </aside>
    </>
  )
}

// ---------------------------------------------------------------------------
// Top bar
// ---------------------------------------------------------------------------

interface TopBarProps {
  title: string
  subtitle?: string
  onOpenMobile: () => void
  actions?: React.ReactNode
}

const TopBar: React.FC<TopBarProps> = ({ title, subtitle, onOpenMobile, actions }) => (
  <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-4 border-b border-line bg-surface/85 px-4 backdrop-blur-md sm:px-6">
    <button
      onClick={onOpenMobile}
      className="rounded-md p-2 text-muted transition-colors hover:bg-subtle lg:hidden"
      aria-label="Open navigation"
    >
      <svg className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>

    <div className="min-w-0 flex-1">
      <h1 className="truncate text-base font-semibold text-strong">{title}</h1>
      {subtitle ? <p className="truncate text-xs text-muted">{subtitle}</p> : null}
    </div>

    {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
  </header>
)

export default Sidebar
export { Sidebar, TopBar }
