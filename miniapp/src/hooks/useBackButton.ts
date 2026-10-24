import { useEffect } from 'react'

import { navigate } from '../utils/router'
import { getWebApp } from '../utils/telegram'

/** Shows Telegram's native back button while the component is mounted. */
export function useBackButton(onBack: () => void): void {
  useEffect(() => {
    const button = getWebApp()?.BackButton
    if (!button) return
    button.show()
    button.onClick(onBack)
    return () => {
      button.offClick(onBack)
      button.hide()
    }
  }, [onBack])
}

const toHome = () => navigate('/')

/** Top-level sections (tabs, lists): the back button returns to the home menu, so pressing back never
 * closes the bot from a sub-screen — only the home menu itself has no back button and so exits. */
export function useHomeBackButton(): void {
  useBackButton(toHome)
}
