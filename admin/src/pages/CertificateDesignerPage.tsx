import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, Field, InlineError, Input, Select } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import { navigate } from '../utils/router'

// Keep these in step with app/services/certificate_templates.py (ELEMENT_TYPES) and the schema.
type ElType =
  | 'name'
  | 'cert_title'
  | 'description'
  | 'place'
  | 'date'
  | 'member_number'
  | 'organization'
  | 'club'
  | 'signer'
  | 'code'
  | 'qr'
  | 'seal'
  | 'logo'
  | 'text'

interface El {
  type: ElType
  x: number
  y: number
  w: number
  size: number
  font: 'serif' | 'sans' | 'mono'
  color: string
  align: 'left' | 'center' | 'right'
  bold: boolean
  italic: boolean
  variant: 'auto' | 'light' | 'dark'
  content: string
}

interface Template {
  id: string
  name: string
  has_background: boolean
  bg_width: number
  bg_height: number
  elements: El[]
  is_default: boolean
}

const LABELS: Record<ElType, string> = {
  name: 'Ism familiya',
  cert_title: 'Sertifikat nomi',
  description: 'Asosiy matn',
  place: "O'rin (1/2/3)",
  date: 'Sana',
  member_number: "A'zo raqami",
  organization: 'Tashkilot nomi',
  club: 'Klub nomi',
  signer: 'Imzolovchi',
  code: 'Tekshirish kodi',
  qr: 'QR kod',
  seal: 'Muhr',
  logo: 'Logotip',
  text: 'Erkin matn',
}
const SAMPLE: Record<ElType, string> = {
  name: 'Karimova Aziza',
  cert_title: "«Faol kitobxon»",
  description: "Bilim testida 1-o'rinni egallagani uchun taqdim etiladi.",
  place: "1-o'rin",
  date: '15.10.2026',
  member_number: "A'zo № KH-000042",
  organization: 'FJSTI',
  club: 'Kitobxonlar klubi',
  signer: 'Klub rahbari — F.I.Sh.',
  code: 'NAMUNA-2026',
  qr: 'QR',
  seal: 'MUHR',
  logo: 'LOGO',
  text: 'Matn',
}
const IMAGE_TYPES: ElType[] = ['qr', 'seal', 'logo']
const FONT_CSS: Record<El['font'], string> = {
  serif: 'Georgia, "Times New Roman", serif',
  sans: 'system-ui, Arial, sans-serif',
  mono: 'ui-monospace, "Courier New", monospace',
}
const LONG_MM = 297
const MM_PER_PT = 0.3527

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function newElement(type: ElType): El {
  const image = IMAGE_TYPES.includes(type)
  return {
    type,
    x: 40,
    y: 42,
    w: image ? 14 : 40,
    size: type === 'name' ? 28 : 16,
    font: 'serif',
    color: type === 'name' ? '#14402c' : '#1c2b24',
    align: 'center',
    bold: type === 'name',
    italic: false,
    variant: 'auto',
    content: '',
  }
}

export function CertificateDesignerPage({ templateId }: { templateId: string }) {
  const { api, download } = useSession()
  const loaded = useAsync((signal) => api<Template>(`/api/v1/admin/certificate-templates/${templateId}`, { signal }), [templateId])

  const [name, setName] = useState('')
  const [elements, setElements] = useState<El[]>([])
  const [isDefault, setIsDefault] = useState(false)
  const [bg, setBg] = useState<{ url: string | null; w: number; h: number }>({ url: null, w: 1754, h: 1240 })
  const [selected, setSelected] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const canvasRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const loadBackground = useCallback(
    async (template: Template) => {
      if (!template.has_background) {
        setBg({ url: null, w: template.bg_width, h: template.bg_height })
        return
      }
      try {
        const blob = await download(`/api/v1/admin/certificate-templates/${template.id}/background`)
        setBg({ url: URL.createObjectURL(blob), w: template.bg_width, h: template.bg_height })
      } catch {
        setBg({ url: null, w: template.bg_width, h: template.bg_height })
      }
    },
    [download],
  )

  useEffect(() => {
    if (loaded.state.status === 'success') {
      const template = loaded.state.data
      setName(template.name)
      setElements(template.elements)
      setIsDefault(template.is_default)
      void loadBackground(template)
    }
  }, [loaded.state, loadBackground])

  useEffect(() => () => void (previewUrl && URL.revokeObjectURL(previewUrl)), [previewUrl])

  const scale = useMemo(() => {
    const widthMm = bg.w >= bg.h ? LONG_MM : (LONG_MM * bg.w) / bg.h
    return { widthMm, heightMm: bg.w >= bg.h ? (LONG_MM * bg.h) / bg.w : LONG_MM }
  }, [bg])

  function update(index: number, patch: Partial<El>) {
    setElements((list) => list.map((el, i) => (i === index ? { ...el, ...patch } : el)))
  }

  function add(type: ElType) {
    setElements((list) => [...list, newElement(type)])
    setSelected(elements.length)
  }

  function remove(index: number) {
    setElements((list) => list.filter((_, i) => i !== index))
    setSelected(null)
  }

  function startDrag(event: React.PointerEvent, index: number) {
    event.preventDefault()
    setSelected(index)
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const el = elements[index]
    const offsetX = ((event.clientX - rect.left) / rect.width) * 100 - el.x
    const offsetY = ((event.clientY - rect.top) / rect.height) * 100 - el.y
    function move(e: PointerEvent) {
      update(index, {
        x: clamp(((e.clientX - rect.left) / rect.width) * 100 - offsetX, 0, 100),
        y: clamp(((e.clientY - rect.top) / rect.height) * 100 - offsetY, 0, 100),
      })
    }
    function up() {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  function startResize(event: React.PointerEvent, index: number) {
    event.preventDefault()
    event.stopPropagation()
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const el = elements[index]
    function move(e: PointerEvent) {
      update(index, { w: clamp(((e.clientX - rect.left) / rect.width) * 100 - el.x, 3, 100) })
    }
    function up() {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  async function save(): Promise<boolean> {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await api(`/api/v1/admin/certificate-templates/${templateId}`, {
        method: 'PUT',
        body: { name: name.trim() || 'Dizayn', elements, is_default: isDefault },
      })
      setMessage('✓ Saqlandi.')
      return true
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
      return false
    } finally {
      setBusy(false)
    }
  }

  async function uploadBackground(file: File) {
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const template = await api<Template>(`/api/v1/admin/certificate-templates/${templateId}/background`, {
        method: 'PUT',
        body: form,
      })
      await loadBackground(template)
      setMessage("✓ Dizayn rasmi yuklandi.")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Rasmni yuklab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function preview() {
    if (!(await save())) return
    setBusy(true)
    try {
      const blob = await download(`/api/v1/admin/certificate-templates/${templateId}/preview.png`)
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      setPreviewUrl(URL.createObjectURL(blob))
    } catch {
      setError("Namunani ko'rsatib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  if (loaded.state.status === 'loading') return <LoadingState />
  if (loaded.state.status === 'error') return <ErrorState message={loaded.state.error.message} onRetry={loaded.reload} />

  const active = selected !== null ? elements[selected] : null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => navigate('certificates?tab=designs')}>
            ← Orqaga
          </Button>
          <Input value={name} onChange={(e) => setName(e.target.value)} className="w-64" placeholder="Dizayn nomi" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
            Asosiy dizayn (avtomatik sertifikatlar uchun)
          </label>
          <Button variant="secondary" onClick={() => fileRef.current?.click()} loading={busy}>
            🖼 Rasm yuklash
          </Button>
          <Button variant="secondary" onClick={() => void preview()} loading={busy}>
            👁 Namuna
          </Button>
          <Button onClick={() => void save()} loading={busy}>
            💾 Saqlash
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,application/pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void uploadBackground(file)
              e.target.value = ''
            }}
          />
        </div>
      </div>
      <InlineError message={error} />
      {message && <p className="text-sm text-emerald-600">{message}</p>}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card className="p-3">
          <p className="mb-2 text-xs text-app-hint">
            Elementni sudrab joyini o'zgartiring; pastki-o'ng burchakdan kengligini torting. O'ng tarafdan shrift, o'lcham va
            rangni sozlang.
          </p>
          <div
            ref={canvasRef}
            onPointerDown={() => setSelected(null)}
            className="relative mx-auto w-full select-none overflow-hidden rounded border border-app-border bg-white shadow-inner"
            style={{ aspectRatio: `${bg.w} / ${bg.h}`, maxWidth: bg.w >= bg.h ? '100%' : '460px' }}
          >
            {bg.url && <img src={bg.url} alt="" className="pointer-events-none absolute inset-0 h-full w-full" />}
            {!bg.url && (
              <div className="absolute inset-0 flex items-center justify-center text-sm text-app-hint">
                Dizayn rasmi hali yuklanmagan
              </div>
            )}
            {elements.map((el, index) => (
              <CanvasElement
                key={index}
                el={el}
                selected={selected === index}
                widthMm={scale.widthMm}
                onPointerDown={(e) => startDrag(e, index)}
                onResize={(e) => startResize(e, index)}
                canvas={canvasRef.current}
              />
            ))}
          </div>
        </Card>

        <div className="space-y-3">
          <Card className="p-3">
            <p className="mb-2 text-sm font-semibold">Element qo'shish</p>
            <div className="flex flex-wrap gap-1.5">
              {(Object.keys(LABELS) as ElType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => add(type)}
                  className="rounded border border-app-border px-2 py-1 text-xs hover:bg-app-muted/40"
                >
                  + {LABELS[type]}
                </button>
              ))}
            </div>
          </Card>

          {active && selected !== null ? (
            <Card className="space-y-2 p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold">{LABELS[active.type]}</p>
                <button type="button" className="text-xs text-app-danger" onClick={() => remove(selected)}>
                  O'chirish
                </button>
              </div>
              {active.type === 'text' && (
                <Field label="Matn">
                  <Input value={active.content} maxLength={240} onChange={(e) => update(selected, { content: e.target.value })} />
                </Field>
              )}
              <div className="grid grid-cols-3 gap-2 text-xs">
                <label>
                  X %
                  <Input type="number" value={Math.round(active.x)} onChange={(e) => update(selected, { x: clamp(Number(e.target.value), 0, 100) })} />
                </label>
                <label>
                  Y %
                  <Input type="number" value={Math.round(active.y)} onChange={(e) => update(selected, { y: clamp(Number(e.target.value), 0, 100) })} />
                </label>
                <label>
                  Kenglik %
                  <Input type="number" value={Math.round(active.w)} onChange={(e) => update(selected, { w: clamp(Number(e.target.value), 3, 100) })} />
                </label>
              </div>
              {IMAGE_TYPES.includes(active.type) ? (
                <Field label="Ko'rinish" hint="To'q dizaynda «Och» ni tanlang">
                  <Select value={active.variant} onChange={(e) => update(selected, { variant: e.target.value as El['variant'] })}>
                    <option value="auto">Avtomatik</option>
                    <option value="light">Och (to'q fon uchun)</option>
                    <option value="dark">To'q (och fon uchun)</option>
                  </Select>
                </Field>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <label>
                      O'lcham (pt)
                      <Input type="number" value={active.size} onChange={(e) => update(selected, { size: clamp(Number(e.target.value), 4, 200) })} />
                    </label>
                    <label>
                      Rang
                      <input type="color" value={active.color} onChange={(e) => update(selected, { color: e.target.value })} className="h-9 w-full rounded border border-app-border" />
                    </label>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <label>
                      Shrift
                      <Select value={active.font} onChange={(e) => update(selected, { font: e.target.value as El['font'] })}>
                        <option value="serif">Serif (bezakli)</option>
                        <option value="sans">Sans (oddiy)</option>
                        <option value="mono">Mono</option>
                      </Select>
                    </label>
                    <label>
                      Tekislash
                      <Select value={active.align} onChange={(e) => update(selected, { align: e.target.value as El['align'] })}>
                        <option value="left">Chap</option>
                        <option value="center">Markaz</option>
                        <option value="right">O'ng</option>
                      </Select>
                    </label>
                  </div>
                  <div className="flex gap-3 text-sm">
                    <label className="flex items-center gap-1">
                      <input type="checkbox" checked={active.bold} onChange={(e) => update(selected, { bold: e.target.checked })} /> Qalin
                    </label>
                    <label className="flex items-center gap-1">
                      <input type="checkbox" checked={active.italic} onChange={(e) => update(selected, { italic: e.target.checked })} /> Qiyshiq
                    </label>
                  </div>
                </>
              )}
            </Card>
          ) : (
            <Card className="p-3 text-sm text-app-hint">Sozlash uchun elementni tanlang yoki yangisini qo'shing.</Card>
          )}

          {previewUrl && (
            <Card className="p-3">
              <p className="mb-2 text-sm font-semibold">Namuna (PDF ko'rinishi)</p>
              <img src={previewUrl} alt="Namuna" className="w-full rounded border border-app-border" />
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

function CanvasElement({
  el,
  selected,
  widthMm,
  onPointerDown,
  onResize,
  canvas,
}: {
  el: El
  selected: boolean
  widthMm: number
  onPointerDown: (e: React.PointerEvent) => void
  onResize: (e: React.PointerEvent) => void
  canvas: HTMLDivElement | null
}) {
  const canvasWidthPx = canvas?.getBoundingClientRect().width ?? 600
  const pxPerMm = canvasWidthPx / widthMm
  const fontPx = IMAGE_TYPES.includes(el.type) ? 0 : Math.max(6, el.size * MM_PER_PT * pxPerMm)
  const image = IMAGE_TYPES.includes(el.type)
  return (
    <div
      onPointerDown={(e) => {
        e.stopPropagation()
        onPointerDown(e)
      }}
      className={`absolute cursor-move ${selected ? 'outline outline-2 outline-app-accent' : 'outline-dashed outline-1 outline-app-border/70'}`}
      style={{ left: `${el.x}%`, top: `${el.y}%`, width: `${el.w}%` }}
    >
      {image ? (
        <div
          className="flex aspect-square w-full items-center justify-center bg-black/5 text-[10px] font-semibold text-app-hint"
          style={{ border: '1px dashed rgba(0,0,0,0.25)' }}
        >
          {SAMPLE[el.type]}
        </div>
      ) : (
        <div
          style={{
            fontFamily: FONT_CSS[el.font],
            fontSize: `${fontPx}px`,
            color: el.color,
            textAlign: el.align,
            fontWeight: el.bold ? 700 : 400,
            fontStyle: el.italic ? 'italic' : 'normal',
            lineHeight: 1.2,
            whiteSpace: 'pre-wrap',
            overflowWrap: 'break-word',
          }}
        >
          {el.type === 'text' ? el.content || SAMPLE.text : SAMPLE[el.type]}
        </div>
      )}
      {selected && (
        <span
          onPointerDown={onResize}
          className="absolute -bottom-1.5 -right-1.5 h-3 w-3 cursor-se-resize rounded-sm border border-white bg-app-accent"
        />
      )}
    </div>
  )
}
