import React, { useEffect } from 'react'
import { Button, Icon, Icons } from './ui'

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  description?: string
  children: React.ReactNode
  width?: string
}

export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  description,
  children,
  width = 'max-w-md',
}) => {
  useEffect(() => {
    if (!open) return

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/45 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`relative w-full ${width} animate-fade-in rounded-xl border border-line bg-surface shadow-overlay`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-strong">{title}</h2>
            {description ? (
              <p className="mt-0.5 text-xs text-muted">{description}</p>
            ) : null}
          </div>
          <button
            onClick={onClose}
            className="-mr-1 shrink-0 rounded-md p-1.5 text-muted transition-colors hover:bg-subtle"
            aria-label="Close dialog"
          >
            <Icon path={Icons.x} className="size-4" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

interface ToastProps {
  message: string
  tone?: 'success' | 'danger'
  onClose: () => void
}

export const Toast: React.FC<ToastProps> = ({ message, tone = 'success', onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000)
    return () => clearTimeout(timer)
  }, [message, onClose])

  const isSuccess = tone === 'success'

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-5 right-5 z-[110] flex max-w-sm animate-slide-in items-start gap-3 rounded-lg border border-line bg-surface px-4 py-3 shadow-overlay"
    >
      <span
        className={`mt-px flex size-5 shrink-0 items-center justify-center rounded-full ${
          isSuccess ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'
        }`}
      >
        <Icon path={isSuccess ? Icons.check : Icons.alert} className="size-3" />
      </span>
      <p className="flex-1 text-xs leading-relaxed text-body">{message}</p>
      <button
        onClick={onClose}
        className="-mr-1 shrink-0 rounded p-1 text-muted transition-colors hover:bg-subtle"
        aria-label="Dismiss"
      >
        <Icon path={Icons.x} className="size-3" />
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Confirm dialog
// ---------------------------------------------------------------------------

interface ConfirmProps {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  tone?: 'danger' | 'primary'
  onConfirm: () => void
  onCancel: () => void
}

export const Confirm: React.FC<ConfirmProps> = ({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  tone = 'primary',
  onConfirm,
  onCancel,
}) => (
  <Modal open={open} onClose={onCancel} title={title}>
    <p className="text-sm leading-relaxed text-body">{message}</p>
    <div className="mt-6 flex justify-end gap-2">
      <Button variant="ghost" onClick={onCancel}>
        Cancel
      </Button>
      <Button variant={tone === 'danger' ? 'danger' : 'primary'} onClick={onConfirm}>
        {confirmLabel}
      </Button>
    </div>
  </Modal>
)

// ---------------------------------------------------------------------------
// Button (re-exported for convenience so views only import one module)
// ---------------------------------------------------------------------------

export { Button }
