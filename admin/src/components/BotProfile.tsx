import { useEffect, useState } from 'react'

import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Setting } from '../types/api'
import { Badge, Button, Card, Field, InlineError, Input, Textarea } from './ui'

interface ProfileTexts {
  name: string
  short_description: string
  description: string
  menu_button?: string
}

interface ProfileState {
  wanted: Required<ProfileTexts>
  telegram: ProfileTexts | null
  username: string | null
  has_avatar: boolean | null
  avatar_preview: string | null
}

const FIELDS: { key: keyof ProfileTexts; setting: string; label: string; max: number; hint: string }[] = [
  { key: 'name', setting: 'bot.name', label: 'Bot nomi', max: 64, hint: "Bo'sh qoldirsangiz — @BotFather'dagi nom qoladi" },
  {
    key: 'short_description',
    setting: 'bot.short_description',
    label: 'Qisqa tavsif',
    max: 120,
    hint: "Bot profilida va havola ulashilganda ko'rinadi",
  },
  {
    key: 'description',
    setting: 'bot.description',
    label: "To'liq tavsif",
    max: 512,
    hint: "Botning bo'sh chatida, «Start» tugmasi ustida ko'rinadi",
  },
  { key: 'menu_button', setting: 'bot.menu_button', label: 'Ilova tugmasi', max: 32, hint: 'Chat pastidagi tugma matni' },
]

/** «🤖 Bot profili»: what @BotFather would do, done from here — the bot applies it itself. */
export function BotProfile() {
  const { api } = useSession()
  const profile = useAsync((signal) => api<ProfileState>('/api/v1/admin/bot-profile', { signal }))
  const [draft, setDraft] = useState<Required<ProfileTexts> | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const data = profile.state.status === 'success' ? profile.state.data : null
  useEffect(() => {
    if (data && draft === null) setDraft(data.wanted)
  }, [data, draft])

  async function run(label: string, action: () => Promise<string>) {
    setBusy(label)
    setError(null)
    setNotice(null)
    try {
      setNotice(await action())
      profile.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bajarib bo'lmadi.")
    } finally {
      setBusy(null)
    }
  }

  async function save() {
    if (!draft || !data) return
    for (const field of FIELDS) {
      if (draft[field.key] !== data.wanted[field.key]) {
        await api<Setting>(`/api/v1/admin/settings/${field.setting}`, { method: 'PUT', body: { value: draft[field.key] } })
      }
    }
    return "✓ Saqlandi va Telegram'ga yuborildi."
  }

  const synced =
    data?.telegram != null &&
    data.telegram.short_description === data.wanted.short_description &&
    data.telegram.description === data.wanted.description &&
    (!data.wanted.name || data.telegram.name === data.wanted.name)
  const dirty = draft != null && data != null && FIELDS.some((field) => draft[field.key] !== data.wanted[field.key])

  return (
    <Card className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-semibold">🤖 Bot profili</h2>
        {data?.username && <Badge>@{data.username}</Badge>}
        {data?.telegram == null && data && <Badge tone="warning">bot hozir ishlamayapti</Badge>}
        {data?.telegram != null && (synced ? <Badge tone="success">Telegram'da shunday</Badge> : <Badge tone="warning">Telegram'da boshqacha</Badge>)}
      </div>
      <p className="text-sm text-app-hint">
        @BotFather'ga kirish shart emas: bu yerdagi matnlarni bot o'zi Telegram'ga yozadi. Buyruqlar menyusi ham o'zi
        sozlanadi — a'zolar oddiy buyruqlarni, adminlar esa qo'shimcha <b>/admin</b>, <b>/stiker</b>, <b>/emoji</b> ni
        ko'radi; kanal va guruhlarda menyu chiqmaydi.
      </p>
      {draft && (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <div className="flex flex-col gap-3">
            {FIELDS.map((field) => {
              const value = draft[field.key]
              const props = {
                value,
                maxLength: field.max,
                onChange: (e: { target: { value: string } }) => setDraft({ ...draft, [field.key]: e.target.value }),
              }
              return (
                <Field key={field.key} label={`${field.label} · ${value.length}/${field.max}`} hint={field.hint}>
                  {field.key === 'description' ? <Textarea rows={9} {...props} /> : <Input {...props} />}
                </Field>
              )
            })}
          </div>
          {/* How a member sees the bot before pressing «Start». */}
          <div className="flex flex-col items-center gap-3 rounded-2xl bg-[#0e1621] p-4 text-white">
            {data?.avatar_preview ? (
              <img src={data.avatar_preview} alt="" className="h-20 w-20 rounded-full shadow-lg" />
            ) : (
              <span className="flex h-20 w-20 items-center justify-center rounded-full bg-[#2b5278] text-4xl">📚</span>
            )}
            <p className="text-center font-semibold">{draft.name || data?.telegram?.name || 'Kitobxon Hub'}</p>
            <p className="text-center text-xs text-white/60">{draft.short_description}</p>
            <div className="w-full whitespace-pre-line rounded-xl bg-[#182533] p-3 text-sm leading-snug">{draft.description}</div>
            <span className="rounded-lg bg-[#2b5278] px-4 py-1.5 text-sm">{draft.menu_button || '📱 Ilova'}</span>
          </div>
        </div>
      )}
      <InlineError message={error} />
      {notice && <p className="text-sm text-emerald-700">{notice}</p>}
      <div className="flex flex-wrap gap-2">
        <Button disabled={!dirty} loading={busy === 'save'} onClick={() => void run('save', async () => (await save()) ?? '')}>
          Saqlash
        </Button>
        <Button
          variant="secondary"
          loading={busy === 'apply'}
          onClick={() =>
            void run('apply', async () => {
              await api('/api/v1/admin/bot-profile/apply', { method: 'POST' })
              return "✓ Nom, tavsif, buyruqlar menyusi va kanal huquqlari Telegram'ga qayta yuborildi."
            })
          }
        >
          🔄 Telegram'ga qayta yuborish
        </Button>
        <Button
          variant="secondary"
          loading={busy === 'avatar'}
          disabled={!data?.avatar_preview}
          title={data?.avatar_preview ? undefined : "Avval klub avatari fayli qo'yilishi kerak"}
          onClick={() => {
            if (!window.confirm('Botning hozirgi rasmi klub avatari bilan almashtirilsinmi?')) return
            void run('avatar', async () => {
              const result = await api<{ ok: boolean }>('/api/v1/admin/bot-profile/avatar', { method: 'POST' })
              return result.ok ? "✓ Bot avatari o'rnatildi (Telegram'da bir necha daqiqada yangilanadi)." : "Klub avatari fayli hali qo'yilmagan."
            })
          }}
        >
          🖼 Klub avatarini o'rnatish
        </Button>
      </div>
    </Card>
  )
}
