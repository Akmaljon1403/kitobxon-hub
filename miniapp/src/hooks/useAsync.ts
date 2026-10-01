import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../services/api'

export type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'success'; data: T }

/** Runs an async loader on mount and exposes loading / error / success states plus a reload function. */
export function useAsync<T>(loader: (signal: AbortSignal) => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })
    loader(controller.signal)
      .then((data) => setState({ status: 'success', data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({
          status: 'error',
          error: error instanceof ApiError ? error : new ApiError('UNKNOWN', "Kutilmagan xatolik yuz berdi.", 0),
        })
      })
    return () => controller.abort()
  }, [attempt, ...deps])

  const reload = useCallback(() => setAttempt((value) => value + 1), [])
  return { state, reload }
}
