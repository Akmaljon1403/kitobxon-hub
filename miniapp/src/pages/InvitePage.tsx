import { useCallback, useEffect, useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { useAuth } from '../store/auth'
import type { MemberContest, ReferralOverview } from '../types/api'
import { formatDate, formatEventDate } from '../utils/format'
import { navigate } from '../utils/router'
import { getWebApp, haptic } from '../utils/telegram'

const SHARE_TEXT = "Kitobxonlar klubiga qo'shil! Tadbirlar, testlar, sertifikatlar va sovg'alar 📚"
const MEDALS = ['🥇', '🥈', '🥉']

function reward(info: ReferralOverview): string {
  const parts = [info.points ? `+${info.points} ball` : null, info.premium_days ? `${info.premium_days} kunlik 💎 Premium` : null]
  return parts.filter(Boolean).join(' va ') || 'rahmat'
}

function Place({ place }: { place: number }) {
  return <span className="w-8 shrink-0 text-center text-lg font-semibold tabular-nums">{place <= 3 ? MEDALS[place - 1] : place}</span>
}

function Tile({ icon, value, label }: { icon: string; value: number; label: string }) {
  return (
    <div className="rounded-xl bg-app-surface p-3 text-center">
      <p className="text-xl font-semibold tabular-nums">
        <span aria-hidden>{icon} </span>
        {value.toLocaleString('uz-UZ')}
      </p>
      <p className="mt-0.5 text-xs text-app-hint">{label}</p>
    </div>
  )
}

/** "2 kun 5 soat" left until the end (updates every minute). */
function useCountdown(until: string): string {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000)
    return () => window.clearInterval(timer)
  }, [])
  const left = Math.max(0, new Date(until).getTime() - now)
  const days = Math.floor(left / 86_400_000)
  const hours = Math.floor((left % 86_400_000) / 3_600_000)
  const minutes = Math.floor((left % 3_600_000) / 60_000)
  if (days) return `${days} kun ${hours} soat`
  if (hours) return `${hours} soat ${minutes} daqiqa`
  return `${minutes} daqiqa`
}

function LinkCard({ info }: { info: ReferralOverview }) {
  const [copied, setCopied] = useState(false)
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
      <p className="text-sm text-app-hint">
        Do'stingiz shaxsiy havolangiz orqali qo'shilib, birinchi tadbirga kelsa — sizga <b className="text-app-text">{reward(info)}</b>
        {info.monthly_limit ? ` (oyiga ${info.monthly_limit} tagacha)` : ''}.
      </p>
      <p className="break-all rounded-xl bg-app-surface px-3 py-2 text-sm">{link}</p>
      <div className="grid grid-cols-2 gap-2">
        <Button onClick={share}>📤 Yuborish</Button>
        <Button variant="secondary" onClick={() => void copy()}>
          {copied ? '✅ Nusxalandi' : '📋 Nusxalash'}
        </Button>
      </div>
    </Card>
  )
}

function ImpactCard({ info }: { info: ReferralOverview }) {
  const impact = info.impact
  if (!impact.invited) {
    return (
      <Card>
        <EmptyState icon="🌱" title="Hali do'st taklif qilmagansiz">
          Birinchi do'stingizni klubga olib keling — u o'qigan har bir kitob va to'plagan har bir ball shu yerda ko'rinadi.
        </EmptyState>
      </Card>
    )
  }
  return (
    <Card className="flex flex-col gap-3">
      <div>
        <p className="font-semibold">💚 Sizning foydangiz</p>
        <p className="text-sm text-app-hint">Siz olib kelgan kitobxonlar klubda nimalar qildi</p>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Tile icon="👥" value={impact.invited} label="taklif qilingan" />
        <Tile icon="✅" value={impact.came_to_events} label="tadbirga kelgan" />
        <Tile icon="⭐" value={impact.friends_points} label="ular to'plagan ball" />
        <Tile icon="📚" value={impact.friends_books} label="o'qilgan kitob" />
        <Tile icon="📅" value={impact.friends_visits} label="tadbirda qatnashish" />
        <Tile icon="📝" value={impact.friends_tests} label="yechilgan test" />
      </div>
      <p className="rounded-xl bg-app-button/10 px-3 py-2 text-sm">
        Sizga taklif uchun: <b>+{impact.earned_points} ball</b>
        {impact.earned_premium_days ? (
          <>
            {' '}
            va <b>{impact.earned_premium_days} kun 💎 Premium</b>
          </>
        ) : null}
      </p>
    </Card>
  )
}

function FriendsCard({ info }: { info: ReferralOverview }) {
  if (info.friend_details === 'COUNT' || info.friends.length === 0) return null
  return (
    <>
      <SectionTitle>Do'stlarim</SectionTitle>
      <Card className="p-2">
        <ul className="divide-y divide-app-surface">
          {info.friends.map((friend, index) => (
            <li key={`${friend.name}-${index}`} className="flex items-center gap-3 px-2 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{friend.name}</p>
                <p className="text-xs text-app-hint">
                  {formatDate(friend.joined_at)} dan beri a'zo
                  {friend.points !== null && ` · ⭐ ${friend.points} ball · 📚 ${friend.books ?? 0} kitob`}
                </p>
              </div>
              {friend.came_to_event ? <Badge tone="success">tadbirga keldi</Badge> : <Badge>kutilmoqda</Badge>}
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}

function ContestCard({ contest }: { contest: MemberContest }) {
  const left = useCountdown(contest.state === 'upcoming' ? contest.starts_at : contest.ends_at)
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start gap-3">
        <span aria-hidden className="text-3xl">
          🏁
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{contest.title}</p>
          {contest.state === 'running' && <p className="text-sm text-app-hint">Tugashiga: {left} · {formatEventDate(contest.ends_at)}</p>}
          {contest.state === 'upcoming' && <p className="text-sm text-app-hint">Boshlanishiga: {left}</p>}
          {contest.state === 'finished' && <Badge tone="info">Yakunlandi</Badge>}
        </div>
      </div>
      {contest.description && <p className="whitespace-pre-line text-sm">{contest.description}</p>}
      <p className="text-sm text-app-hint">
        ✅ Hisoblanadi: {contest.rule}
        {contest.min_friends > 1 ? ` (kamida ${contest.min_friends} ta)` : ''}.
      </p>
      {contest.prizes.length > 0 && (
        <div className="rounded-xl bg-app-surface p-3 text-sm">
          <p className="mb-1 font-medium">🎁 Sovrinlar</p>
          {contest.prizes.map((prize) => (
            <p key={prize.place}>
              {prize.place <= 3 ? MEDALS[prize.place - 1] : `${prize.place}.`} {prize.text}
            </p>
          ))}
          {contest.participation_points > 0 && <p>🙌 Shartni bajargan har kimga: +{contest.participation_points} ball</p>}
        </div>
      )}
      {!contest.eligible && contest.state !== 'finished' && (
        <p className="text-sm text-amber-600">Bu tanlov boshqa fakultet yoki kurs uchun — lekin do'st taklif qilishda davom eting!</p>
      )}
      {contest.eligible && contest.state !== 'upcoming' && (
        <p className="rounded-xl bg-app-button/10 px-3 py-2 text-sm">
          Sizning do'stlaringiz: <b>{contest.my_friends}</b>
          {contest.my_place ? (
            <>
              {' '}
              · o'rningiz: <b>{contest.my_place}</b>
            </>
          ) : null}
        </p>
      )}
      {contest.leaderboard_hidden && contest.state === 'running' && (
        <p className="text-center text-sm text-app-hint">🤫 Jadval hozircha yashirin — natijalar yakunda e'lon qilinadi.</p>
      )}
      {contest.leaderboard.length > 0 && (
        <ul className="flex flex-col">
          {contest.leaderboard.map((row) => (
            <li key={row.place} className={`flex items-center gap-3 px-1 py-2 ${row.me ? 'rounded-xl bg-app-button/10' : ''}`}>
              <Place place={row.place} />
              <span className={`min-w-0 flex-1 truncate ${row.me ? 'font-semibold' : ''}`}>{row.name}</span>
              {row.winner && contest.state === 'finished' && <span aria-label="g'olib">🏆</span>}
              {row.friends !== null && <span className="font-semibold tabular-nums">{row.friends}</span>}
            </li>
          ))}
        </ul>
      )}
      {contest.state !== 'upcoming' && (
        <p className="text-center text-xs text-app-hint">Ishtirokchilar: {contest.participants}</p>
      )}
    </Card>
  )
}

/** «👥 Do'stlar»: the personal link, what the invited friends did, contests and the inviters' table. */
export function InvitePage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/profile'), [])
  useBackButton(goBack)
  const overview = useAsync((signal) => api<ReferralOverview>('/api/v1/me/referrals', { signal }), [])
  const contests = useAsync((signal) => api<MemberContest[]>('/api/v1/me/referral-contests', { signal }), [])

  if (overview.state.status === 'loading') return <LoadingState />
  if (overview.state.status === 'error') return <ErrorState message={overview.state.error.message} onRetry={overview.reload} />
  const info = overview.state.data
  if (!info.enabled || !info.link) {
    return <EmptyState icon="👥" title="Do'stlarni taklif qilish hozircha yopiq" />
  }
  const board = info.leaderboard
  return (
    <div className="flex flex-col gap-3">
      <h1 className="px-1 text-xl font-semibold">👥 Do'stlar</h1>
      <LinkCard info={info} />
      {contests.state.status === 'success' && contests.state.data.length > 0 && (
        <>
          <SectionTitle>Tanlovlar</SectionTitle>
          {contests.state.data.map((contest) => (
            <ContestCard key={contest.id} contest={contest} />
          ))}
        </>
      )}
      <ImpactCard info={info} />
      <FriendsCard info={info} />
      {board && board.items.length > 0 && (
        <>
          <SectionTitle>Eng faol taklif qiluvchilar</SectionTitle>
          <Card className="p-2">
            <ul className="flex flex-col">
              {board.items.map((row) => (
                <li key={row.place} className={`flex items-center gap-3 px-1 py-2 ${row.me ? 'rounded-xl bg-app-button/10' : ''}`}>
                  <Place place={row.place} />
                  <span className={`min-w-0 flex-1 truncate ${row.me ? 'font-semibold' : ''}`}>
                    {row.name}
                    {row.me && ' (siz)'}
                  </span>
                  <span className="font-semibold tabular-nums">{row.friends}</span>
                </li>
              ))}
            </ul>
            {board.my_place && board.my_place > board.items.length && (
              <p className="px-2 pt-2 text-center text-sm text-app-hint">
                Sizning o'rningiz: <b>{board.my_place}</b> ({board.my_friends} ta do'st)
              </p>
            )}
            <p className="px-2 pt-1 text-center text-xs text-app-hint">
              {board.rule === 'ATTENDED' ? "Kamida bitta tadbirga kelgan do'stlar sanaladi" : "Ro'yxatdan o'tgan do'stlar sanaladi"}
            </p>
          </Card>
        </>
      )}
    </div>
  )
}
