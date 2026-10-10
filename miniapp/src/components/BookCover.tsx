import { useState } from 'react'

import { API_BASE } from '../services/api'

const PALETTE = ['from-emerald-500 to-teal-700', 'from-sky-500 to-indigo-700', 'from-amber-500 to-orange-700', 'from-rose-500 to-fuchsia-700']

/** Cover image, or a coloured placeholder with the title when there is no image (or it fails to load). */
export function BookCover({ url, title, className = '' }: { url: string | null; title: string; className?: string }) {
  const [failed, setFailed] = useState(false)
  if (url && !failed) {
    return (
      <img
        src={url.startsWith('/') ? `${API_BASE}${url}` : url}
        alt={title}
        loading="lazy"
        onError={() => setFailed(true)}
        className={`rounded-lg bg-app-surface object-cover ${className}`}
      />
    )
  }
  const tone = PALETTE[title.length % PALETTE.length]
  return (
    <div
      aria-hidden
      className={`flex items-end rounded-lg bg-gradient-to-br p-2 text-left text-[10px] font-semibold leading-tight text-white ${tone} ${className}`}
    >
      <span className="line-clamp-4">{title}</span>
    </div>
  )
}
