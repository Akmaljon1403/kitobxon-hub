import { useMemo, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useHomeBackButton } from '../hooks/useBackButton'
import { ApiError, apiRequest } from '../services/api'
import { useAuth } from '../store/auth'
import { formatDate } from '../utils/format'
import { haptic } from '../utils/telegram'

interface FaqTopic {
  code: string
  title: string
  items: { q: string; a: string }[]
}

interface SupportMessage {
  id: string
  from_admin: boolean
  text: string
  created_at: string
}

/** «Yordam»: answers to the usual questions, and a conversation with the club (the answer also comes in the bot). */
export function HelpPage() {
  const { api } = useAuth()
  useHomeBackButton()
  const faq = useAsync((signal) => apiRequest<FaqTopic[]>('/api/v1/meta/faq', { signal }))
  const thread = useAsync((signal) => api<SupportMessage[]>('/api/v1/me/support', { signal }))
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [topic, setTopic] = useState<'general' | 'payment'>('general')
  const [sending, setSending] = useState(false)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)

  const found = useMemo(() => {
    if (faq.state.status !== 'success') return []
    const needle = query.trim().toLowerCase()
    return faq.state.data
      .map((item) => ({
        ...item,
        items: needle ? item.items.filter((qa) => `${qa.q} ${qa.a}`.toLowerCase().includes(needle)) : item.items,
      }))
      .filter((item) => item.items.length > 0)
  }, [faq.state, query])

  async function send() {
    setSending(true)
    setNotice(null)
    try {
      await api<SupportMessage[]>('/api/v1/me/support', { method: 'POST', body: { text: text.trim(), topic } })
      haptic('success')
      setText('')
      setNotice({ text: '✅ Yuborildi! Javob shu yerda va botda keladi.' })
      thread.reload()
    } catch (error) {
      haptic('error')
      setNotice({ text: error instanceof ApiError ? error.message : "Yuborib bo'lmadi.", error: true })
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <h1 className="px-1 pt-1 font-serif text-2xl font-bold">❓ Yordam</h1>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="🔎 Savolni qidiring: davomat, sertifikat, to'lov..."
        aria-label="Savollarni qidirish"
        className="w-full rounded-xl bg-app-section px-3 py-2.5 text-[15px] outline-none"
      />
      {faq.state.status === 'loading' && <LoadingState />}
      {faq.state.status === 'error' && <ErrorState message={faq.state.error.message} onRetry={faq.reload} />}
      {found.map((group) => (
        <div key={group.code}>
          <SectionTitle>{group.title}</SectionTitle>
          <Card className="divide-y divide-app-hint/10 py-1">
            {group.items.map((qa) => {
              const key = `${group.code}:${qa.q}`
              const expanded = open === key || query.trim().length > 1
              return (
                <div key={key}>
                  <button
                    type="button"
                    aria-expanded={expanded}
                    onClick={() => setOpen(open === key ? null : key)}
                    className="flex w-full items-center justify-between gap-2 py-2.5 text-left text-[15px] font-medium"
                  >
                    {qa.q}
                    <span className="text-app-hint">{expanded ? '−' : '+'}</span>
                  </button>
                  {expanded && <p className="pb-3 text-sm text-app-hint">{qa.a}</p>}
                </div>
              )
            })}
          </Card>
        </div>
      ))}
      {faq.state.status === 'success' && found.length === 0 && (
        <Card className="py-6 text-center text-sm text-app-hint">Bunday savol topilmadi — pastda bizga yozing 👇</Card>
      )}

      <SectionTitle>✉️ Adminga yozish</SectionTitle>
      <Card className="flex flex-col gap-2">
        <div className="grid grid-cols-2 gap-1.5 text-sm">
          {(['general', 'payment'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setTopic(value)}
              className={`rounded-xl px-3 py-2 ${topic === value ? 'bg-app-button/10 ring-1 ring-app-button' : 'bg-app-surface'}`}
            >
              {value === 'general' ? '💬 Umumiy savol' : "💳 To'lov bo'yicha"}
            </button>
          ))}
        </div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, 2000))}
          rows={4}
          placeholder="Savol, taklif yoki muammoingizni yozing..."
          aria-label="Xabar matni"
          className="w-full rounded-xl bg-app-surface px-3 py-2.5 text-[15px] outline-none"
        />
        <Button loading={sending} disabled={text.trim().length < 2} onClick={() => void send()}>
          Yuborish
        </Button>
        {notice && (
          <p role={notice.error ? 'alert' : 'status'} className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-link'}`}>
            {notice.text}
          </p>
        )}
      </Card>

      {thread.state.status === 'success' && thread.state.data.length > 0 && (
        <>
          <SectionTitle>Yozishmalar</SectionTitle>
          <div className="flex flex-col gap-2">
            {thread.state.data.map((message) => (
              <div
                key={message.id}
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${message.from_admin ? 'self-start bg-app-section' : 'self-end bg-app-button text-app-button-text'}`}
              >
                {message.from_admin && <p className="text-xs font-semibold text-app-link">Klub rahbariyati</p>}
                <p className="whitespace-pre-line">{message.text}</p>
                <p className={`mt-0.5 text-right text-[10px] ${message.from_admin ? 'text-app-hint' : 'opacity-80'}`}>{formatDate(message.created_at)}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
