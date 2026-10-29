import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { ReferralBrief } from '../types/api'
import { navigate } from '../utils/router'
import { Icon } from './Icon'
import { Card } from './ui'

/** «🎁 Sizning foydangiz» in short (home and profile pages): friends invited, their points, my reward. */
export function BenefitCard() {
  const { api } = useAuth()
  const { state } = useAsync((signal) => api<ReferralBrief>('/api/v1/me/referrals/brief', { signal }))
  const brief = state.status === 'success' ? state.data : null
  const impact = brief?.impact
  return (
    <button type="button" className="text-left" onClick={() => navigate('/invite')}>
      <Card className="flex items-center gap-3 border border-app-button/30">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-gold-400/15 text-gold-500 dark:text-gold-300">
          <Icon name="gift" size={22} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Sizning foydangiz</p>
          {impact && impact.invited > 0 ? (
            <p className="text-sm text-app-hint">
              <Icon name="users" size={13} className="inline align-[-2px]" /> {impact.invited} ta do'st ·{' '}
              <Icon name="star" size={13} className="inline align-[-2px]" /> ular {impact.friends_points.toLocaleString('uz-UZ')} ball to'pladi · sizga +
              {impact.earned_points} ball
            </p>
          ) : (
            <p className="text-sm text-app-hint">
              Do'stingizni taklif qiling
              {brief && (brief.points || brief.premium_days)
                ? ` — u tadbirga kelsa, sizga ${[brief.points ? `+${brief.points} ball` : '', brief.premium_days ? `${brief.premium_days} kun Premium` : ''].filter(Boolean).join(' va ')}`
                : ''}
            </p>
          )}
        </div>
        <Icon name="chevron-right" size={18} className="shrink-0 self-center text-app-hint" />
      </Card>
    </button>
  )
}
