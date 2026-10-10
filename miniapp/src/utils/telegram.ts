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
  webApp.disableVerticalSwipes?.()
  document.documentElement.dataset.theme = webApp.colorScheme
  webApp.onEvent('themeChanged', () => {
    document.documentElement.dataset.theme = webApp.colorScheme
  })
}

export function haptic(type: 'success' | 'error' | 'warning'): void {
  getWebApp()?.HapticFeedback?.notificationOccurred(type)
}

export function openExternalLink(url: string): void {
  const webApp = getWebApp()
  if (webApp) webApp.openLink(url)
  else window.open(url, '_blank', 'noopener,noreferrer')
}

/** A t.me link (a channel) inside Telegram, without closing the app. */
export function openTelegramLink(url: string): void {
  const webApp = getWebApp()
  if (webApp) webApp.openTelegramLink(url)
  else window.open(url, '_blank', 'noopener,noreferrer')
}

export function openBot(username: string | null, start = ''): void {
  if (!username) return
  const url = `https://t.me/${username}${start ? `?start=${start}` : ''}`
  const webApp = getWebApp()
  if (webApp) {
    webApp.openTelegramLink(url)
    webApp.close()
  } else {
    window.location.href = url
  }
}

/** Native confirmation dialog inside Telegram, browser confirm() elsewhere. */
export function confirmAction(message: string): Promise<boolean> {
  const webApp = getWebApp()
  if (webApp && webApp.isVersionAtLeast('6.2')) {
    return new Promise((resolve) => webApp.showConfirm(message, (ok) => resolve(ok)))
  }
  return Promise.resolve(window.confirm(message))
}
