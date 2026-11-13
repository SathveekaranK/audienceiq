import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './api'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export interface AsyncResult<T> extends AsyncState<T> {
  reload: () => void
  setData: (updater: T | ((prev: T | null) => T)) => void
}

/**
 * Fetch data from the API with loading/error state and a manual reload.
 *
 * Requests are aborted if the component unmounts or the deps change, so
 * switching creators quickly cannot cause a stale response to overwrite
 * fresh data.
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): AsyncResult<T> {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: true,
    error: null,
  })

  const [nonce, setNonce] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    let cancelled = false
    setState((prev) => ({ ...prev, loading: true, error: null }))

    fetcherRef
      .current()
      .then((data) => {
        if (cancelled) return
        setState({ data, loading: false, error: null })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message =
          err instanceof ApiError
            ? err.detail
            : err instanceof Error
              ? err.message
              : 'Unexpected error'
        setState({ data: null, loading: false, error: message })
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  const setData = useCallback(
    (updater: T | ((prev: T | null) => T)) => {
      setState((prev) => ({
        ...prev,
        data:
          typeof updater === 'function'
            ? (updater as (p: T | null) => T)(prev.data)
            : updater,
      }))
    },
    [],
  )

  return { ...state, reload, setData }
}

/**
 * Track an async action (button press) with pending/error state.
 */
export function useAction<Args extends unknown[], R>(
  action: (...args: Args) => Promise<R>,
): {
  run: (...args: Args) => Promise<R | null>
  pending: boolean
  error: string | null
  clearError: () => void
} {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const run = useCallback(
    async (...args: Args) => {
      setPending(true)
      setError(null)
      try {
        const result = await action(...args)
        return result
      } catch (err: unknown) {
        const message =
          err instanceof ApiError
            ? err.detail
            : err instanceof Error
              ? err.message
              : 'Unexpected error'
        if (mounted.current) setError(message)
        return null
      } finally {
        if (mounted.current) setPending(false)
      }
    },
    [action],
  )

  const clearError = useCallback(() => setError(null), [])

  return { run, pending, error, clearError }
}
