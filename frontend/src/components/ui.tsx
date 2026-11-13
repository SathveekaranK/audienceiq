import React from 'react'

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'subtle'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: React.ReactNode
}

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'bg-brand text-white shadow-xs hover:bg-brand-dark active:bg-brand-dark disabled:bg-brand/50',
  secondary:
    'bg-surface text-body border border-line shadow-xs hover:bg-subtle active:bg-subtle disabled:text-muted',
  ghost:
    'text-body hover:bg-subtle active:bg-subtle disabled:text-muted',
  subtle:
    'bg-brand-soft text-brand hover:bg-brand-100 active:bg-brand-100 disabled:text-brand/50',
  danger:
    'bg-danger text-white shadow-xs hover:bg-danger/90 active:bg-danger disabled:bg-danger/50',
}

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-3.5 text-sm gap-2',
  lg: 'h-11 px-5 text-sm gap-2',
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  className = '',
  children,
  disabled,
  ...rest
}) => (
  <button
    {...rest}
    disabled={disabled || loading}
    className={[
      'inline-flex items-center justify-center rounded-md font-medium whitespace-nowrap',
      'transition-colors duration-150 select-none',
      'disabled:cursor-not-allowed',
      BUTTON_VARIANTS[variant],
      BUTTON_SIZES[size],
      className,
    ].join(' ')}
  >
    {loading ? (
      <span
        className="inline-block size-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-r-transparent"
        aria-hidden="true"
      />
    ) : (
      icon
    )}
    {children}
  </button>
)

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  padded?: boolean
}

export const Card: React.FC<CardProps> = ({
  padded = true,
  className = '',
  children,
  ...rest
}) => (
  <div
    {...rest}
    className={[
      'rounded-card border border-line bg-surface shadow-card',
      padded ? 'p-5' : '',
      className,
    ].join(' ')}
  >
    {children}
  </div>
)

interface CardHeaderProps {
  title: React.ReactNode
  subtitle?: React.ReactNode
  action?: React.ReactNode
  className?: string
}

export const CardHeader: React.FC<CardHeaderProps> = ({
  title,
  subtitle,
  action,
  className = '',
}) => (
  <div className={['flex items-start justify-between gap-4', className].join(' ')}>
    <div className="min-w-0">
      <h3 className="text-[15px] font-semibold text-strong">{title}</h3>
      {subtitle ? (
        <p className="mt-0.5 text-xs text-muted">{subtitle}</p>
      ) : null}
    </div>
    {action ? <div className="shrink-0">{action}</div> : null}
  </div>
)

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------

type BadgeTone = 'neutral' | 'success' | 'danger' | 'warning' | 'info' | 'brand'

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: 'bg-neutral-soft text-muted',
  success: 'bg-success-soft text-success',
  danger: 'bg-danger-soft text-danger',
  warning: 'bg-warning-soft text-warning',
  info: 'bg-info-soft text-info',
  brand: 'bg-brand-soft text-brand',
}

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  dot?: boolean
}

export const Badge: React.FC<BadgeProps> = ({
  tone = 'neutral',
  dot = false,
  className = '',
  children,
  ...rest
}) => (
  <span
    {...rest}
    className={[
      'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5',
      'text-2xs font-semibold uppercase tracking-wide',
      BADGE_TONES[tone],
      className,
    ].join(' ')}
  >
    {dot ? <span className="size-1.5 rounded-full bg-current" /> : null}
    {children}
  </span>
)

// ---------------------------------------------------------------------------
// Stat tile
// ---------------------------------------------------------------------------

interface StatTileProps {
  label: string
  value: React.ReactNode
  hint?: React.ReactNode
  icon?: React.ReactNode
  tone?: 'default' | 'success' | 'danger' | 'warning' | 'brand'
  trend?: { value: string; direction: 'up' | 'down' | 'flat' }
  className?: string
}

const STAT_TONES = {
  default: 'text-body bg-subtle',
  success: 'text-success bg-success-soft',
  danger: 'text-danger bg-danger-soft',
  warning: 'text-warning bg-warning-soft',
  brand: 'text-brand bg-brand-soft',
} as const

export const StatTile: React.FC<StatTileProps> = ({
  label,
  value,
  hint,
  icon,
  tone = 'default',
  trend,
  className = '',
}) => (
  <Card className={className}>
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-xs font-medium text-muted">{label}</p>
        <p className="mt-2 text-2xl font-semibold tabular text-strong">{value}</p>
        {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
      </div>
      {icon ? (
        <span
          className={[
            'flex size-9 shrink-0 items-center justify-center rounded-md',
            STAT_TONES[tone],
          ].join(' ')}
        >
          {icon}
        </span>
      ) : null}
    </div>
    {trend ? (
      <div className="mt-3 flex items-center gap-1.5 border-t border-line-subtle pt-3">
        <TrendArrow direction={trend.direction} />
        <span className="text-xs font-medium text-muted">{trend.value}</span>
      </div>
    ) : null}
  </Card>
)

export const TrendArrow: React.FC<{ direction: 'up' | 'down' | 'flat' }> = ({
  direction,
}) => {
  const color =
    direction === 'up'
      ? 'text-success'
      : direction === 'down'
        ? 'text-danger'
        : 'text-muted'
  return (
    <svg
      className={`size-3.5 ${color}`}
      viewBox="0 0 12 12"
      fill="none"
      aria-hidden="true"
    >
      {direction === 'up' ? (
        <path d="M6 9.5V2.5M6 2.5L2.75 5.75M6 2.5l3.25 3.25" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      ) : direction === 'down' ? (
        <path d="M6 2.5v7M6 9.5L2.75 6.25M6 9.5l3.25-3.25" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <path d="M2.75 6h6.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      )}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------

interface ProgressBarProps {
  value: number
  max?: number
  tone?: string
  className?: string
  showLabel?: boolean
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  max = 100,
  tone = 'bg-brand',
  className = '',
  showLabel = false,
}) => {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  return (
    <div className={['flex items-center gap-2', className].join(' ')}>
      <div
        className="h-1.5 flex-1 overflow-hidden rounded-full bg-subtle"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${tone}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel ? (
        <span className="w-10 shrink-0 text-right text-xs tabular text-muted">
          {pct.toFixed(0)}%
        </span>
      ) : null}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className = '',
}) => (
  <div className={['flex flex-col items-center justify-center px-6 py-14 text-center', className].join(' ')}>
    {icon ? (
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-subtle text-muted">
        {icon}
      </div>
    ) : null}
    <h3 className="text-sm font-semibold text-strong">{title}</h3>
    {description ? (
      <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-muted">
        {description}
      </p>
    ) : null}
    {action ? <div className="mt-5">{action}</div> : null}
  </div>
)

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
  className?: string
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Something went wrong',
  message,
  onRetry,
  className = '',
}) => (
  <div
    className={[
      'flex flex-col items-center justify-center px-6 py-14 text-center',
      className,
    ].join(' ')}
  >
    <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-danger-soft text-danger">
      <svg className="size-6" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
    <h3 className="text-sm font-semibold text-strong">{title}</h3>
    <p className="mt-1.5 max-w-md text-xs leading-relaxed text-muted">{message}</p>
    {onRetry ? (
      <Button variant="secondary" className="mt-5" onClick={onRetry}>
        Try again
      </Button>
    ) : null}
  </div>
)

// ---------------------------------------------------------------------------
// Skeletons
// ---------------------------------------------------------------------------

export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={['skeleton rounded-md', className].join(' ')} />
)

export const StatTileSkeleton: React.FC = () => (
  <Card>
    <div className="flex items-start justify-between gap-3">
      <div className="w-full space-y-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-7 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
      <Skeleton className="size-9 shrink-0 rounded-md" />
    </div>
  </Card>
)

export const TableSkeleton: React.FC<{ rows?: number; cols?: number }> = ({
  rows = 5,
  cols = 4,
}) => (
  <div className="space-y-3 p-5">
    {Array.from({ length: rows }).map((_, r) => (
      <div key={r} className="flex gap-4">
        {Array.from({ length: cols }).map((_, c) => (
          <Skeleton key={c} className="h-4 flex-1" />
        ))}
      </div>
    ))}
  </div>
)

// ---------------------------------------------------------------------------
// Icon
// ---------------------------------------------------------------------------

interface IconProps {
  path: string
  className?: string
}

export const Icon: React.FC<IconProps> = ({ path, className = 'size-4' }) => (
  <svg
    className={className}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d={path} />
  </svg>
)

export const Icons = {
  overview:
    'M4 5a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5Zm9 0a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1V5ZM4 14a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-5Zm9 0a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1v-5Z',
  sentiment:
    'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4a1 1 0 1 1 0 2 1 1 0 0 1 0-2Zm-1 4h2v5h-2v-5Z',
  topics:
    'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 2.5a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13ZM8.5 12a1 1 0 1 0 0 2 1 1 0 0 0 0-2Zm3.5 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2Zm3.5 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z',
  segments:
    'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm14 10v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  pains:
    'M12 2 2 7v6c0 5 4.2 8.6 10 9.5 5.8-.9 10-4.5 10-9.5V7l-10-5Zm0 6v4m0 3h.01',
  content:
    'M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6.6L19 8.4V19a2 2 0 0 1-2 2ZM14 3v6h5',
  reports:
    'M4 4h11l5 5v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Zm3 9h6m-6 4h6m-6-8h2',
  videos:
    'M3 6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Zm14 3 4-2v10l-4-2V9Z',
  comments:
    'M21 12a8 8 0 0 1-8 8H7l-4 3v-5.5A8 8 0 1 1 21 12Z',
  plus: 'M12 5v14M5 12h14',
  trash:
    'M4 7h16M10 11v6m4-6v6M5 7l1 13a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1l1-13M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3',
  refresh:
    'M20 11A8 8 0 0 0 6.3 5.7L4 8m0 0V4m0 4h4m-4 5a8 8 0 0 0 13.7 5.3L20 16m0 0v4m0-4h-4',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm10 2-4.35-4.35',
  settings:
    'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7.4-3a7.4 7.4 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7.5 7.5 0 0 0-2-1.2L14.5 2h-4l-.4 2.6a7.5 7.5 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-1a7.5 7.5 0 0 0 2 1.2l.4 2.6h4l.4-2.6a7.5 7.5 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.06-.4.1-.8.1-1.2Z',
  logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4m7 14 5-5-5-5m5 5H9',
  chevronDown: 'm6 9 6 6 6-6',
  chevronRight: 'm9 6 6 6-6 6',
  arrowLeft: 'M19 12H5m7 7-7-7 7-7',
  play: 'm8 5 11 7-11 7V5Z',
  sparkles:
    'M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3Zm6.5 11 .8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2Z',
  download: 'M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2',
  filter: 'M3 5h18l-7 8v6l-4 2v-8L3 5Z',
  eye: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  layers: 'm12 2 9 5-9 5-9-5 9-5Zm9 10-9 5-9-5m18 5-9 5-9-5',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v5l3 2',
  check: 'm5 13 4 4L19 7',
  x: 'M6 6l12 12M18 6 6 18',
  alert: 'M12 9v4m0 4h.01M12 3 2 20h20L12 3Z',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v.01M11 12h1v4h1',
} as const
