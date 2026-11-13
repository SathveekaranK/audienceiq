import React, { useState } from 'react'
import { api_ } from '@/lib/api'
import { Button, Icon, Icons } from '@/components/ui'

type Mode = 'login' | 'register'

interface AuthScreenProps {
  onAuthenticated: (userId: number) => void
  /** When true the screen renders inline (inside a modal) instead of full page. */
  embedded?: boolean
}

const AuthScreen: React.FC<AuthScreenProps> = ({
  onAuthenticated,
  embedded = false,
}) => {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const switchMode = (next: Mode) => {
    setMode(next)
    setError(null)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setPending(true)
    setError(null)
    try {
      if (mode === 'register') {
        const result = await api_.register(username.trim(), email.trim(), password)
        onAuthenticated(result.user_id)
      } else {
        const result = await api_.login(username.trim(), password)
        onAuthenticated(result.user_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setPending(false)
    }
  }

  const brand = (
    <div className="mb-8 flex flex-col items-center text-center">
      <span className="flex size-11 items-center justify-center rounded-xl bg-brand text-white shadow-raised">
        <svg
          className="size-5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M13 10V3L4 14h7m6 4-7 7-7-7H5" />
        </svg>
      </span>
      <h1 className="mt-4 text-lg font-semibold text-strong">AudienceIQ</h1>
      <p className="mt-1 text-xs text-muted">
        Know what your audience actually thinks
      </p>
    </div>
  )

  const tabs = (
    <div className="mb-6 grid grid-cols-2 gap-1 rounded-md bg-subtle p-1">
      {(['login', 'register'] as Mode[]).map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => switchMode(m)}
          className={`rounded px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
            mode === m
              ? 'bg-surface text-strong shadow-xs'
              : 'text-muted hover:text-body'
          }`}
        >
          {m === 'login' ? 'Sign in' : 'Create account'}
        </button>
      ))}
    </div>
  )

  const form = (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label
          htmlFor="auth-username"
          className="mb-1.5 block text-xs font-medium text-body"
        >
          Username
        </label>
        <input
          id="auth-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="yourname"
          autoComplete="username"
          required
          className="h-9 w-full rounded-md border border-line bg-surface px-3 text-sm text-strong outline-none transition-shadow placeholder:text-subtle-text focus:border-brand focus:ring-2 focus:ring-brand/15"
        />
      </div>

      {mode === 'register' ? (
        <div>
          <label
            htmlFor="auth-email"
            className="mb-1.5 block text-xs font-medium text-body"
          >
            Email
          </label>
          <input
            id="auth-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            required
            className="h-9 w-full rounded-md border border-line bg-surface px-3 text-sm text-strong outline-none transition-shadow placeholder:text-subtle-text focus:border-brand focus:ring-2 focus:ring-brand/15"
          />
        </div>
      ) : null}

      <div>
        <label
          htmlFor="auth-password"
          className="mb-1.5 block text-xs font-medium text-body"
        >
          Password
        </label>
        <input
          id="auth-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          required
          className="h-9 w-full rounded-md border border-line bg-surface px-3 text-sm text-strong outline-none transition-shadow placeholder:text-subtle-text focus:border-brand focus:ring-2 focus:ring-brand/15"
        />
        {mode === 'register' ? (
          <p className="mt-1.5 text-2xs text-muted">At least 6 characters.</p>
        ) : null}
      </div>

      {error ? (
        <p className="flex items-start gap-2 rounded-md bg-danger-soft px-3 py-2 text-xs text-danger">
          <Icon path={Icons.alert} className="mt-px size-3.5 shrink-0" />
          {error}
        </p>
      ) : null}

      <Button
        type="submit"
        variant="primary"
        size="lg"
        loading={pending}
        className="w-full"
      >
        {mode === 'login' ? 'Sign in' : 'Create account'}
      </Button>
    </form>
  )

  if (embedded) {
    return (
      <div>
        {tabs}
        {form}
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-4 py-12">
      <div className="w-full max-w-sm">
        {brand}
        <div className="rounded-xl border border-line bg-surface p-6 shadow-card">
          {tabs}
          {form}
        </div>
        <p className="mt-6 text-center text-2xs text-muted">
          AudienceIQ · AI-powered audience intelligence
        </p>
      </div>
    </div>
  )
}

export default AuthScreen
