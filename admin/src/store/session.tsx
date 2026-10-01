import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { ApiError, apiRequest, type RequestOptions } from '../services/api'
import type { AdminSelf, TokenResponse } from '../types/api'

const TOKEN_KEY = 'kitobxon.admin.token'

type SessionState =
  | { kind: 'loading' }
  | { kind: 'signed_out'; message?: string }
  | { kind: 'signed_in'; admin: AdminSelf }

interface SessionValue {
  state: SessionState
  admin: AdminSelf | null
  can: (permission: string) => boolean
  api: <T>(path: string, options?: Omit<RequestOptions, 'token'>) => Promise<T>
  loginWithLink: (token: string) => Promise<void>
  logout: () => Promise<void>
}

const SessionContext = createContext<SessionValue | null>(null)

function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function writeToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // ignore: the session then lasts until the tab is reloaded
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readToken)
  const [state, setState] = useState<SessionState>({ kind: 'loading' })

  const signOut = useCallback((message?: string) => {
    writeToken(null)
    setToken(null)
    setState({ kind: 'signed_out', message })
  }, [])

  const api = useCallback(
    async <T,>(path: string, options: Omit<RequestOptions, 'token'> = {}): Promise<T> => {
      try {
        return await apiRequest<T>(path, { ...options, token })
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          signOut('Sessiya muddati tugadi. Botga /admin yuborib, qaytadan kiring.')
        }
        throw error
      }
    },
    [token, signOut],
  )

  useEffect(() => {
    if (!token) {
      setState((current) => (current.kind === 'signed_out' ? current : { kind: 'signed_out' }))
      return
    }
    let cancelled = false
    apiRequest<AdminSelf>('/api/v1/admin/me', { token })
      .then((admin) => !cancelled && setState({ kind: 'signed_in', admin }))
      .catch((error: unknown) => {
        if (cancelled) return
        signOut(error instanceof ApiError ? error.message : undefined)
      })
    return () => {
      cancelled = true
    }
  }, [token, signOut])

  const loginWithLink = useCallback(async (linkToken: string) => {
    const result = await apiRequest<TokenResponse>('/api/v1/auth/admin/exchange', {
      method: 'POST',
      body: { token: linkToken },
    })
    writeToken(result.access_token)
    setState({ kind: 'loading' })
    setToken(result.access_token)
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiRequest('/api/v1/auth/logout', { method: 'POST', token })
    } catch {
      // the token may already be invalid; signing out locally is enough
    }
    signOut('Tizimdan chiqdingiz.')
  }, [token, signOut])

  const admin = state.kind === 'signed_in' ? state.admin : null
  const value = useMemo<SessionValue>(
    () => ({
      state,
      admin,
      can: (permission: string) => Boolean(admin?.permissions.includes(permission)),
      api,
      loginWithLink,
      logout,
    }),
    [state, admin, api, loginWithLink, logout],
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession must be used inside SessionProvider')
  return value
}
