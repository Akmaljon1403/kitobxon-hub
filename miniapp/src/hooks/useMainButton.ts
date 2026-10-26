import { useEffect, useRef } from 'react'

import { getWebApp } from '../utils/telegram'

interface MainButtonOptions {
  text: string
  onClick: () => void
  /** Hidden when false (the button is removed from the screen). Default true. */
  visible?: boolean
  /** Shows the spinner and blocks taps while an action is in flight. Default false. */
  loading?: boolean
  /** Dimmed and non-tappable when false. Default true. */
  enabled?: boolean
}

/**
 * Drives Telegram's native bottom MainButton for the lifetime of a component.
 *
 * Every call is feature-detected: in a browser (or the e2e stand-in, where `MainButton` is an empty
 * object) the hook simply does nothing, so a screen that uses it still renders and works with its own
 * in-page button as the fallback.
 */
export function useMainButton({ text, onClick, visible = true, loading = false, enabled = true }: MainButtonOptions): void {
  // Keep the latest onClick without re-registering the Telegram handler on every render.
  const handler = useRef(onClick)
  handler.current = onClick

  useEffect(() => {
    const button = getWebApp()?.MainButton
    if (!button || typeof button.onClick !== 'function' || typeof button.show !== 'function') return
    const fire = () => handler.current()
    button.onClick(fire)
    return () => {
      try {
        button.offClick?.(fire)
        button.hide?.()
        button.hideProgress?.()
      } catch {
        // ignore teardown errors in limited webviews
      }
    }
  }, [])

  useEffect(() => {
    const button = getWebApp()?.MainButton
    if (!button || typeof button.setText !== 'function') return
    try {
      button.setText(text)
      if (!visible) {
        button.hide?.()
        return
      }
      button.show?.()
      if (enabled) button.enable?.()
      else button.disable?.()
      if (loading) button.showProgress?.(true)
      else button.hideProgress?.()
    } catch {
      // ignore: the in-page button remains the fallback
    }
  }, [text, visible, loading, enabled])
}
