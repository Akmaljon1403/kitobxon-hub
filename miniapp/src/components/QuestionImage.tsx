import { useEffect, useState } from 'react'

import { useAuth } from '../store/auth'

/** A test question's picture (loaded with the member's sign-in; not cached on the phone). */
export function QuestionImage({ testId, questionId }: { testId: string; questionId: string }) {
  const { download } = useAuth()
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    setSrc(null)
    setFailed(false)
    download(`/api/v1/tests/${testId}/questions/${questionId}/image`)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [download, testId, questionId])

  if (failed) return <p className="mt-2 text-xs text-app-hint">Rasmni yuklab bo'lmadi.</p>
  if (!src) return <div className="mt-2 h-40 animate-pulse rounded-xl bg-app-surface" aria-label="Rasm yuklanmoqda" />
  return <img src={src} alt="Savol rasmi" className="mt-2 max-h-72 w-full rounded-xl object-contain" />
}
