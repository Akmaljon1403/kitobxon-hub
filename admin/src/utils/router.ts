import { useEffect, useState } from 'react'

// A tiny hash router: routes look like "#/books/123" or "#/login?token=...".

export interface Route {
  segments: string[]
  query: URLSearchParams
}

function currentRoute(): Route {
  const raw = window.location.hash.replace(/^#/, '')
  const [path = '', query = ''] = raw.split('?')
  return { segments: path.split('/').filter(Boolean), query: new URLSearchParams(query) }
}

export function navigate(path: string): void {
  window.location.hash = path
}

export function useRoute(): Route {
  const [route, setRoute] = useState(currentRoute)
  useEffect(() => {
    const onChange = () => setRoute(currentRoute())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}
