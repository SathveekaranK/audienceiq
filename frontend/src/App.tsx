import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api_, type Creator } from '@/lib/api'
import { useApi } from '@/lib/hooks'
import { Sidebar, TopBar, NAV_ITEMS, type ViewKey } from '@/components/Layout'
import { Button, Icon, Icons } from '@/components/ui'
import { Modal, Toast } from '@/components/feedback'
import Overview from '@/views/Overview'
import Sentiment from '@/views/Sentiment'
import Emotions from '@/views/Emotions'
import Topics from '@/views/Topics'
import Segments from '@/views/Segments'
import PainPoints from '@/views/PainPoints'
import ContentIdeas from '@/views/ContentIdeas'
import VideoLab from '@/views/VideoLab'
import Videos from '@/views/Videos'
import Comments from '@/views/Comments'
import Reports from '@/views/Reports'
import AuthScreen from '@/views/AuthScreen'

const VIEW_META: Record<ViewKey, { title: string; subtitle: string }> = {
  overview: { title: 'Overview', subtitle: 'A snapshot of how your audience is reacting' },
  sentiment: { title: 'Sentiment', subtitle: 'How viewers feel about your content, over time' },
  emotions: {
    title: 'Emotions',
    subtitle: 'Whether viewers were influenced, triggered, or simply hate it',
  },
  topics: { title: 'Topics', subtitle: 'What your audience is actually talking about' },
  segments: { title: 'Audience Segments', subtitle: 'Distinct groups of viewers and what unites them' },
  'pain-points': { title: 'Pain Points', subtitle: 'Recurring complaints and friction points' },
  content: { title: 'Content Ideas', subtitle: 'What your audience is asking you to make next' },
  'video-lab': {
    title: 'Analyse a Video',
    subtitle: 'Paste a YouTube link and analyse its real comments',
  },
  videos: { title: 'Videos', subtitle: 'Performance across your uploaded content' },
  comments: { title: 'Comments', subtitle: 'Browse and filter every comment collected' },
  reports: { title: 'Reports', subtitle: 'Saved snapshots you can compare over time' },
}

const App: React.FC = () => {
  const [view, setView] = useState<ViewKey>('overview')
  const [creatorId, setCreatorId] = useState<number | null>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [addCreatorOpen, setAddCreatorOpen] = useState(false)
  const [manageOpen, setManageOpen] = useState(false)
  const [authOpen, setAuthOpen] = useState(false)
  const [signedIn, setSignedIn] = useState(
    () => window.localStorage.getItem('aiq_signed_in') === '1',
  )
  const [toast, setToast] = useState<{ message: string; tone: 'success' | 'danger' } | null>(null)

  const creatorsQuery = useApi(() => api_.listCreators(), [])
  const creators = useMemo(() => creatorsQuery.data?.creators ?? [], [creatorsQuery.data])

  // Auto-select the first creator once the list loads.
  useEffect(() => {
    if (creatorId === null && creators.length > 0) {
      setCreatorId(creators[0].creator_id)
    }
    if (creatorId !== null && creators.length > 0) {
      const stillExists = creators.some((c) => c.creator_id === creatorId)
      if (!stillExists) setCreatorId(creators[0].creator_id)
    }
  }, [creators, creatorId])

  const creator = useMemo(
    () => creators.find((c) => c.creator_id === creatorId) ?? null,
    [creators, creatorId],
  )

  const notify = useCallback((message: string, tone: 'success' | 'danger' = 'success') => {
    setToast({ message, tone })
  }, [])

  const handleDeleteCreator = useCallback(
    async (id: number) => {
      try {
        await api_.deleteCreator(id)
        notify('Channel deleted')
        creatorsQuery.reload()
      } catch (err) {
        notify(err instanceof Error ? err.message : 'Delete failed', 'danger')
      }
    },
    [creatorsQuery, notify],
  )

  const meta = VIEW_META[view]

  const renderView = () => {
    if (!creator) {
      return (
        <div className="flex h-full items-center justify-center p-8">
          <div className="max-w-md text-center">
            <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-brand-soft text-brand">
              <Icon path={Icons.layers} className="size-6" />
            </div>
            <h2 className="text-base font-semibold text-strong">Add a channel to get started</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              Connect a YouTube channel and AudienceIQ will collect its comments,
              measure sentiment, find topics and group your viewers.
            </p>
            <Button variant="primary" className="mt-6" onClick={() => setAddCreatorOpen(true)}>
              <Icon path={Icons.plus} className="size-4" />
              Add a channel
            </Button>
          </div>
        </div>
      )
    }

    const shared = { creator, onChanged: creatorsQuery.reload, notify, selectCreator: setCreatorId }

    switch (view) {
      case 'overview':
        return <Overview {...shared} />
      case 'sentiment':
        return <Sentiment {...shared} />
      case 'emotions':
        return <Emotions {...shared} />
      case 'topics':
        return <Topics {...shared} />
      case 'segments':
        return <Segments {...shared} />
      case 'pain-points':
        return <PainPoints {...shared} />
      case 'content':
        return <ContentIdeas {...shared} />
      case 'video-lab':
        return <VideoLab {...shared} />
      case 'videos':
        return <Videos {...shared} />
      case 'comments':
        return <Comments {...shared} />
      case 'reports':
        return <Reports {...shared} />
      default:
        return null
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-page">
      <Sidebar
        view={view}
        onViewChange={setView}
        creator={creator}
        creators={creators}
        onSelectCreator={setCreatorId}
        onAddCreator={() => setAddCreatorOpen(true)}
        onManageCreator={() => setManageOpen(true)}
        onToggleAuth={() => setAuthOpen(true)}
        signedIn={signedIn}
        mobileOpen={mobileNavOpen}
        onCloseMobile={() => setMobileNavOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={meta.title}
          subtitle={meta.subtitle}
          onOpenMobile={() => setMobileNavOpen(true)}
          actions={
            creator ? (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={creatorsQuery.reload}
                  icon={<Icon path={Icons.refresh} className="size-3.5" />}
                  aria-label="Refresh"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setAddCreatorOpen(true)}
                  icon={<Icon path={Icons.plus} className="size-3.5" />}
                >
                  <span className="hidden sm:inline">Add channel</span>
                </Button>
              </>
            ) : null
          }
        />

        <main className="flex-1 overflow-y-auto scrollbar-thin">
          {creatorsQuery.loading ? (
            <div className="p-6">
              <p className="text-sm text-muted">Loading workspace…</p>
            </div>
          ) : creatorsQuery.error ? (
            <div className="flex h-full items-center justify-center p-8">
              <div className="max-w-md text-center">
                <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-danger-soft text-danger">
                  <Icon path={Icons.alert} className="size-6" />
                </div>
                <h2 className="text-base font-semibold text-strong">Cannot reach the backend</h2>
                <p className="mt-2 text-sm leading-relaxed text-muted">{creatorsQuery.error}</p>
                <Button variant="primary" className="mt-6" onClick={creatorsQuery.reload}>
                  Try again
                </Button>
              </div>
            </div>
          ) : (
            <div key={`${view}-${creatorId}`} className="animate-fade-in">
              {renderView()}
            </div>
          )}
        </main>
      </div>

      <AddCreatorModal
        open={addCreatorOpen}
        onClose={() => setAddCreatorOpen(false)}
        onAdded={(newCreator) => {
          setAddCreatorOpen(false)
          creatorsQuery.reload()
          setCreatorId(newCreator.creator_id)
          notify(`Added ${newCreator.name}`)
        }}
      />

      {creator ? (
        <ManageCreatorModal
          creator={creator}
          open={manageOpen}
          onClose={() => setManageOpen(false)}
          onDeleted={() => {
            setManageOpen(false)
            handleDeleteCreator(creator.creator_id)
          }}
        />
      ) : null}

      <Modal
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        title="Account"
        description="Sign in to sync your workspace across devices"
      >
        <AuthScreen
          embedded
          onAuthenticated={(userId) => {
            setAuthOpen(false)
            setSignedIn(true)
            window.localStorage.setItem('aiq_signed_in', '1')
            notify(`Signed in as user #${userId}`)
          }}
        />
      </Modal>

      {toast ? (
        <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} />
      ) : null}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Add creator modal
// ---------------------------------------------------------------------------

const AddCreatorModal: React.FC<{
  open: boolean
  onClose: () => void
  onAdded: (creator: Creator) => void
}> = ({ open, onClose, onAdded }) => {
  const [name, setName] = useState('')
  const [handle, setHandle] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setName('')
      setHandle('')
      setError(null)
    }
  }, [open])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Channel name is required')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const result = await api_.addCreator(name.trim(), handle.trim())
      const list = await api_.listCreators()
      const created =
        list.creators.find((c) => c.creator_id === result.creator_id) ??
        list.creators[list.creators.length - 1]
      if (created) onAdded(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add the channel')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add a channel">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="creator-name" className="mb-1.5 block text-xs font-medium text-body">
            Channel name
          </label>
          <input
            id="creator-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="TechTalks Daily"
            autoFocus
            className="h-9 w-full rounded-md border border-line bg-surface px-3 text-sm text-strong outline-none transition-shadow placeholder:text-subtle-text focus:border-brand focus:ring-2 focus:ring-brand/15"
          />
        </div>

        <div>
          <label htmlFor="creator-handle" className="mb-1.5 block text-xs font-medium text-body">
            Channel handle <span className="font-normal text-muted">(optional)</span>
          </label>
          <input
            id="creator-handle"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            placeholder="@techtalksdaily"
            className="h-9 w-full rounded-md border border-line bg-surface px-3 text-sm text-strong outline-none transition-shadow placeholder:text-subtle-text focus:border-brand focus:ring-2 focus:ring-brand/15"
          />
          <p className="mt-1.5 text-2xs text-muted">
            Links comments to this channel. Use a unique handle so repeated
            additions reuse the same channel.
          </p>
        </div>

        {error ? (
          <p className="flex items-start gap-2 rounded-md bg-danger-soft px-3 py-2 text-xs text-danger">
            <Icon path={Icons.alert} className="mt-px size-3.5 shrink-0" />
            {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={saving}>
            Add channel
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Manage creator modal
// ---------------------------------------------------------------------------

const ManageCreatorModal: React.FC<{
  creator: Creator
  open: boolean
  onClose: () => void
  onDeleted: () => void
}> = ({ creator, open, onClose, onDeleted }) => {
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    if (!open) setConfirming(false)
  }, [open])

  return (
    <Modal
      open={open && !confirming}
      onClose={onClose}
      title={creator.name}
      description="Channel details and data management"
    >
      <dl className="divide-y divide-line-subtle rounded-lg border border-line bg-inset">
        {[
          ['Handle', creator.handle || '—'],
          ['Platform', creator.platform_type],
          ['Videos', creator.stats.videos.toLocaleString()],
          ['Comments', creator.stats.comments.toLocaleString()],
          ['Segments', creator.stats.segments.toLocaleString()],
          ['Reports', creator.stats.reports.toLocaleString()],
        ].map(([label, value]) => (
          <div key={label} className="flex items-center justify-between px-4 py-2.5">
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="text-xs font-medium capitalize text-strong">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
        <Button
          variant="danger"
          onClick={() => setConfirming(true)}
          icon={<Icon path={Icons.trash} className="size-3.5" />}
        >
          Delete channel
        </Button>
      </div>

      <Modal
        open={confirming}
        onClose={() => setConfirming(false)}
        title={`Delete ${creator.name}?`}
      >
        <p className="text-sm leading-relaxed text-body">
          This permanently removes the channel along with every video, comment,
          sentiment result, topic, segment and report associated with it.
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={onDeleted}
            icon={<Icon path={Icons.trash} className="size-3.5" />}
          >
            Delete permanently
          </Button>
        </div>
      </Modal>
    </Modal>
  )
}

export default App
