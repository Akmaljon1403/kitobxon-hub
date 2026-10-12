import { useCallback, useEffect, useState } from 'react'

import { BookCover } from '../components/BookCover'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Reflection, ShelfItemDetail, ShelfStatus } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate } from '../utils/router'
import { confirmAction, haptic } from '../utils/telegram'
import { QuoteCard } from './QuotesPage'
import { ProgressBar, STATUS_TITLES } from './ShelfPage'

const QUESTIONS: { key: keyof Pick<Reflection, 'main_idea' | 'favorite_moment' | 'apply_in_life'>; label: string; hint: string }[] = [
  { key: 'main_idea', label: '1. Kitobning asosiy g‘oyasi nima?', hint: 'Bir-ikki gapda: muallif nima demoqchi?' },
  { key: 'favorite_moment', label: '2. Eng yoqqan joyingiz qaysi?', hint: 'Qaysi voqea, qahramon yoki fikr esda qoldi va nega?' },
  { key: 'apply_in_life', label: '3. Hayotingizda nimani qo‘llaysiz?', hint: 'Bu kitobdan keyin nimani o‘zgartirasiz?' },
]

function todayIso(offset = 0): string {
  const day = new Date()
  day.setDate(day.getDate() - offset)
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`
}

function LogForm({ itemId, onDone }: { itemId: string; onDone: () => void }) {
  const { api } = useAuth()
  const [pages, setPages] = useState('')
  const [minutes, setMinutes] = useState('')
  const [note, setNote] = useState('')
  const [back, setBack] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    const value = Number(pages)
    if (!Number.isInteger(value) || value <= 0) {
      setError('Nechta bet o‘qiganingizni yozing')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api(`/api/v1/me/shelf/${itemId}/logs`, {
        method: 'POST',
        body: { pages: value, minutes: Number(minutes) > 0 ? Number(minutes) : null, note: note.trim() || null, day: todayIso(back) },
      })
      haptic('success')
      setPages('')
      setMinutes('')
      setNote('')
      onDone()
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : 'Saqlab bo‘lmadi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-2">
      <p className="font-semibold">📖 Mutolaa kundaligiga yozish</p>
      <div className="flex gap-1">
        {['Bugun', 'Kecha', '2 kun oldin'].map((label, index) => (
          <button
            key={label}
            type="button"
            onClick={() => setBack(index)}
            className={`rounded-full px-3 py-1 text-xs ${back === index ? 'bg-app-button text-app-button-text' : 'bg-app-surface'}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="number"
          inputMode="numeric"
          placeholder="Betlar"
          value={pages}
          onChange={(event) => setPages(event.target.value)}
          className="min-w-0 flex-1 rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
        />
        <input
          type="number"
          inputMode="numeric"
          placeholder="Daqiqa (ixtiyoriy)"
          value={minutes}
          onChange={(event) => setMinutes(event.target.value)}
          className="min-w-0 flex-1 rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
        />
      </div>
      <textarea
        placeholder="Qisqa izoh: nima yoqdi, nimani o‘yladingiz? (ixtiyoriy)"
        value={note}
        maxLength={1000}
        rows={2}
        onChange={(event) => setNote(event.target.value)}
        className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
      />
      {error && <p className="text-sm text-app-danger">{error}</p>}
      <Button loading={busy} onClick={() => void save()}>
        ✍️ Kundalikka yozish
      </Button>
    </Card>
  )
}

function ReflectionForm({ itemId, saved, onDone }: { itemId: string; saved: Reflection | null; onDone: () => void }) {
  const { api } = useAuth()
  const [answers, setAnswers] = useState({
    main_idea: saved?.main_idea ?? '',
    favorite_moment: saved?.favorite_moment ?? '',
    apply_in_life: saved?.apply_in_life ?? '',
  })
  const [editing, setEditing] = useState(!saved)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)

  async function save() {
    setBusy(true)
    setNotice(null)
    try {
      const result = await api<Reflection>(`/api/v1/me/shelf/${itemId}/reflection`, { method: 'PUT', body: answers })
      haptic('success')
      setEditing(false)
      setNotice({ text: result.points ? `🎉 Rahmat! Sizga +${result.points} ball.` : '✅ Saqlandi.' })
      onDone()
    } catch (err) {
      haptic('error')
      setNotice({ text: err instanceof ApiError ? err.message : 'Saqlab bo‘lmadi', error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-3">
      <div>
        <p className="font-semibold">💡 Kitobdan keyin 3 savol</p>
        <p className="text-sm text-app-hint">O‘qiganlaringizni mustahkamlang — javob yozganingiz uchun ball beriladi (har kitobga bir marta).</p>
      </div>
      {QUESTIONS.map((question) =>
        editing ? (
          <label key={question.key} className="flex flex-col gap-1">
            <span className="text-sm font-medium">{question.label}</span>
            <textarea
              rows={3}
              maxLength={1500}
              placeholder={question.hint}
              value={answers[question.key]}
              onChange={(event) => setAnswers({ ...answers, [question.key]: event.target.value })}
              className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
            />
          </label>
        ) : (
          <div key={question.key}>
            <p className="text-sm font-medium">{question.label}</p>
            <p className="whitespace-pre-line text-[15px] text-app-hint">{answers[question.key]}</p>
          </div>
        ),
      )}
      {notice && <p className={`text-sm ${notice.error ? 'text-app-danger' : 'text-app-link'}`}>{notice.text}</p>}
      {editing ? (
        <Button loading={busy} onClick={() => void save()}>
          Saqlash
        </Button>
      ) : (
        <Button variant="secondary" onClick={() => setEditing(true)}>
          ✏️ Tahrirlash
        </Button>
      )}
    </Card>
  )
}

function AddQuote({ itemId, onDone }: { itemId: string; onDone: () => void }) {
  const { api } = useAuth()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [page, setPage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api('/api/v1/me/quotes', {
        method: 'POST',
        body: { text, shelf_item_id: itemId, page: Number(page) > 0 ? Number(page) : null },
      })
      haptic('success')
      setText('')
      setPage('')
      setOpen(false)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Saqlab bo‘lmadi')
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <Button variant="secondary" onClick={() => setOpen(true)}>
        💬 Iqtibos saqlash
      </Button>
    )
  }
  return (
    <Card className="flex flex-col gap-2">
      <textarea
        rows={4}
        maxLength={1000}
        placeholder="Kitobdagi yoqqan jumlani yozing…"
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="rounded-xl bg-app-surface px-3 py-2 text-[15px] italic outline-none"
      />
      <input
        type="number"
        inputMode="numeric"
        placeholder="Bet (ixtiyoriy)"
        value={page}
        onChange={(event) => setPage(event.target.value)}
        className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
      />
      {error && <p className="text-sm text-app-danger">{error}</p>}
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" onClick={() => setOpen(false)}>
          Bekor
        </Button>
        <Button loading={busy} disabled={!text.trim()} onClick={() => void save()}>
          Saqlash
        </Button>
      </div>
    </Card>
  )
}

/** A book on «📚 Javonim»: progress, the diary, status and rating, «3 savol» and its quotes. */
export function ShelfItemPage({ itemId }: { itemId: string }) {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/shelf'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<ShelfItemDetail>(`/api/v1/me/shelf/${itemId}`, { signal }), [itemId])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pagesTotal, setPagesTotal] = useState('')

  useEffect(() => {
    if (state.status === 'success') setPagesTotal(state.data.pages_total ? String(state.data.pages_total) : '')
  }, [state])

  async function patch(body: Record<string, unknown>, key: string) {
    setBusy(key)
    setError(null)
    try {
      await api(`/api/v1/me/shelf/${itemId}`, { method: 'PATCH', body })
      haptic('success')
      reload()
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : 'Saqlab bo‘lmadi')
    } finally {
      setBusy(null)
    }
  }

  async function remove() {
    if (!(await confirmAction('Kitob javondan olib tashlansinmi? Kundalik yozuvlari ham o‘chadi.'))) return
    await api(`/api/v1/me/shelf/${itemId}`, { method: 'DELETE' })
    navigate('/shelf')
  }

  async function removeLog(id: string) {
    if (!(await confirmAction('Bu yozuv o‘chirilsinmi?'))) return
    await api(`/api/v1/me/diary/${id}`, { method: 'DELETE' })
    reload()
  }

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const item = state.data

  return (
    <div className="flex flex-col gap-3">
      <Card className="flex gap-3">
        <BookCover url={item.cover_url} title={item.title} className="h-28 w-20 shrink-0" />
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-semibold leading-snug">{item.title}</h1>
          {item.author && <p className="text-sm text-app-hint">{item.author}</p>}
          <p className="mt-1 text-sm">{STATUS_TITLES[item.status]}</p>
          <p className="text-xs text-app-hint">
            {item.pages_total ? `${item.pages_read}/${item.pages_total} bet` : `${item.pages_read} bet o‘qildi`}
            {item.finished_at && ` · tugatildi ${formatDate(item.finished_at)}`}
          </p>
          <div className="mt-2">
            <ProgressBar percent={item.percent} />
          </div>
          {item.club_book && item.book_id && (
            <button type="button" className="mt-2 text-sm text-app-link" onClick={() => navigate(`/books/${item.book_id}`)}>
              Klub kitobi sahifasi ›
            </button>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-2">
        {(['READING', 'FINISHED', 'WANT', 'LATER'] as ShelfStatus[])
          .filter((status) => status !== item.status)
          .map((status) => (
            <Button
              key={status}
              variant={status === 'FINISHED' ? 'primary' : 'secondary'}
              loading={busy === status}
              disabled={busy !== null}
              onClick={() => void patch({ status }, status)}
              className="text-sm"
            >
              {STATUS_TITLES[status]}
            </Button>
          ))}
      </div>
      {error && <p className="text-center text-sm text-app-danger">{error}</p>}

      {item.status !== 'FINISHED' && <LogForm itemId={item.id} onDone={reload} />}

      {item.status === 'FINISHED' && (
        <>
          <Card className="flex items-center justify-between gap-2">
            <span className="text-sm">Bahoyingiz:</span>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-label={`${value} yulduz`}
                  onClick={() => void patch(value === item.rating ? { clear_rating: true } : { rating: value }, `r${value}`)}
                  className={`text-2xl ${item.rating && value <= item.rating ? 'text-amber-400' : 'text-app-hint/40'}`}
                >
                  ★
                </button>
              ))}
            </div>
          </Card>
          <ReflectionForm key={item.reflection?.updated_at ?? 'new'} itemId={item.id} saved={item.reflection} onDone={reload} />
        </>
      )}

      <SectionTitle>Iqtiboslar ({item.quotes.length})</SectionTitle>
      {item.quotes.map((quote) => (
        <QuoteCard key={quote.id} quote={quote} onChange={reload} />
      ))}
      <AddQuote itemId={item.id} onDone={reload} />

      <SectionTitle>Kundalik</SectionTitle>
      {item.diary.length === 0 ? (
        <Card className="text-center text-sm text-app-hint">Hali yozuv yo‘q — bugun o‘qiganingizni yozing.</Card>
      ) : (
        <Card className="p-2">
          <ul className="divide-y divide-app-surface">
            {item.diary.map((entry) => (
              <li key={entry.id} className="flex items-start gap-3 px-2 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {formatDate(entry.log_date)} · {entry.pages} bet{entry.minutes ? ` · ${entry.minutes} daq.` : ''}
                  </p>
                  {entry.note && <p className="whitespace-pre-line text-sm text-app-hint">{entry.note}</p>}
                </div>
                <button type="button" aria-label="O‘chirish" className="text-app-hint" onClick={() => void removeLog(entry.id)}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="flex flex-col gap-2">
        <label className="flex items-center justify-between gap-2 text-sm">
          Kitobdagi betlar soni
          <input
            type="number"
            inputMode="numeric"
            value={pagesTotal}
            onChange={(event) => setPagesTotal(event.target.value)}
            onBlur={() => Number(pagesTotal) > 0 && Number(pagesTotal) !== item.pages_total && void patch({ pages_total: Number(pagesTotal) }, 'pages')}
            className="w-24 rounded-xl bg-app-surface px-3 py-1.5 text-right outline-none"
          />
        </label>
        <Button variant="ghost" onClick={() => void remove()}>
          🗑 Javondan olib tashlash
        </Button>
      </Card>
    </div>
  )
}
