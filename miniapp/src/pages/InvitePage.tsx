import { useCallback, useEffect, useState } from 'react'

import { Icon, type IconName } from '../components/Icon'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, FeatureTile, PageTitle, SectionTitle } from '../components/ui'
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

function Tile({ icon, value, label }: { icon: IconName; value: number; label: string }) {
  return (
    <div className="rounded-xl bg-app-surface p-3 text-center">
      <p className="flex items-center justify-center gap-1 text-xl font-semibold tabular-nums">
        <Icon name={icon} size={18} className="text-app-hint" />
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
        <Button onClick={share}><Icon name="send" size={18} />Yuborish</Button>
        <Button variant="secondary" onClick={() => void copy()}>
          {copied ? <><Icon name="check" size={18} />Nusxalandi</> : <><Icon name="copy" size={18} />Nusxalash</>}
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
        <EmptyState icon="sprout" title="Hali do'st taklif qilmagansiz">
          Birinchi do'stingizni klubga olib keling — u o'qigan har bir kitob va to'plagan har bir ball shu yerda ko'rinadi.
        </EmptyState>
      </Card>
    )
  }
  return (
    <Card className="flex flex-col gap-3">
      <div>
        <p className="flex items-center gap-1.5 font-semibold"><Icon name="bar-chart" size={16} />Qisqacha</p>
        <p className="text-sm text-app-hint">Siz olib kelgan kitobxonlar klubda nimalar qildi</p>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Tile icon="users" value={impact.invited} label="taklif qilingan" />
        <Tile icon="check" value={impact.came_to_events} label="tadbirga kelgan" />
        <Tile icon="star" value={impact.friends_points} label="ular to'plagan ball" />
        <Tile icon="book" value={impact.friends_books} label="o'qilgan kitob" />
        <Tile icon="calendar" value={impact.friends_visits} label="tadbirda qatnashish" />
        <Tile icon="file-text" value={impact.friends_tests} label="yechilgan test" />
      </div>
      <p className="rounded-xl bg-brand-500/10 px-3 py-2 text-sm">
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
      <SectionTitle>Taklif qilgan do'stlarim</SectionTitle>
      <Card className="p-2">
        <ul className="divide-y divide-app-surface">
          {info.friends.map((friend, index) => (
            <li key={`${friend.name}-${index}`} className="flex items-center gap-3 px-2 py-2.5">
              <span className="w-6 shrink-0 text-center text-sm text-app-hint tabular-nums">{index + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{friend.name}</p>
                <p className="text-xs text-app-hint">
                  {formatDate(friend.joined_at)} dan beri a'zo
                  {friend.books !== null && ` · ${friend.books} kitob`} ·{' '}
                  {friend.came_to_event ? 'tadbirga keldi' : 'hali kelmadi'}
                </p>
              </div>
              {friend.points !== null ? (
                <span className="flex shrink-0 items-center gap-1 font-semibold tabular-nums">
                  <Icon name="star" size={13} />
                  {friend.points.toLocaleString('uz-UZ')}
                </span>
              ) : friend.came_to_event ? (
                <Badge tone="success">tadbirga keldi</Badge>
              ) : (
                <Badge>kutilmoqda</Badge>
              )}
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
        <FeatureTile icon="flag" tone="brand" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{contest.title}</p>
          {contest.state === 'running' && <p className="text-sm text-app-hint">Tugashiga: {left} · {formatEventDate(contest.ends_at)}</p>}
          {contest.state === 'upcoming' && <p className="text-sm text-app-hint">Boshlanishiga: {left}</p>}
          {contest.state === 'finished' && <Badge tone="info">Yakunlandi</Badge>}
        </div>
      </div>
      {contest.description && <p className="whitespace-pre-line text-sm">{contest.description}</p>}
      <p className="flex items-start gap-1.5 text-sm text-app-hint">
        <Icon name="check" size={14} className="mt-0.5 shrink-0" />
        <span>
          Hisoblanadi: {contest.rule}
          {contest.min_friends > 1 ? ` (kamida ${contest.min_friends} ta)` : ''}.
        </span>
      </p>
      {contest.prizes.length > 0 && (
        <div className="rounded-xl bg-app-surface p-3 text-sm">
          <p className="mb-1 flex items-center gap-1.5 font-medium"><Icon name="gift" size={15} />Sovrinlar</p>
          {contest.prizes.map((prize) => (
            <p key={prize.place}>
              {prize.place <= 3 ? MEDALS[prize.place - 1] : `${prize.place}.`} {prize.text}
            </p>
          ))}
          {contest.participation_points > 0 && <p>Shartni bajargan har kimga: +{contest.participation_points} ball</p>}
        </div>
      )}
      {!contest.eligible && contest.state !== 'finished' && (
        <p className="text-sm text-amber-600">Bu tanlov boshqa fakultet yoki kurs uchun — lekin do'st taklif qilishda davom eting!</p>
      )}
      {contest.eligible && contest.state !== 'upcoming' && (
        <p className="rounded-xl bg-brand-500/10 px-3 py-2 text-sm">
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
        <p className="flex items-center justify-center gap-1.5 text-center text-sm text-app-hint">
          <Icon name="eye-off" size={14} className="shrink-0" />
          Jadval hozircha yashirin — natijalar yakunda e'lon qilinadi.
        </p>
      )}
      {contest.leaderboard.length > 0 && (
        <ul className="flex flex-col">
          {contest.leaderboard.map((row) => (
            <li key={row.place} className={`flex items-center gap-3 px-1 py-2 ${row.me ? 'rounded-xl bg-brand-500/10' : ''}`}>
              <Place place={row.place} />
              <span className={`min-w-0 flex-1 truncate ${row.me ? 'font-semibold' : ''}`}>{row.name}</span>
              {row.winner && contest.state === 'finished' && (
                <span aria-label="g'olib" className="text-gold-500 dark:text-gold-300">
                  <Icon name="trophy" size={16} />
                </span>
              )}
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

/** «🎁 Sizning foydangiz» (always open): the personal link, what the invited friends did, contests and the
 * inviters' table. */
export function InvitePage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/profile'), [])
  useBackButton(goBack)
  const overview = useAsync((signal) => api<ReferralOverview>('/api/v1/me/referrals', { signal }), [])
  const contests = useAsync((signal) => api<MemberContest[]>('/api/v1/me/referral-contests', { signal }), [])

  if (overview.state.status === 'loading') return <LoadingState />
  if (overview.state.status === 'error') return <ErrorState message={overview.state.error.message} onRetry={overview.reload} />
  const info = overview.state.data
  const board = info.leaderboard
  return (
    <div className="flex flex-col gap-3">
      <div>
        <PageTitle icon="gift">Sizning foydangiz</PageTitle>
        <p className="px-1 text-sm text-app-hint">Do'stlaringizni taklif qiling — ular bilan birga o'qing va mukofot oling</p>
      </div>
      {info.link ? (
        <LinkCard info={info} />
      ) : (
        <Card>
          <EmptyState icon="hourglass" title="Havola tayyorlanmoqda">
            Bir daqiqadan so'ng qayta oching yoki botda /referal buyrug'ini yuboring.
          </EmptyState>
          <Button variant="secondary" onClick={overview.reload}>
            <Icon name="refresh" size={18} />Qayta urinish
          </Button>
        </Card>
      )}
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
                <li key={row.place} className={`flex items-center gap-3 px-1 py-2 ${row.me ? 'rounded-xl bg-brand-500/10' : ''}`}>
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
