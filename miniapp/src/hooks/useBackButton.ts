import { useEffect } from 'react'

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
