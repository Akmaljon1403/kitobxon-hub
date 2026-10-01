import type { TelegramWebApp } from '../types/telegram'

/** Returns the Telegram WebApp object when the page runs inside Telegram, otherwise null. */
export function getWebApp(): TelegramWebApp | null {
  const webApp = window.Telegram?.WebApp
  // Outside Telegram the script still defines WebApp, but initData is empty.
  return webApp && webApp.initData ? webApp : null
}

export function initTelegram(): void {
  const webApp = getWebApp()
  if (!webApp) return
  webApp.ready()
  webApp.expand()
  document.documentElement.dataset.theme = webApp.colorScheme
  webApp.onEvent('themeChanged', () => {
    document.documentElement.dataset.theme = webApp.colorScheme
  })
}
