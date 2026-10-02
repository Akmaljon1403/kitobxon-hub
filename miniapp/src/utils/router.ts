import { useEffect, useState } from 'react'

// A tiny hash router: routes look like "#/books/123". Telegram may append its own launch
// parameters to the hash ("#/books&tgWebAppData=..."), so everything from the first
// tgWebApp parameter on is ignored.

function currentPath(): string {
  const raw = window.location.hash.replace(/^#/, '')
  const path = raw.split(/[?&]?tgWebApp/)[0] ?? ''
  const clean = path.split('?')[0] ?? ''
  return clean.startsWith('/') ? clean : `/${clean}`
}

/** Query parameters of the current route, e.g. "#/checkin?scan=1" → scan=1. */
export function routeQuery(): URLSearchParams {
  const raw = window.location.hash.replace(/^#/, '')
  const path = raw.split(/[?&]?tgWebApp/)[0] ?? ''
  return new URLSearchParams(path.split('?')[1] ?? '')
}

export function navigate(path: string): void {
  window.location.hash = path
}

export function useRoute(): string[] {
  const [path, setPath] = useState(currentPath)
  useEffect(() => {
    const onChange = () => {
      setPath(currentPath())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return path.split('/').filter(Boolean)
}
