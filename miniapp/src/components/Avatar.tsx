import { useState } from 'react'

import type { Me } from '../types/api'
import { initials } from '../utils/format'

export function Avatar({ me, size = 'size-16' }: { me: Me; size?: string }) {
  const [failed, setFailed] = useState(false)
  if (me.photo_url && !failed) {
    return (
      <img
        src={me.photo_url}
        alt=""
        onError={() => setFailed(true)}
        className={`${size} shrink-0 rounded-full bg-app-surface object-cover`}
      />
    )
  }
  return (
    <div
      aria-hidden
      className={`${size} flex shrink-0 items-center justify-center rounded-full bg-app-button font-semibold text-app-button-text`}
    >
      {initials(me.first_name, me.last_name)}
    </div>
  )
}
