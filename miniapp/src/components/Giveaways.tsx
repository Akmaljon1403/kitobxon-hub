import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { MemberGiveaways, PublicGiveaway } from '../types/api'
import { formatEventDate } from '../utils/format'
import { Icon } from './Icon'
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
    case 'NEW_MEMBERS':
      return `Botga qo'shilgan birinchi ${giveaway.winners_count} kishi — sovg'a darhol beriladi`
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
          <SectionTitle>
            <span className="flex items-center gap-1.5">
              <Icon name="gift" size={13} />
              Yaqindagi sovg'a o'yinlari
            </span>
          </SectionTitle>
          {upcoming.map((giveaway) => (
            <Card key={giveaway.id} className="flex flex-col gap-1 bg-gradient-to-br from-gold-400/10 to-transparent">
              <p className="font-semibold">{giveaway.title}</p>
              <p className="text-sm">
                <span className="text-app-hint">Sovg'a:</span> {giveaway.reward}
              </p>
              <p className="text-sm text-app-hint">
                {how(giveaway)} · {giveaway.period}
              </p>
              {AUDIENCE[giveaway.audience] && <p className="text-xs text-app-hint">{AUDIENCE[giveaway.audience]}</p>}
              {giveaway.premium_bonus && (
                <p className="flex items-center gap-1 text-xs text-app-link">
                  <Icon name="gem" size={12} />
                  Premium a'zolarda imkoniyat ikki baravar
                </p>
              )}
              {giveaway.scheduled_at && (
                <p className="flex items-center gap-1 text-xs text-app-hint">
                  <Icon name="calendar" size={12} />
                  G'oliblar: {formatEventDate(giveaway.scheduled_at)}
                </p>
              )}
            </Card>
          ))}
        </>
      )}
      {recent.length > 0 && (
        <>
          <SectionTitle>
            <span className="flex items-center gap-1.5">
              <Icon name="medal" size={13} />
              So'nggi g'oliblar
            </span>
          </SectionTitle>
          {recent.map((giveaway) => (
            <Card key={giveaway.id} className="flex flex-col gap-1.5">
              <p className="font-semibold">
                {giveaway.title} <span className="font-normal text-app-hint">· {giveaway.period}</span>
              </p>
              <ul className="flex flex-col gap-1 text-sm">
                {giveaway.winners.map((winner, index) => (
                  <li key={`${winner.name}-${index}`} className="flex gap-2">
                    <span aria-hidden className="shrink-0">
                      {giveaway.rule !== 'RANDOM' && giveaway.rule !== 'NEW_MEMBERS' && winner.place && MEDALS[winner.place] ? (
                        MEDALS[winner.place]
                      ) : (
                        <Icon name="gift" size={16} className="inline align-[-2px] text-gold-500 dark:text-gold-300" />
                      )}
                    </span>
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
