import { readFileSync } from 'node:fs'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

// Main journeys, in order: an admin prepares a book, an event and a test through the API; a
// member uses the Mini App (home, QR-code check-in, test); the admin checks the results in the
// Admin Panel. Telegram itself is replaced by a small stand-in that hands over signed launch data.

interface State {
  member: { init_data: string; first_name: string; last_name: string }
  stranger_init_data: string
  admin_links: { api: string; ui: string }
}

const state: State = JSON.parse(readFileSync(new URL('../.state.json', import.meta.url), 'utf8'))

const ANSWERS: Record<string, string> = { muallifi: 'Abdulla Qodiriy', qahramoni: 'Otabek' }

let adminToken = ''
let eventId = ''
let testId = ''

function telegramStandIn(initData: string | null): string {
  if (initData === null) return ''
  return `window.Telegram = { WebApp: {
    initData: ${JSON.stringify(initData)}, initDataUnsafe: {}, version: '8.0', platform: 'android',
    colorScheme: 'light', themeParams: {}, isExpanded: true, viewportHeight: 780, viewportStableHeight: 780,
    BackButton: { show(){return this}, hide(){return this}, onClick(){return this}, offClick(){return this} },
    MainButton: {}, HapticFeedback: { notificationOccurred(){}, impactOccurred(){}, selectionChanged(){} },
    ready(){}, expand(){}, close(){}, isVersionAtLeast(){return true}, disableVerticalSwipes(){},
    enableClosingConfirmation(){}, disableClosingConfirmation(){},
    openLink(){}, openTelegramLink(){}, showAlert(m, cb){cb && cb()}, showConfirm(m, cb){cb(true)},
    onEvent(){}, offEvent(){}
  }};`
}

/** Opens the Mini App the way Telegram would and records any browser error. */
async function openMiniApp(page: Page, initData: string | null, route: string): Promise<string[]> {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => message.type() === 'error' && errors.push(message.text()))
  // telegram-web-app.js is only a bridge to the Telegram client; the stand-in replaces it.
  await page.route('https://telegram.org/**', (r) => r.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.setViewportSize({ width: 390, height: 844 })
  if (initData !== null) await page.addInitScript(telegramStandIn(initData))
  await page.goto(`/app/#${route}`)
  return errors
}

async function adminApi(request: APIRequestContext, method: 'get' | 'post' | 'put', path: string, data?: unknown) {
  const response = await request[method](`/api/v1${path}`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data,
  })
  expect(response.ok(), `${method.toUpperCase()} ${path}: ${response.status()} ${await response.text()}`).toBeTruthy()
  return response.status() === 204 ? null : response.json()
}

test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  const login = await request.post('/api/v1/auth/admin/exchange', { data: { token: state.admin_links.api } })
  expect(login.ok()).toBeTruthy()
  adminToken = (await login.json()).access_token

  const now = Date.now()
  const iso = (minutes: number) => new Date(now + minutes * 60_000).toISOString()
  const book = await adminApi(request, 'post', '/admin/books', {
    title: "O'tkan kunlar",
    author: 'Abdulla Qodiriy',
    status: 'ACTIVE',
  })
  const event = await adminApi(request, 'post', '/admin/events', {
    title: "O'tkan kunlar — muhokama",
    location: 'Kutubxona',
    book_id: book.id,
    starts_at: iso(-5),
    ends_at: iso(60),
    status: 'PUBLISHED',
  })
  eventId = event.id
  const quiz = await adminApi(request, 'post', '/admin/tests', {
    title: "«O'tkan kunlar» — sinov testi",
    book_id: book.id,
    starts_at: iso(-5),
    ends_at: iso(24 * 60),
    duration_minutes: 10,
    passing_score: 10,
    attempts_allowed: 1,
  })
  testId = quiz.id
  await adminApi(request, 'put', `/admin/tests/${testId}/questions`, {
    questions: [
      {
        type: 'SINGLE_CHOICE',
        text: 'Romanning muallifi kim?',
        points: 1,
        options: [{ text: 'Abdulla Qodiriy', is_correct: true }, { text: "Cho'lpon" }, { text: 'Oybek' }],
      },
      {
        type: 'SINGLE_CHOICE',
        text: 'Romanning bosh qahramoni kim?',
        points: 1,
        options: [{ text: 'Otabek', is_correct: true }, { text: 'Anvar' }, { text: "Ra'no" }],
      },
    ],
  })
  await adminApi(request, 'post', `/admin/tests/${testId}/publish`)
})

test('a registered member opens the Mini App', async ({ page }) => {
  const errors = await openMiniApp(page, state.member.init_data, '/')
  await expect(page.getByText('Assalomu alaykum,')).toBeVisible()
  await expect(page.getByText(`${state.member.first_name}!`)).toBeVisible()
  await expect(page.getByText("O'tkan kunlar").first()).toBeVisible()
  await page.goto('/app/#/books')
  await expect(page.getByText('Abdulla Qodiriy').first()).toBeVisible()
  expect(errors).toEqual([])
})

test('the member checks in with the code shown by the admin', async ({ page, request }) => {
  await adminApi(request, 'post', `/admin/events/${eventId}/attendance/open`, {})
  const { code } = await adminApi(request, 'get', `/admin/events/${eventId}/attendance/token`)

  const errors = await openMiniApp(page, state.member.init_data, `/events/${eventId}`)
  await page.getByLabel('Davomat kodi').fill(code)
  await page.getByRole('button', { name: 'Yuborish' }).click()
  await expect(page.getByText('Davomatingiz qayd etildi!')).toBeVisible()
  expect(errors).toEqual([])
})

test('the member takes the test and gets full points', async ({ page }) => {
  const errors = await openMiniApp(page, state.member.init_data, `/tests/${testId}`)
  await page.getByRole('button', { name: /Testni boshlash/ }).click()
  await expect(page.getByRole('timer')).toBeVisible()
  for (let index = 0; index < 2; index++) {
    const question = (await page.locator('main h2').textContent()) ?? ''
    const key = Object.keys(ANSWERS).find((word) => question.includes(word))
    expect(key, `unexpected question: ${question}`).toBeTruthy()
    await page.getByRole('radio', { name: ANSWERS[key!] }).click()
    if (index === 0) await page.getByRole('button', { name: 'Keyingi →' }).click()
  }
  await page.getByRole('button', { name: 'Yakunlash ✓' }).click()
  await expect(page.getByText("2 ta to'g'ri javob (2 tadan)")).toBeVisible()

  await page.goto('/app/#/results')
  await expect(page.getByRole('heading', { name: /Natijalarim/ })).toBeVisible()
  await expect(page.getByText("O'tkan kunlar — muhokama").first()).toBeVisible()
  expect(errors).toEqual([])
})

test('the points add up on the server', async ({ request }) => {
  const login = await request.post('/api/v1/auth/telegram', { data: { init_data: state.member.init_data } })
  const token = (await login.json()).access_token
  const scores = await (await request.get('/api/v1/me/scores', { headers: { Authorization: `Bearer ${token}` } })).json()
  const breakdown: Record<string, number> = scores.breakdown
  expect(breakdown.TEST).toBe(20)
  expect(breakdown.ATTENDANCE).toBeGreaterThan(0)
  // Everything else (e.g. a first-achievement bonus) is listed too, and the total is their sum.
  expect(scores.total).toBe(Object.values(breakdown).reduce((sum, value) => sum + value, 0))
})

test('the admin signs in with a one-time link and sees the results', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => message.type() === 'error' && errors.push(message.text()))
  // Outside Telegram the Telegram script has nothing to do; keep the run independent of telegram.org.
  await page.route('https://telegram.org/**', (r) => r.fulfill({ contentType: 'application/javascript', body: '' }))

  await page.goto(`/admin/#/login?token=${state.admin_links.ui}`)
  await expect(page.getByText("Jami a'zolar")).toBeVisible()

  await page.goto(`/admin/#/events/${eventId}/attendance`)
  await expect(page.getByText('Qatnashdi: 1')).toBeVisible()
  await expect(page.getByText(`${state.member.last_name} ${state.member.first_name}`)).toBeVisible()

  await page.goto(`/admin/#/tests/${testId}/results`)
  await expect(page.getByText(`${state.member.last_name} ${state.member.first_name}`)).toBeVisible()

  await page.goto('/admin/#/analytics')
  await expect(page.getByText("Faol a'zolar soni")).toBeVisible()
  expect(errors).toEqual([])

  // A used link cannot be used again.
  const again = await page.request.post('/api/v1/auth/admin/exchange', { data: { token: state.admin_links.ui } })
  expect(again.status()).toBe(401)
})

test('a stranger is sent to the bot to register', async ({ page }) => {
  await openMiniApp(page, state.stranger_init_data, '/')
  await expect(page.getByText('Xush kelibsiz!')).toBeVisible()
  await expect(page.getByRole('button', { name: "Ro'yxatdan o'tish" })).toBeVisible()
})

test('the Mini App explains when it is opened outside Telegram', async ({ page }) => {
  await openMiniApp(page, null, '/')
  await expect(page.getByText('Bu ilova Telegram ichida ishlaydi.')).toBeVisible()
})
