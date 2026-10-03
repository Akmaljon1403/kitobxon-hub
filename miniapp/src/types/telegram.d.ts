// Minimal typings for the Telegram Mini Apps API (https://core.telegram.org/bots/webapps)
// covering only what Kitobxon Hub uses.

export interface TelegramThemeParams {
  bg_color?: string
  text_color?: string
  hint_color?: string
  link_color?: string
  button_color?: string
  button_text_color?: string
  secondary_bg_color?: string
}

export interface TelegramWebAppUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
  language_code?: string
  photo_url?: string
}

export interface TelegramBottomButton {
  text: string
  isVisible: boolean
  isActive: boolean
  setText(text: string): TelegramBottomButton
  show(): TelegramBottomButton
  hide(): TelegramBottomButton
  enable(): TelegramBottomButton
  disable(): TelegramBottomButton
  showProgress(leaveActive?: boolean): TelegramBottomButton
  hideProgress(): TelegramBottomButton
  onClick(callback: () => void): TelegramBottomButton
  offClick(callback: () => void): TelegramBottomButton
}

export interface TelegramBackButton {
  isVisible: boolean
  show(): TelegramBackButton
  hide(): TelegramBackButton
  onClick(callback: () => void): TelegramBackButton
  offClick(callback: () => void): TelegramBackButton
}

export interface TelegramWebApp {
  initData: string
  initDataUnsafe: { user?: TelegramWebAppUser; start_param?: string; auth_date?: number }
  version: string
  platform: string
  colorScheme: 'light' | 'dark'
  themeParams: TelegramThemeParams
  isExpanded: boolean
  viewportHeight: number
  viewportStableHeight: number
  MainButton: TelegramBottomButton
  BackButton: TelegramBackButton
  HapticFeedback?: {
    impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
    notificationOccurred(type: 'error' | 'success' | 'warning'): void
    selectionChanged(): void
  }
  ready(): void
  expand(): void
  close(): void
  isVersionAtLeast(version: string): boolean
  disableVerticalSwipes?: () => void
  enableClosingConfirmation?: () => void
  disableClosingConfirmation?: () => void
  openLink(url: string, options?: { try_instant_view?: boolean }): void
  openTelegramLink(url: string): void
  showAlert(message: string, callback?: () => void): void
  showConfirm(message: string, callback?: (confirmed: boolean) => void): void
  showScanQrPopup?: (params: { text?: string }, callback?: (data: string) => boolean | void) => void
  closeScanQrPopup?: () => void
  /** Bot API 6.1+: shows a Telegram invoice (Stars payments) inside the Mini App. */
  openInvoice?: (url: string, callback?: (status: 'paid' | 'cancelled' | 'failed' | 'pending') => void) => void
  /** Bot API 8.0+: Telegram's own "save file" dialog for a public HTTPS link. */
  downloadFile?: (params: { url: string; file_name: string }, callback?: (accepted: boolean) => void) => void
  onEvent(eventType: string, handler: (...args: unknown[]) => void): void
  offEvent(eventType: string, handler: (...args: unknown[]) => void): void
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp }
  }
}
