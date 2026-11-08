import { renderHook } from '@testing-library/react'
import { useContext } from 'react'
import { describe, expect, it } from 'vitest'

import { ThemeProviderContext } from '../theme-context'
import { DEFAULT_DASHBOARD_STYLE } from '../theme/tokens'

describe('ThemeProviderContext', () => {
  it('无 Provider 时暴露默认初始值，空实现可调用且不抛错', () => {
    const { result } = renderHook(() => useContext(ThemeProviderContext))
    const state = result.current

    expect(state.theme).toBe('system')
    expect(state.resolvedTheme).toBe('light')
    expect(state.themeConfig).toEqual({
      selectedPreset: 'light',
      styleTokenOverrides: {},
      styleCustomCSS: {},
      dashboardStyle: DEFAULT_DASHBOARD_STYLE,
      styleBackgroundConfig: {},
    })

    expect(state.setTheme('dark')).toBeNull()
    expect(state.updateThemeConfig({ selectedPreset: 'dark' })).toBeNull()
    expect(state.resetTheme()).toBeNull()
  })
})
