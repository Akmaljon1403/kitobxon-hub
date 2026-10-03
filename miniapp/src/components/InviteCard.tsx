import { useState } from 'react'

import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { Referrals } from '../types/api'
import { getWebApp, haptic } from '../utils/telegram'
import { Button, Card } from './ui'

const SHARE_TEXT = "Kitobxonlar klubiga qo'shil! Tadbirlar, testlar, sertifikatlar va sovg'alar 📚"

function reward(info: Referrals): string {
  const parts = [info.points ? `+${info.points} ball` : null, info.premium_days ? `${info.premium_days} kunlik 💎 Premium` : null]
  return parts.filter(Boolean).join(' va ') || 'rahmat'
}

/** «Do'stni taklif qilish»: a personal link; the reward comes when the friend attends an event. */
export function InviteCard() {
  const { api } = useAuth()
  const { state } = useAsync((signal) => api<Referrals>('/api/v1/me/referrals', { signal }), [])
  const [copied, setCopied] = useState(false)
  if (state.status !== 'success' || !state.data.enabled || !state.data.link) return null
  const info = state.data
  const link = info.link as string

  function share() {
    const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(SHARE_TEXT)}`
    const webApp = getWebApp()
    if (webApp) webApp.openTelegramLink(url)
    else window.open(url, '_blank', 'noopener,noreferrer')
    haptic('success')
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      haptic('success')
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-start gap-3">
        <span aria-hidden className="text-3xl">
          👥
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Do'stni taklif qilish</p>
          <p className="text-sm text-app-hint">
            Do'stingiz havolangiz orqali qo'shilib, birinchi tadbirga kelsa — sizga {reward(info)}
            {info.monthly_limit ? ` (oyiga ${info.monthly_limit} tagacha)` : ''}.
          </p>
        </div>
      </div>
      <p className="break-all rounded-xl bg-app-bg px-3 py-2 text-sm">{link}</p>
      <div className="grid grid-cols-2 gap-2">
        <Button onClick={share}>📤 Yuborish</Button>
        <Button variant="secondary" onClick={() => void copy()}>
          {copied ? '✅ Nusxalandi' : '📋 Nusxalash'}
        </Button>
      </div>
      <p className="text-center text-xs text-app-hint">
        Taklif qilganlaringiz: <b>{info.invited}</b> · mukofot olingan: <b>{info.rewarded}</b>
      </p>
    </Card>
  )
}
