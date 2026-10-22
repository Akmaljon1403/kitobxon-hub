import { useEffect, useRef, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, InlineError, PageHeader, Select, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Page } from '../types/api'
import { formatDateTime } from '../utils/format'
import { navigate } from '../utils/router'

type TicketStatus = 'OPEN' | 'ANSWERED' | 'CLOSED'
type TicketKind = 'GENERAL' | 'PAYMENT'

interface SupportMember {
  user_id: string
  first_name: string
  last_name: string
  faculty: string | null
  course: number | null
  group_name: string | null
  telegram_username: string | null
}

interface Ticket {
  id: string
  status: TicketStatus
  kind: TicketKind
  unread: boolean
  last_message_at: string
  created_at: string
  last_text: string
  message_count: number
  member: SupportMember
}

interface Message {
  id: string
  from_admin: boolean
  admin_name: string | null
  text: string
  has_photo: boolean
  created_at: string
}

interface TicketDetail {
  id: string
  status: TicketStatus
  created_at: string
  member: SupportMember
  messages: Message[]
}

const STATUS: Record<TicketStatus, { label: string; tone: 'warning' | 'success' | 'neutral' }> = {
  OPEN: { label: 'Javob kutmoqda', tone: 'warning' },
  ANSWERED: { label: 'Javob berilgan', tone: 'success' },
  CLOSED: { label: 'Yopilgan', tone: 'neutral' },
}

const KIND: Record<TicketKind, { label: string; tone: 'info' | 'neutral' }> = {
  GENERAL: { label: '✉️ Umumiy', tone: 'neutral' },
  PAYMENT: { label: '💳 To\'lov', tone: 'info' },
}

function memberLine(member: SupportMember): string {
  return [member.faculty, member.course ? `${member.course}-kurs` : null, member.group_name].filter(Boolean).join(' · ')
}

export function SupportPage() {
  const { api, can } = useSession()
  const seesPayment = can('PAYMENT_SUPPORT')
  const [status, setStatus] = useState<'' | TicketStatus>('')
  const [kind, setKind] = useState<'' | TicketKind>('')
  const query = [status ? `&status=${status}` : '', kind ? `&kind=${kind}` : ''].join('')
  const { state, reload } = useAsync(
    (signal) => api<Page<Ticket>>(`/api/v1/admin/support?limit=50${query}`, { signal }),
    [status, kind],
  )

  return (
    <>
      <PageHeader
        title="Murojaatlar"
        subtitle={
          seesPayment
            ? "A'zolarning botdagi murojaatlari — umumiy savollar va to'lov bo'yicha murojaatlar. To'lov murojaatlari to'lovlar kanaliga ham boradi. Javobingiz a'zoga «Klub rahbariyati» nomidan yetadi."
            : "A'zolar botdagi «✉️ Adminga yozish» orqali yozgan xabarlar. Javobingiz a'zoga «Klub rahbariyati» nomidan boradi."
        }
      />
      <div className="flex flex-wrap gap-2">
        <div className="w-56">
          <Select value={status} onChange={(e) => setStatus(e.target.value as '' | TicketStatus)} aria-label="Holat">
            <option value="">Barcha holatlar</option>
            <option value="OPEN">Javob kutayotganlar</option>
            <option value="ANSWERED">Javob berilganlar</option>
            <option value="CLOSED">Yopilganlar</option>
          </Select>
        </div>
        {seesPayment && (
          <div className="w-56">
            <Select value={kind} onChange={(e) => setKind(e.target.value as '' | TicketKind)} aria-label="Turi">
              <option value="">Barcha turlar</option>
              <option value="GENERAL">✉️ Umumiy</option>
              <option value="PAYMENT">💳 To'lov</option>
            </Select>
          </div>
        )}
      </div>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <Card className="divide-y divide-app-border">
          {state.data.items.length === 0 && <p className="p-6 text-center text-sm text-app-hint">Hozircha murojaat yo'q 🎉</p>}
          {state.data.items.map((ticket) => (
            <button
              key={ticket.id}
              type="button"
              onClick={() => navigate(`/support/${ticket.id}`)}
              className="flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-app-surface"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className={`text-sm ${ticket.unread ? 'font-semibold' : ''}`}>
                  {ticket.unread && <span aria-label="Yangi" className="mr-1.5 inline-block size-2 rounded-full bg-app-button" />}
                  {ticket.member.last_name} {ticket.member.first_name}
                  <span className="font-normal text-app-hint"> · {memberLine(ticket.member)}</span>
                </span>
                <span className="flex items-center gap-2 text-xs text-app-hint">
                  {formatDateTime(ticket.last_message_at)}
                  {ticket.kind === 'PAYMENT' && <Badge tone={KIND.PAYMENT.tone}>{KIND.PAYMENT.label}</Badge>}
                  <Badge tone={STATUS[ticket.status].tone}>{STATUS[ticket.status].label}</Badge>
                </span>
              </div>
              <p className="line-clamp-2 text-sm text-app-hint">{ticket.last_text}</p>
            </button>
          ))}
        </Card>
      )}
    </>
  )
}

function Photo({ messageId }: { messageId: string }) {
  const { download } = useSession()
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let url: string | null = null
    download(`/api/v1/admin/support/messages/${messageId}/photo`)
      .then((blob) => {
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => setFailed(true))
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [download, messageId])
  if (failed) return <p className="text-xs text-app-hint">Rasmni yuklab bo'lmadi.</p>
  return src ? <img src={src} alt="A'zo yuborgan rasm" className="max-h-72 rounded-lg" /> : <p className="text-xs text-app-hint">Rasm yuklanmoqda…</p>
}

export function SupportTicketPage({ ticketId }: { ticketId: string }) {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<TicketDetail>(`/api/v1/admin/support/${ticketId}`, { signal }), [ticketId])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (state.status === 'success') bottom.current?.scrollIntoView({ block: 'end' })
  }, [state])

  async function send() {
    setBusy(true)
    setError(null)
    try {
      await api(`/api/v1/admin/support/${ticketId}/reply`, { method: 'POST', body: { text } })
      setText('')
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function setStatus(status: TicketStatus) {
    await api(`/api/v1/admin/support/${ticketId}/status`, { method: 'POST', body: { status } })
    reload()
  }

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const ticket = state.data
  return (
    <>
      <PageHeader
        title={`${ticket.member.last_name} ${ticket.member.first_name}`}
        subtitle={[memberLine(ticket.member), ticket.member.telegram_username ? `@${ticket.member.telegram_username}` : null].filter(Boolean).join(' · ')}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => navigate('/support')}>
              ← Murojaatlar
            </Button>
            {ticket.status === 'CLOSED' ? (
              <Button variant="secondary" onClick={() => void setStatus('OPEN')}>
                Qayta ochish
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => void setStatus('CLOSED')}>
                ✓ Yopish
              </Button>
            )}
          </div>
        }
      />
      <Card className="flex flex-col gap-3 p-4">
        {ticket.messages.map((message) => (
          <div key={message.id} className={`flex ${message.from_admin ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex max-w-[85%] flex-col gap-1.5 rounded-2xl px-4 py-2.5 ${message.from_admin ? 'bg-app-button/10' : 'bg-app-surface'}`}>
              {message.has_photo && <Photo messageId={message.id} />}
              <p className="whitespace-pre-wrap text-sm">{message.text}</p>
              <p className="text-xs text-app-hint">
                {message.from_admin ? `Javob · ${message.admin_name ?? 'admin'}` : "A'zo"} · {formatDateTime(message.created_at)}
              </p>
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </Card>
      <Card className="flex flex-col gap-2 p-4">
        <label htmlFor="reply" className="text-sm font-medium">
          Javob yozish
        </label>
        <Textarea id="reply" rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder="Javobingiz bot orqali a'zoga yuboriladi…" />
        <InlineError message={error} />
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-app-hint">A'zo sizning ismingizni ko'rmaydi — javob «Klub rahbariyati» nomidan boradi.</p>
          <Button onClick={() => void send()} loading={busy} disabled={!text.trim()}>
            Yuborish
          </Button>
        </div>
      </Card>
    </>
  )
}
