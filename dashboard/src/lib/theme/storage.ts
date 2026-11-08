/**
 * 主题配置的 localStorage 存储管理模块。
 */

import { DASHBOARD_STYLES, DEFAULT_DASHBOARD_STYLE } from './tokens'
import type {
  BackgroundConfigMap,
  StyleBackgroundConfigMap,
  StyleCustomCSS,
  StyleTokenOverrides,
  UserThemeConfig,
} from './tokens'

export const THEME_STORAGE_KEYS = {
  MODE: 'maibot-theme-mode',
  PRESET: 'maibot-theme-preset',
  STYLE_OVERRIDES: 'maibot-theme-style-overrides',
  STYLE_CUSTOM_CSS: 'maibot-theme-style-custom-css',
  STYLE_BACKGROUND_CONFIG: 'maibot-theme-style-background',
  DASHBOARD_STYLE: 'maibot-theme-dashboard-style',
} as const

const DEFAULT_THEME_CONFIG: UserThemeConfig = {
  selectedPreset: 'light',
  styleTokenOverrides: {},
  styleCustomCSS: {},
  styleBackgroundConfig: {},
  dashboardStyle: DEFAULT_DASHBOARD_STYLE,
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

type ImportThemeConfigRecord = Record<string, unknown> & Pick<UserThemeConfig, 'selectedPreset'>

function hasRequiredImportThemeFields(
  config: Record<string, unknown>,
  errors: string[]
): config is ImportThemeConfigRecord {
  let valid = true

  if (typeof config.selectedPreset !== 'string') {
    errors.push('selectedPreset must be a string')
    valid = false
  }

  return valid
}

function normalizeStyleTokenOverrides(value: unknown): StyleTokenOverrides {
  if (!isRecord(value)) {
    return {}
  }

  const nextOverrides: StyleTokenOverrides = {}
  for (const style of DASHBOARD_STYLES) {
    if (isRecord(value[style])) {
      nextOverrides[style] = value[style] as StyleTokenOverrides[typeof style]
    }
  }

  return nextOverrides
}

function normalizeStyleCustomCSS(value: unknown): StyleCustomCSS {
  if (!isRecord(value)) {
    return {}
  }

  const nextCustomCSS: StyleCustomCSS = {}
  if (typeof value.modern === 'string') {
    nextCustomCSS.modern = value.modern
  }

  return nextCustomCSS
}

function normalizeStyleBackgroundConfig(value: unknown): StyleBackgroundConfigMap {
  if (!isRecord(value)) {
    return {}
  }

  const nextBackgroundConfig: StyleBackgroundConfigMap = {}
  for (const style of DASHBOARD_STYLES) {
    if (isRecord(value[style])) {
      nextBackgroundConfig[style] = value[style] as BackgroundConfigMap
    }
  }

  return nextBackgroundConfig
}

function parseJSONStorage(key: string): unknown {
  const value = localStorage.getItem(key)
  if (!value) {
    return undefined
  }

  return JSON.parse(value)
}

export function loadThemeConfig(): UserThemeConfig {
  const preset = localStorage.getItem(THEME_STORAGE_KEYS.PRESET)

  let styleTokenOverrides: StyleTokenOverrides = {}
  let styleCustomCSS: StyleCustomCSS = {}
  let styleBackgroundConfig: StyleBackgroundConfigMap = {}

  try {
    styleTokenOverrides = normalizeStyleTokenOverrides(
      parseJSONStorage(THEME_STORAGE_KEYS.STYLE_OVERRIDES)
    )
  } catch {
    styleTokenOverrides = {}
  }

  try {
    styleCustomCSS = normalizeStyleCustomCSS(parseJSONStorage(THEME_STORAGE_KEYS.STYLE_CUSTOM_CSS))
  } catch {
    styleCustomCSS = {}
  }

  try {
    styleBackgroundConfig = normalizeStyleBackgroundConfig(
      parseJSONStorage(THEME_STORAGE_KEYS.STYLE_BACKGROUND_CONFIG)
    )
  } catch {
    styleBackgroundConfig = {}
  }

  return {
    selectedPreset: preset || DEFAULT_THEME_CONFIG.selectedPreset,
    styleTokenOverrides,
    styleCustomCSS,
    styleBackgroundConfig,
    dashboardStyle: DEFAULT_DASHBOARD_STYLE,
  }
}

export function saveThemeConfig(config: UserThemeConfig): void {
  localStorage.setItem(THEME_STORAGE_KEYS.PRESET, config.selectedPreset)
  localStorage.setItem(
    THEME_STORAGE_KEYS.STYLE_OVERRIDES,
    JSON.stringify(normalizeStyleTokenOverrides(config.styleTokenOverrides))
  )
  localStorage.setItem(
    THEME_STORAGE_KEYS.STYLE_CUSTOM_CSS,
    JSON.stringify(normalizeStyleCustomCSS(config.styleCustomCSS))
  )
  localStorage.setItem(
    THEME_STORAGE_KEYS.STYLE_BACKGROUND_CONFIG,
    JSON.stringify(normalizeStyleBackgroundConfig(config.styleBackgroundConfig))
  )
  localStorage.setItem(THEME_STORAGE_KEYS.DASHBOARD_STYLE, DEFAULT_DASHBOARD_STYLE)
}

export function saveThemePartial(partial: Partial<UserThemeConfig>): void {
  const current = loadThemeConfig()
  saveThemeConfig({
    ...current,
    ...partial,
  })
}

export function exportThemeJSON(): string {
  const config = loadThemeConfig()
  return JSON.stringify(config, null, 2)
}

export function importThemeJSON(json: string): { success: boolean; errors: string[] } {
  const errors: string[] = []

  let config: unknown
  try {
    config = JSON.parse(json)
  } catch (error) {
    return {
      success: false,
      errors: [`Invalid JSON format: ${error instanceof Error ? error.message : 'Unknown error'}`],
    }
  }

  if (!isRecord(config)) {
    return {
      success: false,
      errors: ['Configuration must be a JSON object'],
    }
  }

  const hasRequiredFields = hasRequiredImportThemeFields(config, errors)
  if (
    config.styleTokenOverrides !== undefined &&
    (typeof config.styleTokenOverrides !== 'object' || config.styleTokenOverrides === null)
  ) {
    errors.push('styleTokenOverrides must be an object')
  }
  if (
    config.styleCustomCSS !== undefined &&
    (typeof config.styleCustomCSS !== 'object' || config.styleCustomCSS === null)
  ) {
    errors.push('styleCustomCSS must be an object')
  }
  if (
    config.styleBackgroundConfig !== undefined &&
    (typeof config.styleBackgroundConfig !== 'object' || config.styleBackgroundConfig === null)
  ) {
    errors.push('styleBackgroundConfig must be an object')
  }
  if (config.dashboardStyle !== undefined && typeof config.dashboardStyle !== 'string') {
    errors.push('dashboardStyle must be a string')
  }

  if (errors.length > 0) {
    return { success: false, errors }
  }
  const selectedPreset = config.selectedPreset
  if (!hasRequiredFields || typeof selectedPreset !== 'string') {
    throw new Error('Theme import required fields were not narrowed after validation')
  }

  saveThemeConfig({
    selectedPreset,
    styleTokenOverrides: normalizeStyleTokenOverrides(config.styleTokenOverrides),
    styleCustomCSS: normalizeStyleCustomCSS(config.styleCustomCSS),
    styleBackgroundConfig: normalizeStyleBackgroundConfig(config.styleBackgroundConfig),
    dashboardStyle: DEFAULT_DASHBOARD_STYLE,
  })

  return { success: true, errors: [] }
}

export function resetThemeToDefault(): void {
  Object.values(THEME_STORAGE_KEYS).forEach((key) => {
    localStorage.removeItem(key)
  })
}
