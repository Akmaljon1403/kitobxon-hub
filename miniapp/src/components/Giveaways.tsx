import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { MemberGiveaways, PublicGiveaway } from '../types/api'
import { formatEventDate } from '../utils/format'
import { Card, SectionTitle } from './ui'

const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }
const AUDIENCE: Record<PublicGiveaway['audience'], string | null> = {
  ALL: null,
  ATTENDED: "Davrda tadbirga kelganlar qatnashadi",
  PREMIUM: "Faqat 💎 Premium a'zolar uchun",
}

function how(giveaway: PublicGiveaway): string {
  switch (giveaway.rule) {
    case 'RANDOM':
      return `${giveaway.winners_count} ta tasodifiy g'olib`
    case 'TEST_TOP':
      return `Testlardan eng ko'p ball to'plagan ${giveaway.winners_count} kishi`
    case 'EVENT_PLACES':
      return `Har bir tadbir testining 1–${giveaway.winners_count}-o'rinlari`
    default:
      return `Reytingdagi birinchi ${giveaway.winners_count} kishi`
  }
}

/** «🎲 Sovg'a o'yinlari»: what can be won soon and who won recently. */
export function Giveaways() {
  const { api } = useAuth()
  const { state } = useAsync((signal) => api<MemberGiveaways>('/api/v1/me/giveaways', { signal }))
  if (state.status !== 'success') return null
  const { upcoming, recent } = state.data
  if (!upcoming.length && !recent.length) return null

  return (
    <>
      {upcoming.length > 0 && (
        <>
          <SectionTitle>🎲 Yaqindagi sovg'a o'yinlari</SectionTitle>
          {upcoming.map((giveaway) => (
            <Card key={giveaway.id} className="flex flex-col gap-1 bg-gradient-to-br from-amber-50 to-transparent dark:from-amber-500/10">
              <p className="font-semibold">{giveaway.title}</p>
              <p className="text-sm">🎁 {giveaway.reward}</p>
              <p className="text-sm text-app-hint">
                {how(giveaway)} · {giveaway.period}
              </p>
              {AUDIENCE[giveaway.audience] && <p className="text-xs text-app-hint">{AUDIENCE[giveaway.audience]}</p>}
              {giveaway.premium_bonus && <p className="text-xs text-app-link">💎 Premium a'zolarda imkoniyat ikki baravar</p>}
              {giveaway.scheduled_at && <p className="text-xs text-app-hint">🗓 G'oliblar: {formatEventDate(giveaway.scheduled_at)}</p>}
            </Card>
          ))}
        </>
      )}
      {recent.length > 0 && (
        <>
          <SectionTitle>🏅 So'nggi g'oliblar</SectionTitle>
          {recent.map((giveaway) => (
            <Card key={giveaway.id} className="flex flex-col gap-1.5">
              <p className="font-semibold">
                {giveaway.title} <span className="font-normal text-app-hint">· {giveaway.period}</span>
              </p>
              <ul className="flex flex-col gap-1 text-sm">
                {giveaway.winners.map((winner, index) => (
                  <li key={`${winner.name}-${index}`} className="flex gap-2">
                    <span aria-hidden>{giveaway.rule !== 'RANDOM' && winner.place ? (MEDALS[winner.place] ?? '🎁') : '🎁'}</span>
                    <span>
                      <b className="font-medium">{winner.name}</b> <span className="text-app-hint">— {winner.reason}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </>
      )}
    </>
  )
}
